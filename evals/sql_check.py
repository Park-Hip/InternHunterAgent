"""Compare generated SQL with reference results on the read-only fixture database."""

from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from evals.fixtures.loader import fixture_database_url

_SELECT = re.compile(r"\s*SELECT\s+(?:DISTINCT\s+)?(.*?)\s+FROM\s", re.I | re.S)
_COUNT = re.compile(r"\s*COUNT\s*\(\s*\*\s*\)\s+AS\s+count\s*", re.I)


def projected_columns(sql: str) -> list[str] | None:
    match = _SELECT.match(sql)
    if match is None:
        return None
    columns = []
    for part in match.group(1).split(","):
        part = part.strip()
        alias = re.search(r"\s+AS\s+(\w+)\s*$", part, re.I)
        columns.append((alias.group(1) if alias else part.rsplit(".", 1)[-1]).strip('"').lower())
    return columns


def execute_query(sql: str, database_url: str | None = None) -> list[dict[str, Any]]:
    engine = create_engine(database_url or fixture_database_url())
    try:
        with engine.begin() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            return [dict(row) for row in connection.execute(text(sql)).mappings()]
    finally:
        engine.dispose()


def compare_result_sets(
    generated_sql: str, reference_sql: str, database_url: str | None = None,
    mode: str = "ids_only", expected_count: int | None = None,
    display_limit: int | None = None,
) -> dict[str, Any]:
    """Compare row identity, a count-only aggregate, or an empty result.

    An id-less generated query must never pass on two empty results. SQL errors
    are infrastructure failures, not bad model answers.
    """
    if mode not in {"ids_only", "aggregate_count", "zero_results"}:
        raise ValueError(f"Unknown SQL comparison mode: {mode}")
    if mode in {"ids_only", "zero_results"} and "id" not in (projected_columns(reference_sql) or []):
        raise ValueError("Reference SQL must project id")
    if mode == "aggregate_count" and not _COUNT.fullmatch((_SELECT.match(reference_sql) or [None, ""])[1]):
        raise ValueError("Count reference must project COUNT(*) AS count")
    try:
        generated = execute_query(generated_sql, database_url)
        reference = execute_query(reference_sql, database_url)
    except SQLAlchemyError as exc:
        return {"status": "INFRA", "error": str(exc)}
    fetched_count = len(generated)
    if display_limit is not None:
        if display_limit <= 0 or mode != "ids_only":
            raise ValueError("display_limit requires a positive ids_only comparison")
        generated = generated[:display_limit]
    details: dict[str, Any] = {"actual_count": len(generated), "fetched_count": fetched_count, "reference_count": len(reference)}
    if mode == "aggregate_count":
        if not _SELECT.match(generated_sql) or not _COUNT.fullmatch(_SELECT.match(generated_sql)[1]):
            return {**details, "status": "FAIL", "reason": "Count query must project only COUNT(*) AS count"}
        if len(reference) != 1 or len(reference[0]) != 1:
            raise ValueError("Count reference must return one aggregate")
        expected = next(iter(reference[0].values()))
        observed = next(iter(generated[0].values())) if len(generated) == 1 and len(generated[0]) == 1 else None
        if expected_count is not None and expected != expected_count:
            raise ValueError("Dataset expected_count disagrees with fixture")
        return {**details, "status": "PASS" if observed == expected else "FAIL", "expected": expected, "actual": observed}
    if mode == "zero_results":
        if reference:
            raise ValueError("Zero-results reference returned rows")
        return {**details, "status": "PASS" if not generated else "FAIL"}
    if "id" not in (projected_columns(generated_sql) or []):
        return {**details, "status": "FAIL", "reason": "Generated SQL does not project id"}
    if any("id" not in row for row in generated + reference):
        return {**details, "status": "FAIL", "reason": "Result has no id"}
    actual = Counter(json.dumps(row["id"], default=str) for row in generated)
    expected_ids = Counter(json.dumps(row["id"], default=str) for row in reference)
    return {
        **details, "status": "PASS" if actual == expected_ids else "FAIL",
        "missing_ids": [json.loads(key) for key in (expected_ids - actual).elements()],
        "unexpected_ids": [json.loads(key) for key in (actual - expected_ids).elements()],
    }
