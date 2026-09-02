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

REPLAY_PATH = Path(__file__).with_name("replays") / "t0025.9-committed.json"
ACTIVE_REPLAY_DIR = REPLAY_PATH.parent
# Historical captures preserved under evals/archive/replays/ (issue #148/#249).
# They keep their original bytes and provenance but are no longer current
# regression evidence: the registry moved on, so they no longer validate.
ARCHIVED_REPLAY_NAMES = frozenset(
    {
        "t0024.4-v3-obligations.json",
        "t0025.7-acceptance.json",
        "v6-baseline-20260823.json",
    }
)

# Schema versions 2 and 3 preserve the legacy file-wide prompt_version. Version 4
# records independently versioned surfaces. Historical artifacts keep their bytes and
# can still be replayed, but cannot be compared to named lineage one surface at a time.
REPLAY_SCHEMA_VERSION = 4
_LEGACY_REPLAY_SCHEMA_VERSIONS = frozenset({2, 3})
_SUPPORTED_REPLAY_SCHEMA_VERSIONS = frozenset(
    {*_LEGACY_REPLAY_SCHEMA_VERSIONS, REPLAY_SCHEMA_VERSION}
)
_PROMPT_SURFACES = frozenset({"system", "schema_context", "sql_generation"})
_LEGACY_MANIFEST_KEYS = {
    "run_id",
    "schema_version",
    "source_capture",
    "sanitized",
    "prompt_version",
}
_NAMED_MANIFEST_KEYS = {
    "run_id",
    "schema_version",
    "source_capture",
    "sanitized",
    "prompt_versions",
}
_SCENARIO_KEYS = {"scenario_type", "status", "repeats"}
_REPEAT_KEYS = {"repeat", "status", "turns"}
_TURN_KEYS = {
    "turn",
    "status",
    "seams",
    "expected_execution_accuracy",
    "expected_grade",
}
_V2_SEAM_KEYS = {"question", "answer", "tools_called", "sql_text"}
_V3_SEAM_KEYS = {*_V2_SEAM_KEYS, "tool_output", "tool_arguments"}
def active_replay_paths(directory: Path = ACTIVE_REPLAY_DIR) -> list[Path]:
    """Discover every active replay artifact, in deterministic sorted order.

    The active replay directory is the contract for current regression
    evidence: CI iterates it rather than defaulting to one path so a stale or
    newly added artifact can never be silently skipped.
    """
    return sorted(directory.glob("*.json"))


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
    schema_version = manifest.get("schema_version")
    manifest_keys = (
        _NAMED_MANIFEST_KEYS
        if schema_version == REPLAY_SCHEMA_VERSION
        else _LEGACY_MANIFEST_KEYS
    )
    _assert_keys(manifest, manifest_keys, "replay manifest")
    if not (
        isinstance(manifest["run_id"], str)
        and isinstance(schema_version, int)
        and isinstance(manifest["source_capture"], str)
        and manifest["sanitized"] is True
    ):
        raise ValueError("Replay manifest has invalid provenance fields")
    if schema_version not in _SUPPORTED_REPLAY_SCHEMA_VERSIONS:
        raise ValueError(
            f"Replay schema_version is {schema_version}, "
            f"expected one of {sorted(_SUPPORTED_REPLAY_SCHEMA_VERSIONS)}"
        )
    if schema_version == REPLAY_SCHEMA_VERSION:
        prompt_versions = manifest["prompt_versions"]
        if not (
            isinstance(prompt_versions, dict)
            and set(prompt_versions) == _PROMPT_SURFACES
            and all(
                isinstance(version, str) and version.strip()
                for version in prompt_versions.values()
            )
        ):
            raise ValueError("Replay manifest has invalid prompt_versions")
    elif not (
        isinstance(manifest["prompt_version"], str)
        and manifest["prompt_version"].strip()
    ):
        raise ValueError("Replay manifest has invalid prompt_version")
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
                if turn["expected_execution_accuracy"] not in {
                    "PASS",
                    "FAIL",
                    "EXEMPT",
                    "NOT_EVALUATED",
                }:
                    raise ValueError(
                        f"Replay scenario {scenario_id} has an invalid expected execution status"
                    )
                if turn["expected_grade"] not in {"PASS", "FAIL", "NOT_EVALUATED"}:
                    raise ValueError(
                        f"Replay scenario {scenario_id} has an invalid expected grade"
                    )
                seams = turn["seams"]
                if not isinstance(seams, dict):
                    raise ValueError(
                        f"Replay scenario {scenario_id} seams must be an object"
                    )
                seam_keys = (
                    _V3_SEAM_KEYS
                    if manifest["schema_version"] >= 3
                    else _V2_SEAM_KEYS
                )
                _assert_keys(seams, seam_keys, f"Replay scenario {scenario_id} seams")
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
                if manifest["schema_version"] >= 3:
                    if seams["tool_output"] is not None and not isinstance(
                        seams["tool_output"], str
                    ):
                        raise ValueError(
                            f"Replay scenario {scenario_id} tool output must be a string or null"
                        )
                    if seams["tool_arguments"] is not None and not isinstance(
                        seams["tool_arguments"], list
                    ):
                        raise ValueError(
                            f"Replay scenario {scenario_id} tool arguments must be a list or null"
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
            execution_turns = execution_repeats[repeat_index]["turns"]
            for turn_index, turn in enumerate(repeat["turns"]):
                execution_status = execution_turns[turn_index]["status"]
                if execution_status != turn["expected_execution_accuracy"]:
                    mismatches.append(
                        f"{scenario_id} r{repeat['repeat']} t{turn['turn']} execution "
                        f"expected {turn['expected_execution_accuracy']}, got {execution_status}"
                    )
                grade = next(
                    item
                    for item in grade_turns
                    if item["repeat"] == repeat["repeat"]
                    and item["turn"] == turn["turn"]
                )
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


def run_active_replays(database_url: str | None = None) -> dict[str, Any]:
    """Run every discovered active replay; a stale one fails loudly by name.

    Failures are collected across the whole set first so a single invocation
    names every invalid artifact instead of stopping at the first one.
    """
    reports: dict[str, Any] = {}
    failures: list[str] = []
    for path in active_replay_paths(ACTIVE_REPLAY_DIR):
        try:
            reports[path.name] = run_replay(path, database_url)
        except ValueError as exc:
            failures.append(f"{path.name}: {exc}")
    if failures:
        raise ValueError("Active replays are not all valid - " + "; ".join(failures))
    return reports


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Replay committed evaluation evidence without model or judge calls."
    )
    parser.add_argument("--replay", type=Path)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Replay every artifact in the active replay directory.",
    )
    parser.add_argument("--database-url")
    args = parser.parse_args(argv)
    if args.all:
        result = run_active_replays(args.database_url)
    else:
        result = run_replay(args.replay or REPLAY_PATH, args.database_url)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
