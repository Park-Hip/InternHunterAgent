"""Load the versioned evaluation scenario registry and derive DeepEval goldens from it."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import re
from typing import Any

import yaml
from deepeval.dataset import EvaluationDataset, Golden

# Default scenario registry path. Override by passing a different Path to
# load_scenarios() — e.g. `load_scenarios(Path("scenarios_v2.yaml"))` — without
# touching this line. A future v2 registry stays on its own file; the function
# signature is the override point, not a second constant here.
SCENARIOS_PATH = Path(__file__).resolve().parent / "scenarios_v1.yaml"
_REQUIRED_KEYS = {"id", "name", "requirements", "decision", "type", "expected", "probe", "expected_tools"}
_SCENARIO_TYPES = {"single", "conversational"}
_SCENARIO_ID_PATTERN = re.compile(r"(SAF|HON|HLP)-[A-Z]+(?:-[A-Z]+)*-[1-9][0-9]*")
_REQUIREMENT_PATTERN = re.compile(r"G[0-9]{2}")
# The grader reads its tool expectation from here, so an unknown name would
# silently become an expectation no agent can satisfy.
_KNOWN_TOOLS = {"query_clean_jobs", "get_job_details"}
_TURN_TOOL_EXPECTATION_KEYS = {"required", "allowed"}
# The rest of each scenario's grading expectations. Same reasoning as the tool
# names: a misspelled field would be silently ignored and quietly weaken a rule.
_GRADING_KEYS = {
    "execution_comparison",
    "assertions",
    "projection",
}
_EXECUTION_COMPARISONS = {
    "exact",
    "contains_reference",
    "ids_only",
    "limited_ids",
    "aggregate_count",
    "zero_results",
    "cross_currency",
}
_ASSERTION_TYPES = {"literal", "structural", "semantic"}
_ASSERTION_FIELDS = {
    "literal": {"expected_answer_count", "count_only", "forbidden_patterns", "required_patterns"},
    "structural": {
        "require_vietnamese",
        "require_source_links",
        "required_any",
        "forbidden_any",
        "reject_salary_period",
        "preserve_returned_job_levels",
        "reject_title_to_level_inference",
        "reject_lifecycle_substitution",
    },
    "semantic": {"required_any", "forbidden_any", "forbid_single_salary_winner"},
}
_PROJECTION_COLUMNS = {
    "id", "title", "company", "role", "tech_stack", "location", "source_url",
    "job_level", "listing_expires_on", "created_on", "is_internship", "salary_min",
    "salary_max", "salary_currency", "is_salary_negotiable", "count",
}


def _validate_term(scenario_id: str, field: str, term: Any) -> None:
    """Accept a literal answer substring or a reference into the behavior glossary.

    The glossary *name* is checked in ``evals/grader.py``, which already owns the
    glossary. Resolving it here would pull ``src.core.config`` into the registry
    loader, and the loader is imported on paths that must not construct and cache
    ``Settings()`` before the fixture database is bound.
    """
    if isinstance(term, dict) and set(term) == {"glossary"}:
        if isinstance(term["glossary"], str) and term["glossary"].strip():
            return
    if isinstance(term, dict) and set(term) == {"lexicon"}:
        if isinstance(term["lexicon"], list) and term["lexicon"] and all(
            isinstance(item, str) and item.strip() for item in term["lexicon"]
        ):
            return
    raise ValueError(
        f"Scenario {scenario_id} {field} terms must use {{glossary: NAME}} or {{lexicon: [...]}}: {term!r}"
    )


def _validate_term_list(scenario_id: str, field: str, value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Scenario {scenario_id} {field} must be a non-empty list")
    for term in value:
        _validate_term(scenario_id, field, term)


def _validate_grading(scenario_id: str, grading: Any) -> None:
    """Reject an unknown or malformed grading field before it can weaken a rule."""
    if not isinstance(grading, dict) or not grading:
        raise ValueError(f"Scenario {scenario_id} grading must be a non-empty mapping")

    unknown = grading.keys() - _GRADING_KEYS
    if unknown:
        raise ValueError(f"Scenario {scenario_id} has unknown grading fields: {sorted(unknown)}")

    assertions = grading.get("assertions", [])
    if not isinstance(assertions, list):
        raise ValueError(f"Scenario {scenario_id} assertions must be a list")
    for assertion in assertions:
        if not isinstance(assertion, dict):
            raise ValueError(f"Scenario {scenario_id} assertion must be a mapping")
        assertion_type = assertion.get("type")
        if assertion_type not in _ASSERTION_TYPES:
            raise ValueError(f"Scenario {scenario_id} has unknown assertion type: {assertion_type!r}")
        fields = set(assertion) - {"type"}
        if not fields:
            raise ValueError(f"Scenario {scenario_id} {assertion_type} assertion has no fields")
        unsupported = fields - _ASSERTION_FIELDS[assertion_type]
        if unsupported:
            raise ValueError(
                f"Scenario {scenario_id} {assertion_type} assertion has unsupported fields: {sorted(unsupported)}"
            )
        _validate_assertion_fields(scenario_id, assertion_type, assertion)

    if "execution_comparison" in grading and grading["execution_comparison"] not in _EXECUTION_COMPARISONS:
        raise ValueError(
            f"Scenario {scenario_id} has an unknown execution_comparison: "
            f"{grading['execution_comparison']!r}"
        )
    if "projection" in grading:
        projection = grading["projection"]
        if not isinstance(projection, dict) or set(projection) != {"exact"}:
            raise ValueError(f"Scenario {scenario_id} projection must contain exactly 'exact'")
        columns = projection["exact"]
        if not isinstance(columns, list) or not columns or any(
            not isinstance(column, str) or column not in _PROJECTION_COLUMNS for column in columns
        ):
            raise ValueError(f"Scenario {scenario_id} projection exact must name known output columns")
        if len(columns) != len(set(columns)):
            raise ValueError(f"Scenario {scenario_id} projection exact must not contain duplicates")


def _validate_assertion_fields(
    scenario_id: str, assertion_type: str, assertion: dict[str, Any]
) -> None:
    if "expected_answer_count" in assertion:
        count = assertion["expected_answer_count"]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(
                f"Scenario {scenario_id} expected_answer_count must be a non-negative integer"
            )

    if "count_only" in assertion:
        if assertion["count_only"] is not True:
            raise ValueError(f"Scenario {scenario_id} count_only must be true")
        if "expected_answer_count" not in assertion:
            raise ValueError(
                f"Scenario {scenario_id} count_only requires expected_answer_count"
            )

    if "forbid_single_salary_winner" in assertion and not isinstance(
        assertion["forbid_single_salary_winner"], bool
    ):
        raise ValueError(f"Scenario {scenario_id} forbid_single_salary_winner must be a boolean")

    if "require_vietnamese" in assertion and not isinstance(assertion["require_vietnamese"], bool):
        raise ValueError(f"Scenario {scenario_id} require_vietnamese must be a boolean")

    if "require_source_links" in assertion and assertion["require_source_links"] is not True:
        raise ValueError(f"Scenario {scenario_id} require_source_links must be true")

    for field in (
        "reject_salary_period",
        "preserve_returned_job_levels",
        "reject_title_to_level_inference",
        "reject_lifecycle_substitution",
    ):
        if field in assertion and assertion[field] is not True:
            raise ValueError(f"Scenario {scenario_id} {field} must be true")

    if "required_any" in assertion:
        groups = assertion["required_any"]
        if not isinstance(groups, list) or not groups:
            raise ValueError(f"Scenario {scenario_id} required_any must be a non-empty list")
        # Each group is an OR of alternatives, and all groups must match. An empty
        # group would be unsatisfiable rather than permissive.
        for group in groups:
            _validate_term_list(scenario_id, "required_any group", group)

    if "forbidden_any" in assertion:
        _validate_term_list(scenario_id, "forbidden_any", assertion["forbidden_any"])

    if "forbidden_patterns" in assertion:
        patterns = assertion["forbidden_patterns"]
        if not isinstance(patterns, list) or not patterns:
            raise ValueError(f"Scenario {scenario_id} forbidden_patterns must be a non-empty list")
        for pattern in patterns:
            if not isinstance(pattern, str):
                raise ValueError(
                    f"Scenario {scenario_id} forbidden_patterns must be regular-expression strings"
                )
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"Scenario {scenario_id} forbidden pattern {pattern!r} does not compile: {exc}"
                ) from exc

    if "required_patterns" in assertion:
        patterns = assertion["required_patterns"]
        if not isinstance(patterns, list) or not patterns:
            raise ValueError(f"Scenario {scenario_id} required_patterns must be a non-empty list")
        for pattern in patterns:
            if not isinstance(pattern, str):
                raise ValueError(
                    f"Scenario {scenario_id} required_patterns must be regular-expression strings"
                )
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"Scenario {scenario_id} required pattern {pattern!r} does not compile: {exc}"
                ) from exc


def _validate_tool_expectation(scenario_id: str, field: str, expectation: Any) -> None:
    if not isinstance(expectation, dict) or set(expectation) != _TURN_TOOL_EXPECTATION_KEYS:
        raise ValueError(
            f"Scenario {scenario_id} {field} must contain required and allowed"
        )
    required = expectation["required"]
    allowed = expectation["allowed"]
    if not (
        isinstance(required, list)
        and isinstance(allowed, list)
        and all(tool in _KNOWN_TOOLS for tool in required)
        and all(tool in _KNOWN_TOOLS for tool in allowed)
    ):
        raise ValueError(
            f"Scenario {scenario_id} {field} lists must contain known tool names"
        )
    if not set(required).issubset(allowed):
        raise ValueError(
            f"Scenario {scenario_id} {field} required tools must be allowed"
        )


def _validate_turn_tool_expectations(scenario_id: str, scenario: dict[str, Any]) -> None:
    """Validate a conversational scenario's optional per-turn tool contract."""
    expectations = scenario.get("turn_tool_expectations")
    if expectations is None:
        return
    if scenario["type"] != "conversational":
        raise ValueError(
            f"Scenario {scenario_id} turn_tool_expectations require a conversational scenario"
        )
    if not isinstance(expectations, list) or len(expectations) != len(scenario["turns"]):
        raise ValueError(
            f"Scenario {scenario_id} turn_tool_expectations must have one entry per turn"
        )
    for expectation in expectations:
        _validate_tool_expectation(scenario_id, "turn tool expectation", expectation)


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
        if not (
            isinstance(scenario["expected_tools"], list)
            and all(tool in _KNOWN_TOOLS for tool in scenario["expected_tools"])
        ):
            raise ValueError(
                f"Scenario {scenario_id} expected_tools must be a list of known tool names"
            )

        _validate_turn_tool_expectations(scenario_id, scenario)
        if "tool_expectation" in scenario:
            _validate_tool_expectation(scenario_id, "tool_expectation", scenario["tool_expectation"])

        if "grading" in scenario:
            _validate_grading(scenario_id, scenario["grading"])

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
    lines = [
        f"Scenario: {scenario['id']}",
        f"Name: {scenario['name']}",
        f"Input: {question}",
        f"Expected behavior: {scenario['expected']}",
        f"Expected tools: {', '.join(scenario['expected_tools']) or 'none'}",
    ]
    if expectations := scenario.get("turn_tool_expectations"):
        lines.append(f"Turn tool expectations: {expectations}")
    elif expectation := scenario.get("tool_expectation"):
        lines.append(f"Tool expectation: {expectation}")
    lines.append(f"Probe: {'yes' if scenario['probe'] else 'no'}")
    return "\n".join(lines)


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
