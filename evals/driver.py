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


def _fixture_database_url() -> str:
    settings_path = ROOT / "config" / "settings.yaml"
    settings = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    try:
        database_url = settings["eval"]["fixture"]["database_url"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Missing eval.fixture.database_url in config/settings.yaml") from exc
    if not isinstance(database_url, str) or not database_url.strip():
        raise RuntimeError("Missing or empty eval.fixture.database_url in config/settings.yaml")
    return database_url


def _bind_fixture_environment() -> None:
    """Bind native driver runs before any src module can freeze Settings()."""
    os.environ["DATABASE_URL"] = _fixture_database_url()
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
    settings = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    agent = settings["agent"]
    database_hash, database_name, database_row_count = _database_fingerprint(
        _fixture_database_url()
    )
    return {
        "run_id": str(uuid.uuid4()),
        "started_at": _utc_now(),
        "finished_at": None,
        "git_sha": _git_sha(),
        "fixture_hash": database_hash,
        "fixture_seed_hash": _sha256(fixture_path),
        "database_name": database_name,
        "database_row_count": database_row_count,
        "prompt_hash": _sha256(prompts_path),
        "config_hash": _sha256(settings_path),
        "models": {
            "react": agent["react"]["model"],
            "sql_generation": agent["sql_generation"]["model"],
        },
        "sampling": {
            "react": {
                key: agent["react"].get(key)
                for key in ("temperature", "max_tokens", "reasoning_effort", "reasoning_format")
            },
            "sql_generation": {
                key: agent["sql_generation"].get(key)
                for key in ("temperature", "max_tokens", "reasoning_effort", "reasoning_format")
            },
        },
        "retry_policy": {
            "max_retries_per_turn": MAX_RETRIES,
            "backoff_seconds": list(DEFAULT_BACKOFF_SECONDS),
            "quota_backoff_seconds": list(QUOTA_BACKOFF_SECONDS),
            "max_backoff_seconds": MAX_BACKOFF_SECONDS,
            "honors_provider_retry_hint": True,
            "provider_sdk_max_retries": SDK_MAX_RETRIES,
        },
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
    fields = (
        "fixture_hash",
        "database_name",
        "database_row_count",
        "prompt_hash",
        "config_hash",
    )
    differences = [field for field in fields if left["manifest"].get(field) != right["manifest"].get(field)]
    if differences:
        raise ValueError("Runs are incomparable: " + ", ".join(differences) + " differ")


def compare_runs(left_path: Path, right_path: Path) -> dict[str, Any]:
    left = load_run(left_path)
    right = load_run(right_path)
    _assert_comparable(left, right)
    return {"comparable": True, "left": left["manifest"]["run_id"], "right": right["manifest"]["run_id"]}


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


async def _capture_case(case: dict[str, Any]) -> list[harness.SeamRun]:
    with _native_provider_environment():
        if case["type"] == "single":
            return [await harness.run_single_turn_case(case)]
        runs, _ = await harness.run_conversational_case(case)
        return runs


async def _capture_with_retry(
    case: dict[str, Any], manifest: dict[str, Any], repeat_index: int, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
) -> list[harness.SeamRun]:
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await _capture_case(case)
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
) -> dict[str, Any]:
    artifact = load_run(output) if resume and output.exists() else _new_run(build_manifest())
    manifest = artifact["manifest"]
    if not resume and output.exists():
        raise FileExistsError(f"Refusing to overwrite existing run: {output}")

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
                runs = await _capture_with_retry(case, manifest, repeat_index + 1, sleep=sleep)
                for turn_index, seam in enumerate(runs):
                    repeat_record["turns"].append({"turn": turn_index + 1, "status": "COMPLETE", "seams": _seam_dict(seam)})
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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "run.json")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--score", action="store_true", help="Run the judge after each captured repeat.")
    parser.add_argument("--ids", help="Comma-separated scenario IDs to run.")
    parser.add_argument("command", nargs="?", choices=("run", "diff"), default="run")
    parser.add_argument("other", nargs="?", type=Path, help="Second run artifact for diff.")
    args = parser.parse_args(argv)
    if args.command == "diff":
        if args.other is None:
            parser.error("diff requires a second run artifact")
        print(json.dumps(compare_runs(args.output, args.other), indent=2))
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
