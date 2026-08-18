"""Run the versioned scenario registry over the in-process evaluation harness.

The driver owns orchestration and persistence only. Capture and scoring remain in
``evals.harness`` so the three seam definitions do not diverge between pytest and
recorded runs.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml

# Safe to import above the environment bind below: the loader reads the YAML
# directly and never touches src.core.config, so it cannot freeze Settings().
from evals.fixtures.loader import fixture_database_url

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evals" / "runs"
SCORER_VERSION = "harness-score-v1"
MAX_RETRIES = 2
SDK_MAX_RETRIES = 0

# A per-minute token quota is cleared by waiting out its window, not by a short
# backoff: a 429 on Groq's 8000 TPM tier asks for 14-17s, so the 1s/2s ladder
# below retried inside the same blocked window and burned tokens without ever
# succeeding. Quota failures get their own ladder, and a provider that states
# its own wait wins over both.
DEFAULT_BACKOFF_SECONDS = (1.0, 2.0)
QUOTA_BACKOFF_SECONDS = (20.0, 40.0)
MAX_BACKOFF_SECONDS = 90.0
RETRY_HINT_MARGIN_SECONDS = 1.0
_RETRY_HINT_PATTERN = re.compile(r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s)\b", re.IGNORECASE)

# The 19 columns `evals/fixtures/seed_eval_db.sql` writes, in seed-file order.
# The three lifecycle columns are excluded deliberately: is_active, first_seen_at,
# and last_seen_at take their migration defaults at seed time, so the two
# timestamps carry the wall clock of the last fixture rebuild. Hashing them would
# give identical data a new fixture_hash after every rebuild and make
# _assert_comparable reject runs that are in fact comparable.
SEEDED_COLUMNS = (
    "id",
    "source",
    "external_id",
    "source_url",
    "title",
    "company",
    "role",
    "description",
    "tech_stack",
    "job_level",
    "location",
    "posted_date",
    "listing_expires_on",
    "created_on",
    "is_internship",
    "salary_min",
    "salary_max",
    "salary_currency",
    "is_salary_negotiable",
)


def _bind_fixture_environment() -> None:
    """Bind native driver runs before any src module can freeze Settings()."""
    os.environ["DATABASE_URL"] = fixture_database_url()
    # Default tracing off so a capture costs no Langfuse quota, but let an operator
    # opt in with LANGFUSE_ENABLED=true. Forcing it off unconditionally made every
    # captured trace_id None, so the viewer's trace field was structurally dead.
    os.environ.setdefault("LANGFUSE_ENABLED", "false")


@contextmanager
def _native_provider_environment():
    """Disable SDK retries only while the native driver owns retry accounting."""
    previous = os.environ.get("EVAL_DRIVER_DISABLE_PROVIDER_RETRIES")
    os.environ["EVAL_DRIVER_DISABLE_PROVIDER_RETRIES"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("EVAL_DRIVER_DISABLE_PROVIDER_RETRIES", None)
        else:
            os.environ["EVAL_DRIVER_DISABLE_PROVIDER_RETRIES"] = previous


def _tracing_enabled() -> bool:
    """Mirror src/agents/tracing/langfuse.py so the manifest cannot disagree with the run."""
    return os.environ.get("LANGFUSE_ENABLED", "true").lower() not in {"0", "false", "no"}


_bind_fixture_environment()

from evals import harness  # noqa: E402
from evals.scenarios import load_scenarios, repeat_count  # noqa: E402
from evals.sanitization import FORBIDDEN_CONTENT  # noqa: E402

# Below the bind because it reads config/prompts.yaml through src.core.config, which
# must not be frozen before the fixture environment is in place.
from src.agents.runtime.prompts import load_prompt_version  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_turn_pacing_seconds() -> float:
    """Seconds to idle before each turn so it meets an unspent per-minute window."""
    settings = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    return float(settings["eval"]["driver"]["turn_pacing_seconds"])


def _worktree_state() -> str:
    """Return whether the source used for this run is reproducible from Git."""
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return "clean" if not status.strip() else "dirty"


def _database_fingerprint(database_url: str) -> tuple[str, str, int]:
    """Fingerprint the resolved database contents, not the seed file on disk.

    Projects ``SEEDED_COLUMNS`` rather than ``*`` so the hash covers exactly the
    data the seed defines and stays stable across fixture rebuilds.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    expected_name = make_url(database_url).database
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            actual_name = connection.execute(text("SELECT current_database()")).scalar_one()
            if actual_name != expected_name:
                raise RuntimeError(
                    f"Fixture database mismatch: expected {expected_name!r}, got {actual_name!r}"
                )
            # SEEDED_COLUMNS is a frozen tuple of identifiers, never user input.
            projection = ", ".join(SEEDED_COLUMNS)
            rows = [
                dict(row)
                for row in connection.execute(
                    text(f"SELECT {projection} FROM clean_jobs ORDER BY id")
                ).mappings().all()
            ]
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 - make provenance failure explicit
        raise RuntimeError(f"Cannot fingerprint fixture database {expected_name!r}: {exc}") from exc
    finally:
        engine.dispose()
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), actual_name, len(rows)


def build_manifest() -> dict[str, Any]:
    settings_path = ROOT / "config" / "settings.yaml"
    prompts_path = ROOT / "config" / "prompts.yaml"
    fixture_path = ROOT / "evals" / "fixtures" / "seed_eval_db.sql"
    scenarios_path = ROOT / "evals" / "scenarios_v1.yaml"
    settings = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    agent = settings["agent"]
    worktree_state = _worktree_state()
    database_hash, database_name, database_row_count = _database_fingerprint(
        fixture_database_url()
    )
    return {
        "run_id": str(uuid.uuid4()),
        "started_at": _utc_now(),
        "finished_at": None,
        "git_sha": _git_sha(),
        "fixture_hash": database_hash,
        "fixture_seed_hash": _sha256(fixture_path),
        "scenario_registry_hash": _sha256(scenarios_path),
        "worktree_state": worktree_state,
        "baseline_eligible": worktree_state == "clean",
        "database_name": database_name,
        "database_row_count": database_row_count,
        # prompt_hash detects that the prompt changed; prompt_version names which prompt
        # produced the run. A capture that cannot name its prompt cannot be read as the
        # baseline for a later one, which is what T0024.1's version label is for.
        "prompt_version": load_prompt_version(),
        "prompt_hash": _sha256(prompts_path),
        "config_hash": _sha256(settings_path),
        # Provider is recorded per profile because a profile may override agent.provider,
        # and a capture that cannot say which provider produced it is not evidence. The
        # native knobs travel with it: `thinking` decides whether DeepSeek honored
        # `temperature` at all, so omitting it would hide the run's biggest variable.
        "providers": {
            profile: agent[profile].get("provider", agent["provider"])
            for profile in ("react", "sql_generation")
        },
        "models": {
            "react": agent["react"]["model"],
            "sql_generation": agent["sql_generation"]["model"],
        },
        "sampling": {
            profile: {
                key: agent[profile].get(key)
                for key in (
                    "temperature",
                    "max_tokens",
                    "reasoning_effort",
                    "reasoning_format",
                    "thinking",
                )
            }
            for profile in ("react", "sql_generation")
        },
        "retry_policy": {
            "max_retries_per_turn": MAX_RETRIES,
            "backoff_seconds": list(DEFAULT_BACKOFF_SECONDS),
            "quota_backoff_seconds": list(QUOTA_BACKOFF_SECONDS),
            "max_backoff_seconds": MAX_BACKOFF_SECONDS,
            "honors_provider_retry_hint": True,
            "provider_sdk_max_retries": SDK_MAX_RETRIES,
        },
        "turn_pacing_seconds": load_turn_pacing_seconds(),
        "tracing": {"langfuse_enabled": _tracing_enabled()},
        "retry_events": [],
        "scorer_version": SCORER_VERSION,
    }


def _new_run(manifest: dict[str, Any]) -> dict[str, Any]:
    return {"manifest": manifest, "status": "RUNNING", "scenarios": {}, "checkpoint": {}}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_run(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("manifest"), dict):
        raise ValueError(f"{path} is not a scenario-driver run artifact")
    return payload


def _assert_comparable(left: dict[str, Any], right: dict[str, Any]) -> None:
    if left["manifest"].get("worktree_state") != "clean" or right["manifest"].get("worktree_state") != "clean":
        raise ValueError("Runs are incomparable: dirty or unknown worktree state")
    fields = (
        "fixture_hash",
        "database_name",
        "database_row_count",
        "prompt_hash",
        "config_hash",
        "scenario_registry_hash",
    )
    differences = [field for field in fields if left["manifest"].get(field) != right["manifest"].get(field)]
    if differences:
        raise ValueError("Runs are incomparable: " + ", ".join(differences) + " differ")


def compare_runs(left_path: Path, right_path: Path) -> dict[str, Any]:
    left = load_run(left_path)
    right = load_run(right_path)
    _assert_comparable(left, right)
    return {"comparable": True, "left": left["manifest"]["run_id"], "right": right["manifest"]["run_id"]}


def _forbidden_capture_field(value: Any, path: str = "capture") -> str | None:
    """Name the first secret-like source value before it reaches a replay."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if (
                FORBIDDEN_CONTENT.search(key)
                and isinstance(child, str)
                and child.strip()
            ):
                return child_path
            found = _forbidden_capture_field(child, child_path)
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _forbidden_capture_field(child, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(value, str) and FORBIDDEN_CONTENT.search(value):
        return path
    return None


def _grade_index(grade: dict[str, Any], capture_run_id: str) -> dict[tuple[str, int, int], dict[str, Any]]:
    if grade.get("run_id") != capture_run_id:
        raise ValueError("Grade report run_id does not match the capture manifest")
    scenarios = grade.get("scenarios")
    if not isinstance(scenarios, dict):
        raise ValueError("Grade report must contain a scenarios object")
    indexed: dict[tuple[str, int, int], dict[str, Any]] = {}
    for scenario_id, entries in scenarios.items():
        if not isinstance(entries, list):
            raise ValueError(f"Grade report scenario {scenario_id} must contain a list")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("repeat"), int) or not isinstance(entry.get("turn"), int):
                continue
            key = (scenario_id, entry["repeat"], entry["turn"])
            if key in indexed:
                raise ValueError(f"Grade report has duplicate evidence for {scenario_id} r{entry['repeat']} t{entry['turn']}")
            indexed[key] = entry
    return indexed


def _expected_execution_accuracy(
    grade: dict[str, Any], scenario: dict[str, Any], label: str
) -> str:
    for check in grade.get("checks", []):
        if not isinstance(check, dict) or check.get("name") != "execution_accuracy":
            continue
        match = re.fullmatch(
            r"execution accuracy (?:is )?(PASS|FAIL|EXEMPT)",
            str(check.get("detail", "")),
        )
        if match and check.get("passed") is (match.group(1) != "FAIL"):
            return match.group(1)
    if scenario.get("execution_accuracy_exempt"):
        return "EXEMPT"
    raise ValueError(
        f"Grade report has a non-replayable execution-accuracy result for {label}; "
        "it must declare PASS, FAIL, or EXEMPT"
    )


def freeze_capture(capture_path: Path, grade_path: Path, output: Path) -> dict[str, Any]:
    """Project completed capture evidence into the narrow, committed replay format."""
    # Importing the replay runner also imports its deterministic grader, which
    # reads runtime settings. Native capture imports must stay independent of
    # that path so they can bind the fixture environment before configuration.
    from evals.replay import REPLAY_SCHEMA_VERSION, validate_replay

    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing replay: {output}")

    capture = load_run(capture_path)
    forbidden = _forbidden_capture_field(capture)
    if forbidden:
        raise ValueError(f"Capture contains forbidden content at {forbidden}")

    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    if not isinstance(grade, dict):
        raise ValueError(f"{grade_path} is not a grader report")
    run_id = capture["manifest"].get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("Capture manifest must contain a run_id")
    prompt_version = capture["manifest"].get("prompt_version")
    if not isinstance(prompt_version, str) or not prompt_version.strip():
        raise ValueError(
            "Capture manifest must contain a prompt_version; a capture recorded before "
            "T0035.1 cannot be frozen without stamping the version it actually ran"
        )
    grades = _grade_index(grade, run_id)
    scenarios_by_id = {scenario["id"]: scenario for scenario in load_scenarios()}

    replay: dict[str, Any] = {
        "manifest": {
            "run_id": run_id,
            "schema_version": REPLAY_SCHEMA_VERSION,
            "source_capture": capture_path.name,
            "sanitized": True,
            "prompt_version": prompt_version.strip(),
        },
        "status": "COMPLETE",
        "scenarios": {},
    }
    for scenario_id, record in capture.get("scenarios", {}).items():
        scenario = scenarios_by_id.get(scenario_id)
        if scenario is None:
            raise ValueError(f"Capture contains unknown scenario id: {scenario_id}")
        capture_repeats = record.get("repeats", [])
        if record.get("status") in {"UNRUN", "INFRA"} and not any(
            repeat.get("turns") for repeat in capture_repeats if isinstance(repeat, dict)
        ):
            continue
        if record.get("status") != "COMPLETE":
            raise ValueError(f"Capture scenario {scenario_id} is not COMPLETE")
        frozen_repeats: list[dict[str, Any]] = []
        for repeat in capture_repeats:
            repeat_number = repeat.get("repeat")
            if not isinstance(repeat_number, int) or repeat.get("status") != "COMPLETE":
                raise ValueError(f"Capture scenario {scenario_id} has an incomplete repeat")
            turns: list[dict[str, Any]] = []
            for turn_number, turn in enumerate(repeat.get("turns", []), start=1):
                label = f"{scenario_id} r{repeat_number} t{turn_number}"
                if turn.get("status") != "COMPLETE":
                    raise ValueError(f"Capture turn {label} is not COMPLETE")
                grade_entry = grades.get((scenario_id, repeat_number, turn_number))
                if grade_entry is None:
                    raise ValueError(f"Grade report has no evidence for {label}")
                if grade_entry.get("status") not in {"PASS", "FAIL"}:
                    raise ValueError(f"Grade report has an unusable verdict for {label}")
                seams = turn.get("seams")
                if not isinstance(seams, dict):
                    raise ValueError(f"Capture turn {label} has no seam evidence")
                turns.append(
                    {
                        "turn": turn_number,
                        "status": "COMPLETE",
                        "expected_execution_accuracy": _expected_execution_accuracy(
                            grade_entry, scenario, label
                        ),
                        "expected_grade": grade_entry["status"],
                        "seams": {key: seams.get(key) for key in ("question", "answer", "tools_called", "sql_text")},
                    }
                )
            frozen_repeats.append({"repeat": repeat_number, "status": "COMPLETE", "turns": turns})
        replay["scenarios"][scenario_id] = {
            "scenario_type": scenario["type"],
            "status": "COMPLETE",
            "repeats": frozen_repeats,
        }

    validate_replay(replay)
    _write_json(output, replay)
    return replay


def _is_quota_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("429", "rate limit", "rate_limit", "quota", "tpm", "tokens per minute"))


def _parse_retry_hint(message: str) -> float | None:
    """Read the wait the provider itself asked for, e.g. 'Please try again in 14.16s'."""
    match = _RETRY_HINT_PATTERN.search(message)
    if match is None:
        return None
    value = float(match.group(1))
    return value / 1000 if match.group(2).lower() == "ms" else value


def _retry_delay(exc: BaseException, attempt: int) -> float:
    """Pick the wait before retry `attempt` (0-based), preferring the provider's own hint."""
    hint = _parse_retry_hint(str(exc))
    if hint is not None:
        return min(hint + RETRY_HINT_MARGIN_SECONDS, MAX_BACKOFF_SECONDS)
    ladder = QUOTA_BACKOFF_SECONDS if _is_quota_error(exc) else DEFAULT_BACKOFF_SECONDS
    return ladder[min(attempt, len(ladder) - 1)]


def _seam_dict(run: harness.SeamRun) -> dict[str, Any]:
    return {
        "question": run.question,
        "answer": run.answer,
        "tools_called": run.tools_called,
        "tool_output": run.tool_output,
        "sql_text": run.sql_text,
        "trace_id": run.trace_id,
    }


async def _capture_case(
    case: dict[str, Any], pause: Callable[[], Awaitable[None]] | None = None
) -> list[harness.SeamRun]:
    with _native_provider_environment():
        if case["type"] == "single":
            return [await harness.run_single_turn_case(case)]
        runs, _ = await harness.run_conversational_case(case, pause=pause)
        return runs


async def _capture_with_retry(
    case: dict[str, Any],
    manifest: dict[str, Any],
    repeat_index: int,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    pause: Callable[[], Awaitable[None]] | None = None,
) -> list[harness.SeamRun]:
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await _capture_case(case, pause=pause)
        except Exception as exc:  # noqa: BLE001 - persisted as infrastructure evidence
            if attempt >= MAX_RETRIES:
                raise
            delay = _retry_delay(exc, attempt)
            manifest["retry_events"].append(
                {"scenario_id": case["id"], "repeat": repeat_index, "attempt": attempt + 1, "error": str(exc), "at": _utc_now(), "delay_seconds": delay}
            )
            await sleep(delay)
    raise AssertionError("unreachable")


def _score_case(case: dict[str, Any], runs: list[harness.SeamRun]) -> dict[str, Any]:
    final = runs[-1]
    result: dict[str, Any] = {
        "seam1_routing": harness.score(harness.seam1_metrics(), harness.build_seam1_case(case, final)),
        "seam3_synthesis": harness.score(harness.seam3_metrics(), harness.build_seam3_case(case, final)),
    }
    seam2 = harness.build_seam2_case(final)
    if seam2 is not None:
        result["seam2_nl_to_sql"] = harness.score(harness.seam2_metrics(), seam2)
    return result


async def run(
    scenarios: list[dict[str, Any]],
    output: Path,
    capture_only: bool = True,
    resume: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    pacing_seconds: float | None = None,
) -> dict[str, Any]:
    artifact = load_run(output) if resume and output.exists() else _new_run(build_manifest())
    manifest = artifact["manifest"]
    if not resume and output.exists():
        raise FileExistsError(f"Refusing to overwrite existing run: {output}")

    pacing = load_turn_pacing_seconds() if pacing_seconds is None else pacing_seconds
    spent_a_window = False

    async def pause() -> None:
        if pacing:
            await sleep(pacing)

    for scenario_index, case in enumerate(scenarios):
        scenario_id = case["id"]
        record = artifact["scenarios"].setdefault(scenario_id, {"status": "UNRUN", "repeats": []})
        needed = repeat_count(case)
        if record["status"] == "COMPLETE" and len(record["repeats"]) >= needed:
            continue
        completed_repeats = [item for item in record["repeats"] if item["status"] == "COMPLETE"]
        record["repeats"] = completed_repeats
        for repeat_index in range(len(completed_repeats), needed):
            repeat_record: dict[str, Any] = {"repeat": repeat_index + 1, "status": "RUNNING", "turns": []}
            record["repeats"].append(repeat_record)
            artifact["checkpoint"] = {"scenario_id": scenario_id, "scenario_index": scenario_index, "repeat": repeat_index + 1}
            _write_json(output, artifact)
            try:
                if spent_a_window:
                    await pause()
                spent_a_window = True
                runs = await _capture_with_retry(
                    case, manifest, repeat_index + 1, sleep=sleep, pause=pause
                )
                for turn_index, seam in enumerate(runs):
                    repeat_record["turns"].append(
                        {
                            "turn": turn_index + 1,
                            "status": "COMPLETE",
                            "seams": _seam_dict(seam),
                            "telemetry": seam.telemetry,
                        }
                    )
                    artifact["checkpoint"]["turn"] = turn_index + 1
                    _write_json(output, artifact)
                if not capture_only:
                    repeat_record["scores"] = _score_case(case, runs)
                repeat_record["status"] = "COMPLETE"
            except Exception as exc:  # noqa: BLE001 - preserve partial runs
                repeat_record["status"] = "INFRA"
                repeat_record["error"] = str(exc)
                if _is_quota_error(exc):
                    artifact["status"] = "PARTIAL_QUOTA"
                    _mark_unrun(artifact, scenarios, scenario_index, scenario_id)
                    _write_json(output, artifact)
                    return artifact
            _write_json(output, artifact)
        record["status"] = "COMPLETE" if len(record["repeats"]) >= needed and all(r["status"] == "COMPLETE" for r in record["repeats"]) else "INFRA"
        _write_json(output, artifact)

    artifact["status"] = "COMPLETE"
    manifest["finished_at"] = _utc_now()
    _write_json(output, artifact)
    return artifact


def _mark_unrun(artifact: dict[str, Any], scenarios: list[dict[str, Any]], index: int, current_id: str) -> None:
    for case in scenarios[index + 1 :]:
        artifact["scenarios"].setdefault(case["id"], {"status": "UNRUN", "repeats": []})
    artifact["scenarios"][current_id]["status"] = "INFRA"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run evaluation scenarios over the in-process harness.")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT / "run.json")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--score", action="store_true", help="Run the judge after each captured repeat.")
    parser.add_argument("--ids", help="Comma-separated scenario IDs to run.")
    parser.add_argument("--grade", type=Path, help="Deterministic grader report for freeze.")
    parser.add_argument("command", nargs="?", choices=("run", "diff", "freeze"), default="run")
    parser.add_argument("other", nargs="?", type=Path, help="Second run artifact for diff, or capture artifact for freeze.")
    args = parser.parse_args(argv)
    if args.command == "diff":
        if args.other is None:
            parser.error("diff requires a second run artifact")
        print(json.dumps(compare_runs(args.output, args.other), indent=2))
        return
    if args.command == "freeze":
        if args.other is None:
            parser.error("freeze requires a capture artifact")
        if args.grade is None:
            parser.error("freeze requires --grade <grade.json>")
        freeze_capture(args.other, args.grade, args.output)
        return
    scenarios = load_scenarios()
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        scenarios = [case for case in scenarios if case["id"] in wanted]
    if not scenarios:
        parser.error("No scenarios selected")
    asyncio.run(run(scenarios, args.output, capture_only=not args.score, resume=args.resume))


if __name__ == "__main__":
    main()
