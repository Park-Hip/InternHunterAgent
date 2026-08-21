"""Deterministic execution-accuracy grading for persisted evaluation seams."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from evals.fixtures.loader import fixture_database_url
from evals.scenarios import load_scenarios


_SELECT_LIST_PATTERN = re.compile(r"\s*SELECT\s+(?:DISTINCT\s+)?(.*?)\s+FROM\s", re.IGNORECASE | re.DOTALL)


def _value_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _split_select_list(select_list: str) -> list[str]:
    """Split a select list on its top-level commas, so a call's arguments stay one item."""
    items: list[str] = []
    depth = 0
    current: list[str] = []
    for character in select_list:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            items.append("".join(current))
            current = []
            continue
        current.append(character)
    items.append("".join(current))
    return items


def selects_id(sql: str) -> bool:
    """Report whether a reference query projects an ``id`` column.

    Reference queries are written in this repository and are single-table selects, so reading
    the select list is enough. A query this cannot parse is reported as not selecting ``id``,
    which fails the ``ids_only`` guard loudly instead of grading against an unknown projection.
    """
    match = _SELECT_LIST_PATTERN.match(sql)
    if match is None:
        return False
    select_list = match.group(1).strip()
    if select_list == "*":
        return True
    for item in _split_select_list(select_list):
        item = item.strip()
        alias = re.search(r"\s+AS\s+(\w+)\s*$", item, re.IGNORECASE)
        name = alias.group(1) if alias else item.rsplit(".", maxsplit=1)[-1]
        if name.strip('"').lower() == "id":
            return True
    return False


def validate_execution_comparison(scenario: dict[str, Any]) -> None:
    """Reject ``ids_only`` on a scenario whose reference SQL does not project ``id``.

    Without this, ``ids_only`` over a ``COUNT(*)`` reference compares two empty id multisets and
    passes every generated query. That is a silent false pass, which is worse than the projection
    failure ``ids_only`` exists to remove.
    """
    comparison_mode = scenario.get("grading", {}).get("execution_comparison", "exact")
    if comparison_mode != "ids_only":
        return
    reference_sql = scenario.get("reference_sql")
    queries = reference_sql if isinstance(reference_sql, list) else [reference_sql]
    for index, query in enumerate(queries):
        if not isinstance(query, str) or not selects_id(query):
            turn = f" turn {index + 1}" if isinstance(reference_sql, list) else ""
            raise ValueError(
                f"Scenario {scenario.get('id', '<unknown>')}{turn} declares "
                "execution_comparison: ids_only but its reference SQL does not select id"
            )


def _result_key(row: dict[str, Any], compare_ids: bool) -> str:
    """Build a comparison key without treating aliases as result differences."""
    if compare_ids:
        return _value_key(row["id"])
    # Result columns are ordered in a SQL row, while aliases are presentation metadata.
    return json.dumps([_value_key(value) for value in row.values()], ensure_ascii=False)


def execute_query(sql: str, database_url: str | None = None) -> list[dict[str, Any]]:
    """Execute one read-only reference or generated query against the fixture."""
    engine = create_engine(database_url or fixture_database_url())
    try:
        with engine.begin() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            result = connection.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]
    finally:
        engine.dispose()


def compare_result_sets(
    generated_sql: str,
    reference_sql: str,
    database_url: str | None = None,
    comparison_mode: str = "exact",
) -> dict[str, Any]:
    """Compare query results using the scenario's explicit semantic contract."""
    try:
        generated_rows = execute_query(generated_sql, database_url)
        reference_rows = execute_query(reference_sql, database_url)
    except SQLAlchemyError as exc:
        return {"status": "INFRA", "error": str(exc)}

    if comparison_mode == "ids_only":
        # Dropping an id-less row would compare a short multiset against the reference, and when the
        # reference legitimately returns nothing, two empty multisets match whatever was generated.
        # That is the same silent false pass validate_execution_comparison prevents on the reference
        # side, so neither side may be filtered.
        if any("id" not in row for row in reference_rows):
            raise ValueError(
                "Reference query for an ids_only comparison returned rows without an id column"
            )
        if any("id" not in row for row in generated_rows):
            return {
                "status": "FAIL",
                "error": "Generated query does not project id, so row identity cannot be compared",
                "generated_row_count": len(generated_rows),
                "reference_row_count": len(reference_rows),
                "generated_rows": generated_rows,
                "reference_rows": reference_rows,
                "comparison_mode": comparison_mode,
            }
        generated = Counter(_value_key(row["id"]) for row in generated_rows)
        reference = Counter(_value_key(row["id"]) for row in reference_rows)
    elif comparison_mode == "contains_reference":
        generated = Counter(
            _result_key({key: row[key] for key in reference_rows[0]}, False)
            for row in generated_rows
            if reference_rows and all(key in row for key in reference_rows[0])
        )
        reference = Counter(_result_key(row, False) for row in reference_rows)
    elif comparison_mode == "exact":
        generated = Counter(_result_key(row, False) for row in generated_rows)
        reference = Counter(_result_key(row, False) for row in reference_rows)
    else:
        raise ValueError(f"Unknown comparison mode: {comparison_mode!r}")
    matches = reference <= generated if comparison_mode == "contains_reference" else generated == reference
    return {
        "status": "PASS" if matches else "FAIL",
        "generated_row_count": len(generated_rows),
        "reference_row_count": len(reference_rows),
        "generated_rows": generated_rows,
        "reference_rows": reference_rows,
        "comparison_mode": comparison_mode,
    }


def grade_turn(
    scenario: dict[str, Any],
    generated_sql: str | None,
    database_url: str | None = None,
    reference_sql: str | None = None,
) -> dict[str, Any]:
    """Grade one persisted turn, preserving explicit registry exemptions."""
    exemption = scenario.get("execution_accuracy_exempt")
    if exemption is not None:
        return {
            "status": "EXEMPT",
            "reason": exemption["reason"],
        }
    validate_execution_comparison(scenario)
    reference_sql = reference_sql or scenario.get("reference_sql")
    if not generated_sql:
        return {"status": "UNRUN", "error": "No generated SQL was persisted"}
    if not isinstance(reference_sql, str):
        return {"status": "INFRA", "error": "Scenario has no turn reference SQL"}
    comparison_mode = scenario.get("grading", {}).get("execution_comparison", "exact")
    if comparison_mode == "exact":
        result = compare_result_sets(generated_sql, reference_sql, database_url)
    else:
        result = compare_result_sets(
            generated_sql, reference_sql, database_url, comparison_mode
        )
    return {"status": result.pop("status"), "reference_sql": reference_sql, **result}


def grade_run(run: dict[str, Any], database_url: str | None = None) -> dict[str, Any]:
    """Return execution-accuracy results for every persisted turn in a run."""
    scenarios = {scenario["id"]: scenario for scenario in load_scenarios()}
    # Reject a misclassified scenario before the first query runs, so a registry mistake cannot
    # be mistaken for a grading result partway through a run.
    for registry_scenario in scenarios.values():
        validate_execution_comparison(registry_scenario)
    results: dict[str, Any] = {}
    for scenario_id, scenario_record in run.get("scenarios", {}).items():
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            results[scenario_id] = {"status": "INFRA", "error": "Unknown scenario id"}
            continue
        repeats = []
        for repeat in scenario_record.get("repeats", []):
            turns = []
            for turn_index, turn in enumerate(repeat.get("turns", [])):
                seams = turn.get("seams", {})
                reference_sql = scenario.get("reference_sql")
                if isinstance(reference_sql, list):
                    reference_sql = reference_sql[turn_index] if turn_index < len(reference_sql) else None
                turns.append(grade_turn(scenario, seams.get("sql_text"), database_url, reference_sql))
            repeats.append({"repeat": repeat.get("repeat"), "turns": turns})
        results[scenario_id] = repeats
    return {"run_id": run.get("manifest", {}).get("run_id"), "scenarios": results}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Grade persisted runs by SQL execution accuracy.")
    parser.add_argument("run", type=Path)
    parser.add_argument("--database-url")
    # Reported rows carry the fixture's Vietnamese company names, so stdout cannot
    # be redirected into the grader's --execution-accuracy input on a cp1252
    # console. Writing the file directly keeps the report UTF-8 on every platform.
    parser.add_argument("--output", type=Path, help="Write the report as UTF-8 JSON instead of printing it")
    args = parser.parse_args(argv)
    run = json.loads(args.run.read_text(encoding="utf-8"))
    report = json.dumps(grade_run(run, args.database_url), ensure_ascii=False, default=str, indent=2)
    if args.output is None:
        print(report)
        return
    args.output.write_text(report, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
