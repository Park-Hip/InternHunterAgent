"""Deterministic execution-accuracy grading for persisted evaluation seams."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from evals.fixtures.loader import fixture_database_url
from evals.scenarios import load_scenarios


def _value_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


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
) -> dict[str, Any]:
    """Compare query results as unordered row multisets, including duplicates."""
    try:
        generated_rows = execute_query(generated_sql, database_url)
        reference_rows = execute_query(reference_sql, database_url)
    except SQLAlchemyError as exc:
        return {"status": "INFRA", "error": str(exc)}

    compare_ids = bool(generated_rows and reference_rows) and all(
        "id" in row for row in generated_rows + reference_rows
    )
    generated = Counter(_result_key(row, compare_ids) for row in generated_rows)
    reference = Counter(_result_key(row, compare_ids) for row in reference_rows)
    return {
        "status": "PASS" if generated == reference else "FAIL",
        "generated_row_count": len(generated_rows),
        "reference_row_count": len(reference_rows),
        "generated_rows": generated_rows,
        "reference_rows": reference_rows,
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
    reference_sql = reference_sql or scenario.get("reference_sql")
    if not generated_sql:
        return {"status": "UNRUN", "error": "No generated SQL was persisted"}
    if not isinstance(reference_sql, str):
        return {"status": "INFRA", "error": "Scenario has no turn reference SQL"}
    result = compare_result_sets(generated_sql, reference_sql, database_url)
    return {"status": result.pop("status"), "reference_sql": reference_sql, **result}


def grade_run(run: dict[str, Any], database_url: str | None = None) -> dict[str, Any]:
    """Return execution-accuracy results for every persisted turn in a run."""
    scenarios = {scenario["id"]: scenario for scenario in load_scenarios()}
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
