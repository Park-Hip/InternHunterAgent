"""Load the versioned evaluation scenario registry and derive DeepEval goldens from it."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import re
from typing import Any

import yaml
from deepeval.dataset import EvaluationDataset, Golden

SCENARIOS_PATH = Path(__file__).resolve().parent / "scenarios_v1.yaml"
_REQUIRED_KEYS = {"id", "name", "requirements", "decision", "type", "expected", "probe"}
_SCENARIO_TYPES = {"single", "conversational"}
_SCENARIO_ID_PATTERN = re.compile(r"(SAF|HON|HLP)-[A-Z]+(?:-[A-Z]+)*-[1-9][0-9]*")
_REQUIREMENT_PATTERN = re.compile(r"G[0-9]{2}")


def load_scenarios(path: Path = SCENARIOS_PATH) -> list[dict[str, Any]]:
    """Load and validate the one versioned evaluation scenario registry."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Expected a YAML list in {path}")

    # Report duplicate identifiers before field-level validation so the registry's primary key
    # error remains deterministic even when a copied fixture omits newer metadata.
    seen_raw_ids: set[str] = set()
    for item in raw:
        if isinstance(item, dict) and item.get("id") in seen_raw_ids:
            raise ValueError(f"Duplicate scenario id: {item['id']}")
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            seen_raw_ids.add(item["id"])

    scenarios: list[dict[str, Any]] = []
    ids: set[str] = set()
    for scenario in raw:
        if not isinstance(scenario, dict):
            raise ValueError("Each scenario must be a mapping")

        missing = _REQUIRED_KEYS - scenario.keys()
        if missing:
            raise ValueError(f"Scenario {scenario.get('id', '<unknown>')} missing keys: {missing}")

        scenario_id = scenario["id"]
        if not isinstance(scenario_id, str) or not _SCENARIO_ID_PATTERN.fullmatch(scenario_id):
            raise ValueError(
                "Scenario id must use the <CLASS>-<BEHAVIOR>-<n> taxonomy: "
                f"{scenario_id!r}"
            )
        if scenario_id in ids:
            raise ValueError(f"Duplicate scenario id: {scenario_id}")
        ids.add(scenario_id)

        scenario_type = scenario["type"]
        if scenario_type not in _SCENARIO_TYPES:
            raise ValueError(f"Scenario {scenario_id} has invalid type: {scenario_type!r}")

        if not isinstance(scenario["name"], str) or not scenario["name"]:
            raise ValueError(f"Scenario {scenario_id} requires a non-empty name")
        if not (
            isinstance(scenario["requirements"], list)
            and all(
                isinstance(requirement, str)
                and _REQUIREMENT_PATTERN.fullmatch(requirement)
                for requirement in scenario["requirements"]
            )
        ):
            raise ValueError(
                f"Scenario {scenario_id} requirements must be a list of G-code strings"
            )
        if scenario["decision"] is not None and not isinstance(scenario["decision"], int):
            raise ValueError(f"Scenario {scenario_id} decision must be an integer or null")

        has_input = "input" in scenario
        has_turns = "turns" in scenario
        if has_input == has_turns:
            raise ValueError(
                f"Scenario {scenario_id} must have exactly one of 'input' or 'turns'"
            )
        if scenario_type == "single" and not isinstance(scenario["input"], str):
            raise ValueError(f"Single-turn scenario {scenario_id} requires a string input")
        if scenario_type == "conversational" and not (
            isinstance(scenario["turns"], list)
            and scenario["turns"]
            and all(isinstance(turn, str) for turn in scenario["turns"])
        ):
            raise ValueError(
                f"Conversational scenario {scenario_id} requires a non-empty list of string turns"
            )
        if not isinstance(scenario["expected"], str) or not scenario["expected"]:
            raise ValueError(f"Scenario {scenario_id} requires expected behavior")
        if not isinstance(scenario["probe"], bool):
            raise ValueError(f"Scenario {scenario_id} probe must be a boolean")

        reference_sql = scenario.get("reference_sql")
        has_reference_sql = isinstance(reference_sql, str) or (
            isinstance(reference_sql, list)
            and bool(reference_sql)
            and all(isinstance(query, str) and query.strip() for query in reference_sql)
        )
        exemption = scenario.get("execution_accuracy_exempt")
        if has_reference_sql == bool(exemption):
            raise ValueError(
                f"Scenario {scenario_id} must have exactly one of reference_sql or "
                "execution_accuracy_exempt"
            )
        if isinstance(reference_sql, str) and not reference_sql.strip():
            raise ValueError(f"Scenario {scenario_id} reference_sql must be non-empty")
        if exemption is not None and (
            not isinstance(exemption, dict)
            or not isinstance(exemption.get("reason"), str)
            or not exemption["reason"].strip()
        ):
            raise ValueError(
                f"Scenario {scenario_id} execution_accuracy_exempt requires a reason"
            )

        scenarios.append(scenario)

    return scenarios


def repeat_count(scenario: dict[str, Any]) -> int:
    """Return the frozen determinism-protocol repeat count for a scenario."""
    return 3 if scenario["probe"] else 2


def scenario_category(scenario_id: str) -> str:
    """Return the class carried in a class-first scenario id."""
    return scenario_id.split("-", maxsplit=1)[0]


def build_eval_dataset() -> EvaluationDataset:
    """Generate single-turn DeepEval goldens directly from the scenario registry."""
    goldens = [
        Golden(
            input=scenario["input"],
            expected_output=scenario["expected"],
            additional_metadata={
                "id": scenario["id"],
                "category": scenario_category(scenario["id"]),
                "probe": scenario["probe"],
                "name": scenario["name"],
                "requirements": scenario["requirements"],
                "decision": scenario["decision"],
            },
        )
        for scenario in load_scenarios()
        if scenario["type"] == "single"
    ]
    return EvaluationDataset(goldens=goldens)


def format_scenario(scenario: dict[str, Any]) -> str:
    """Render a scenario for inspection without running the agent or a model."""
    question = scenario.get("input") or " -> ".join(scenario["turns"])
    return "\n".join(
        [
            f"Scenario: {scenario['id']}",
            f"Name: {scenario['name']}",
            f"Input: {question}",
            f"Expected behavior: {scenario['expected']}",
            f"Probe: {'yes' if scenario['probe'] else 'no'}",
        ]
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Provide a no-model CLI for checking the recovered instrument."""
    parser = argparse.ArgumentParser(description="Inspect evaluation scenarios without running a model.")
    parser.add_argument("--scenario", help="Scenario id to display. Omit to display every scenario.")
    args = parser.parse_args(argv)

    scenarios = load_scenarios()
    if args.scenario:
        scenarios = [scenario for scenario in scenarios if scenario["id"] == args.scenario]
        if not scenarios:
            parser.error(f"Unknown scenario id: {args.scenario}")

    print("\n\n".join(format_scenario(scenario) for scenario in scenarios))


if __name__ == "__main__":
    main()
