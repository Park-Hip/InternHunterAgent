"""Run the committed, no-model evaluation replay against the frozen fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evals.execution_accuracy import grade_run
from evals.grader import grade_persisted_run
from evals.scenarios import load_scenarios
from evals.sanitization import FORBIDDEN_CONTENT as _FORBIDDEN_CONTENT

REPLAY_PATH = Path(__file__).with_name("replays") / "t0039.3-deepseek-v4.json"

# 2 (T0035.1) added prompt_version. The bump is checked rather than tolerated: a
# schema_version 1 artifact predates the lineage stamp, so accepting it would let an
# unlabelled replay pass as a labelled one - the silent invalidation M35 exists to stop.
REPLAY_SCHEMA_VERSION = 2
_MANIFEST_KEYS = {"run_id", "schema_version", "source_capture", "sanitized", "prompt_version"}
_SCENARIO_KEYS = {"scenario_type", "status", "repeats"}
_REPEAT_KEYS = {"repeat", "status", "turns"}
_TURN_KEYS = {
    "turn",
    "status",
    "seams",
    "expected_execution_accuracy",
    "expected_grade",
}
_SEAM_KEYS = {"question", "answer", "tools_called", "sql_text"}
def load_replay(path: Path = REPLAY_PATH) -> dict[str, Any]:
    """Load the committed replay artifact as UTF-8 JSON."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _assert_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    unexpected = set(value) - expected
    missing = expected - set(value)
    if unexpected or missing:
        raise ValueError(
            f"{label} keys differ: missing={sorted(missing)}, unexpected={sorted(unexpected)}"
        )


def validate_replay(replay: dict[str, Any]) -> None:
    """Validate the narrow replay schema and reject un-sanitized trace fields."""
    _assert_keys(replay, {"manifest", "status", "scenarios"}, "replay")
    manifest = replay["manifest"]
    if not isinstance(manifest, dict):
        raise ValueError("Replay manifest must be an object")
    _assert_keys(manifest, _MANIFEST_KEYS, "replay manifest")
    if not (
        isinstance(manifest["run_id"], str)
        and isinstance(manifest["schema_version"], int)
        and isinstance(manifest["source_capture"], str)
        and manifest["sanitized"] is True
        and isinstance(manifest["prompt_version"], str)
        and manifest["prompt_version"].strip()
    ):
        raise ValueError("Replay manifest has invalid provenance fields")
    if manifest["schema_version"] != REPLAY_SCHEMA_VERSION:
        raise ValueError(
            f"Replay schema_version is {manifest['schema_version']}, "
            f"expected {REPLAY_SCHEMA_VERSION}"
        )
    if replay["status"] != "COMPLETE":
        raise ValueError("Replay status must be COMPLETE")
    if _FORBIDDEN_CONTENT.search(json.dumps(replay)):
        raise ValueError("Replay contains a credential or live trace identifier")

    scenarios = replay["scenarios"]
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError("Replay must contain at least one scenario")
    registry = {scenario["id"]: scenario for scenario in load_scenarios()}
    for scenario_id, scenario_record in scenarios.items():
        scenario = registry.get(scenario_id)
        if scenario is None:
            raise ValueError(f"Replay contains unknown scenario id: {scenario_id}")
        if not isinstance(scenario_record, dict):
            raise ValueError(f"Replay scenario {scenario_id} must be an object")
        _assert_keys(scenario_record, _SCENARIO_KEYS, f"Replay scenario {scenario_id}")
        if scenario_record["scenario_type"] != scenario["type"]:
            raise ValueError(
                f"Replay scenario {scenario_id} has an invalid scenario_type"
            )
        if scenario_record["status"] != "COMPLETE":
            raise ValueError(f"Replay scenario {scenario_id} must be COMPLETE")
        repeats = scenario_record["repeats"]
        if not isinstance(repeats, list) or not repeats:
            raise ValueError(
                f"Replay scenario {scenario_id} must contain completed repeats"
            )
        for repeat in repeats:
            if not isinstance(repeat, dict):
                raise ValueError(
                    f"Replay scenario {scenario_id} repeat must be an object"
                )
            _assert_keys(repeat, _REPEAT_KEYS, f"Replay scenario {scenario_id} repeat")
            if not isinstance(repeat["repeat"], int) or repeat["status"] != "COMPLETE":
                raise ValueError(f"Replay scenario {scenario_id} repeat is invalid")
            turns = repeat["turns"]
            expected_turns = len(scenario.get("turns", [scenario.get("input")]))
            if not isinstance(turns, list) or len(turns) != expected_turns:
                raise ValueError(
                    f"Replay scenario {scenario_id} has an invalid turn count"
                )
            questions = scenario.get("turns") or [scenario["input"]]
            for turn_index, turn in enumerate(turns, start=1):
                if not isinstance(turn, dict):
                    raise ValueError(
                        f"Replay scenario {scenario_id} turn must be an object"
                    )
                _assert_keys(turn, _TURN_KEYS, f"Replay scenario {scenario_id} turn")
                if turn["turn"] != turn_index or turn["status"] != "COMPLETE":
                    raise ValueError(f"Replay scenario {scenario_id} turn is invalid")
                if turn["expected_execution_accuracy"] not in {"PASS", "FAIL", "EXEMPT"}:
                    raise ValueError(
                        f"Replay scenario {scenario_id} has an invalid expected execution status"
                    )
                if turn["expected_grade"] not in {"PASS", "FAIL"}:
                    raise ValueError(
                        f"Replay scenario {scenario_id} has an invalid expected grade"
                    )
                seams = turn["seams"]
                if not isinstance(seams, dict):
                    raise ValueError(
                        f"Replay scenario {scenario_id} seams must be an object"
                    )
                _assert_keys(seams, _SEAM_KEYS, f"Replay scenario {scenario_id} seams")
                if not all(
                    isinstance(seams[key], expected)
                    for key, expected in (
                        ("question", str),
                        ("answer", str),
                        ("tools_called", list),
                    )
                ):
                    raise ValueError(
                        f"Replay scenario {scenario_id} seams have invalid values"
                    )
                if seams["sql_text"] is not None and not isinstance(
                    seams["sql_text"], str
                ):
                    raise ValueError(
                        f"Replay scenario {scenario_id} SQL must be a string or null"
                    )
                # Without this the replay could keep passing against a question
                # the registry no longer asks, which is exactly the drift the
                # gate exists to catch.
                if seams["question"] != questions[turn_index - 1]:
                    raise ValueError(
                        f"Replay scenario {scenario_id} turn {turn_index} question "
                        "does not match the frozen registry"
                    )


def _assert_expected_outcomes(
    replay: dict[str, Any],
    execution_accuracy: dict[str, Any],
    grades: dict[str, Any],
) -> None:
    """Fail the gate when a recorded SQL or deterministic-grade outcome drifts."""
    mismatches: list[str] = []
    for scenario_id, scenario_record in replay["scenarios"].items():
        execution_repeats = execution_accuracy["scenarios"][scenario_id]
        grade_turns = grades["scenarios"][scenario_id]
        for repeat_index, repeat in enumerate(scenario_record["repeats"]):
            if repeat_index >= len(execution_repeats):
                mismatches.append(
                    f"{scenario_id} r{repeat['repeat']} execution repeat is missing"
                )
                continue
            execution_turns = execution_repeats[repeat_index]["turns"]
            for turn_index, turn in enumerate(repeat["turns"]):
                if turn_index >= len(execution_turns):
                    mismatches.append(
                        f"{scenario_id} r{repeat['repeat']} t{turn['turn']} execution turn is missing"
                    )
                    continue
                execution_status = execution_turns[turn_index]["status"]
                if execution_status != turn["expected_execution_accuracy"]:
                    mismatches.append(
                        f"{scenario_id} r{repeat['repeat']} t{turn['turn']} execution "
                        f"expected {turn['expected_execution_accuracy']}, got {execution_status}"
                    )
                grade = next(
                    (
                        item
                        for item in grade_turns
                        if item["repeat"] == repeat["repeat"]
                        and item["turn"] == turn["turn"]
                    ),
                    None,
                )
                if grade is None:
                    mismatches.append(
                        f"{scenario_id} r{repeat['repeat']} t{turn['turn']} grade is missing"
                    )
                    continue
                if grade["status"] != turn["expected_grade"]:
                    mismatches.append(
                        f"{scenario_id} r{repeat['repeat']} t{turn['turn']} grade "
                        f"expected {turn['expected_grade']}, got {grade['status']}"
                    )
    if mismatches:
        raise ValueError("Replay outcome mismatch: " + "; ".join(mismatches))


def run_replay(
    path: Path = REPLAY_PATH, database_url: str | None = None
) -> dict[str, Any]:
    """Validate, execute, and grade the committed replay without a provider call."""
    replay = load_replay(path)
    validate_replay(replay)
    execution_accuracy = grade_run(replay, database_url)
    grades = grade_persisted_run(replay, execution_accuracy)
    _assert_expected_outcomes(replay, execution_accuracy, grades)
    return {"execution_accuracy": execution_accuracy, "grades": grades}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Replay committed evaluation evidence without model or judge calls."
    )
    parser.add_argument("--replay", type=Path, default=REPLAY_PATH)
    parser.add_argument("--database-url")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            run_replay(args.replay, args.database_url),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
