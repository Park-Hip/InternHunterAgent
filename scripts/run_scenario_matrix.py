from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.runtime.prompts import load_prompt_version
from src.core.config import settings

SCENARIOS_PATH = ROOT / "evals" / "scenarios_v1.yaml"
REPORT_PATH = ROOT / "evals" / "v1_scenario_matrix.md"
CHECKPOINT_PATH = ROOT / "evals" / "v1_scenario_matrix.observed.json"
CHAT_URL = "http://127.0.0.1:8000/api/v1/agent/chat"
PENDING_LIVE_RUN = "_pending live run_"
THROWAWAY_QUERY = "How many jobs are there?"
DEFAULT_SLEEP_SECONDS = 1.5
TURN_TIMEOUT_SECONDS = 240.0


def load_scenarios(path: Path = SCENARIOS_PATH) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        scenarios = yaml.safe_load(handle)
    if not isinstance(scenarios, list):
        raise ValueError("evals/scenarios_v1.yaml must contain a top-level list.")
    return scenarios


def repeat_count(scenario: dict[str, Any]) -> int:
    return 3 if scenario["probe"] else 2


def run_date_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_checkpoint(path: Path = CHECKPOINT_PATH) -> dict[str, list[str]]:
    """Reload previously collected answers so a run can resume across a Groq
    daily-quota reset instead of restarting the whole ~78-turn pass."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object of {{id: [answers]}}.")
    return data


def save_checkpoint(observed: dict[str, list[str]], path: Path = CHECKPOINT_PATH) -> None:
    path.write_text(json.dumps(observed, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_scenarios(
    scenarios: list[dict[str, Any]],
    ids: str | None = None,
    probes_only: bool = False,
) -> list[dict[str, Any]]:
    result = scenarios
    if probes_only:
        result = [scenario for scenario in result if scenario["probe"]]
    if ids:
        wanted = {token.strip() for token in ids.split(",") if token.strip()}
        result = [scenario for scenario in result if scenario["id"] in wanted]
    return result


def scenario_section(scenario_id: str) -> str:
    if scenario_id.startswith("M-D"):
        return "4c. Decision-specific probe scenarios"
    if scenario_id.startswith("M-"):
        return "4b. Coverage-gap scenarios"
    return "4a. Golden-anchored scenarios"


def scenario_category(scenario_id: str) -> str:
    return "M" if scenario_id.startswith("M-") else scenario_id[:1]


def prompt_version() -> str:
    return load_prompt_version()


def model_id() -> str:
    return settings.config_yaml["agent"]["groq"]["model"]


def temperature() -> Any:
    return settings.config_yaml["agent"]["groq"]["temperature"]


def fixture_dsn() -> str:
    return settings.config_yaml["eval"]["fixture"]["database_url"]


def report_header(run_date: str, version: str) -> str:
    return "\n".join(
        [
            "# v1 Scenario Matrix",
            "",
            "Template - Observed/Pass are filled by the live run per docs/Manual_Verification_Guide.md -> T0015.4. Do not hand-fill from imagination.",
            "",
            f"- prompt_version: `{version}`",
            f"- model: `{model_id()}`",
            f"- temperature: `{temperature()}`",
            f"- run_date_utc: `{run_date}`",
            f"- fixture_seed_confirmation: User confirms `COUNT(*) = 22` from `python -m evals.fixtures.loader` against `{fixture_dsn()}`",
            "",
        ]
    )


def format_input_cell(scenario: dict[str, Any]) -> str:
    if scenario["type"] == "conversational":
        return "<br>".join(
            f"Turn {index}: {escape_markdown(str(turn))}"
            for index, turn in enumerate(scenario["turns"], start=1)
        )
    return escape_markdown(str(scenario["input"]))


def format_observed_cell(observed_runs: list[str] | None) -> str:
    if observed_runs is None:
        return PENDING_LIVE_RUN
    return "<br>".join(
        f"r{index}: {escape_markdown(answer)}"
        for index, answer in enumerate(observed_runs, start=1)
    )


def escape_markdown(value: str) -> str:
    normalized = " ".join(value.strip().split())
    return normalized.replace("|", "\\|")


def build_report(
    scenarios: list[dict[str, Any]],
    observed: dict[str, list[str]] | None,
    run_date: str,
    version: str,
) -> str:
    lines: list[str] = [report_header(run_date, version)]
    current_section: str | None = None
    table_header = [
        "| ID | Category | Input / turns | Expected behavior | Observed (r1 / r2 / r3) | Pass? (N/N) | Prompt lever if fail |",
        "|---|---|---|---|---|---|---|",
    ]

    for scenario in scenarios:
        section = scenario_section(scenario["id"])
        if section != current_section:
            if current_section is not None:
                lines.append("")
            lines.append(f"## {section}")
            lines.extend(table_header)
            current_section = section
        observed_runs = None if observed is None else observed.get(scenario["id"], [])
        row = [
            scenario["id"],
            scenario_category(scenario["id"]),
            format_input_cell(scenario),
            escape_markdown(str(scenario["expected"])),
            format_observed_cell(observed_runs if observed_runs else None),
            "",
            "",
        ]
        lines.append(f"| {' | '.join(row)} |")

    lines.extend(
        [
            "",
            "## Failures -> prompt levers (fill after grading)",
            "",
            "- _Fill after the live run and manual grading._",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(markdown: str, path: Path = REPORT_PATH) -> None:
    path.write_text(markdown, encoding="utf-8")


def run_template(path: Path = REPORT_PATH) -> None:
    scenarios = load_scenarios()
    run_date = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write_report(build_report(scenarios, observed=None, run_date=run_date, version=prompt_version()), path)


def assert_live_prompt_version() -> str:
    version = prompt_version()
    if version != "v1":
        raise SystemExit(
            f"Aborting live scenario run: expected prompt_version 'v1', got '{version}'."
        )
    return version


def _post_payload_httpx(payload: dict[str, Any]) -> dict[str, Any]:
    assert httpx is not None
    # Long timeout: on the Groq free tier a single turn can sit through several
    # server-side 429/TPM retry backoffs (8000 tokens/min cap) before it lands.
    with httpx.Client(timeout=TURN_TIMEOUT_SECONDS) as client:
        response = client.post(CHAT_URL, json=payload)
        response.raise_for_status()
        return response.json()


def _post_payload_urllib(payload: dict[str, Any]) -> dict[str, Any]:
    from urllib import request

    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        CHAT_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=60.0) as response:
        return json.loads(response.read().decode("utf-8"))


def post_turn(query: str, session_id: str | None) -> dict[str, Any]:
    payload = {"query": query, "session_id": session_id}
    if httpx is not None:
        return _post_payload_httpx(payload)
    return _post_payload_urllib(payload)


def run_preflight() -> None:
    response = post_turn(THROWAWAY_QUERY, str(uuid.uuid4()))
    if not str(response.get("answer", "")).strip():
        raise SystemExit("Aborting live scenario run: preflight query returned an empty answer.")


def run_live(
    scenarios: list[dict[str, Any]],
    sleep_s: float,
    version: str,
) -> dict[str, list[str]]:
    """Collect answers, checkpointing after every scenario so a mid-run failure
    (rate spike or daily-quota exhaustion) never loses completed work. Already
    complete scenarios in the checkpoint are skipped so a re-run resumes."""
    observed = load_checkpoint()
    all_scenarios = load_scenarios()
    total = len(scenarios)
    failed: list[str] = []
    for index, scenario in enumerate(scenarios, start=1):
        scenario_id = scenario["id"]
        needed = repeat_count(scenario)
        if len(observed.get(scenario_id, [])) >= needed:
            print(f"[{index}/{total}] {scenario_id}: complete ({needed}/{needed}) - skipping")
            continue

        print(f"[{index}/{total}] {scenario_id}: running {needed}x ...", flush=True)
        try:
            answers: list[str] = []
            for _ in range(needed):
                run_session_id = str(uuid.uuid4())
                if scenario["type"] == "conversational":
                    answer = run_conversational_scenario(scenario["turns"], run_session_id, sleep_s)
                else:
                    answer = run_single_turn_scenario(str(scenario["input"]), run_session_id)
                answers.append(answer)
                if sleep_s:
                    time.sleep(sleep_s)
        except Exception as exc:  # noqa: BLE001 - one bad turn must not abort the pass
            # Leave the scenario out of the checkpoint so it stays pending and is
            # retried on the next run (likely a transient Groq TPM 429).
            failed.append(scenario_id)
            print(f"    ! {scenario_id} failed ({type(exc).__name__}: {exc}); left pending", flush=True)
            if sleep_s:
                time.sleep(sleep_s)
            continue

        observed[scenario_id] = answers
        save_checkpoint(observed)
        write_report(build_report(all_scenarios, observed, run_date_now(), version))

    if failed:
        print(f"Incomplete ({len(failed)}): {', '.join(failed)} - re-run to resume.", flush=True)
    return observed


def run_single_turn_scenario(user_input: str, session_id: str) -> str:
    response = post_turn(user_input, session_id)
    return str(response.get("answer", "")).strip()


def run_conversational_scenario(turns: list[str], session_id: str, sleep_s: float = 0.0) -> str:
    final_answer = ""
    active_session_id = session_id
    for turn_index, turn in enumerate(turns):
        if turn_index and sleep_s:
            time.sleep(sleep_s)
        response = post_turn(turn, active_session_id)
        final_answer = str(response.get("answer", "")).strip()
        active_session_id = str(response.get("session_id") or active_session_id)
    return final_answer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect observed agent answers for the frozen v1 manual scenario matrix."
    )
    parser.add_argument(
        "--template",
        "--no-run",
        action="store_true",
        dest="template",
        help="Write the blank report template without making any HTTP calls.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Seconds to pause between turns (RPM guard for the Groq free tier).",
    )
    parser.add_argument(
        "--probes-only",
        action="store_true",
        help="Run only the 15 honesty/safety probes (each 3x).",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated scenario ids to run (e.g. 'C2,C5,M-G44').",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.template:
        run_template()
        return

    version = assert_live_prompt_version()
    run_preflight()
    scenarios = filter_scenarios(load_scenarios(), ids=args.ids, probes_only=args.probes_only)
    if not scenarios:
        raise SystemExit("No scenarios matched the given --ids / --probes-only filter.")
    try:
        observed = run_live(scenarios, sleep_s=args.sleep, version=version)
    except Exception as exc:  # noqa: BLE001 - preserve partial progress, then surface
        raise SystemExit(
            f"Run interrupted ({exc}). Progress is checkpointed in "
            f"{CHECKPOINT_PATH.name}; re-run the same command to resume."
        ) from exc
    write_report(build_report(load_scenarios(), observed=observed, run_date=run_date_now(), version=version))
    print(f"Done. Report: {REPORT_PATH.name}  Checkpoint: {CHECKPOINT_PATH.name}")


if __name__ == "__main__":
    main()
