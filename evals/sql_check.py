"""Compare generated SQL with reference results on the read-only fixture database.

Queries run through the fixture reader role, the same column-granted, non-owner
role the evaluation tool uses (#730). A generated star or hidden-column read
therefore fails here as it does in production instead of returning 21 columns.
"""

from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from evals.fixtures.loader import fixture_reader_database_url
from src.core.column_contract import HIDDEN_COLUMN_NAMES, VISIBLE_COLUMN_NAMES

_SELECT = re.compile(r"\s*SELECT\s+(?:DISTINCT\s+)?(.*?)\s+FROM\s", re.I | re.S)
_COUNT = re.compile(r"\s*COUNT\s*\(\s*\*\s*\)\s+AS\s+count\s*", re.I)


class ReaderRoleError(ValueError):
    """The scoring connection is not the column-granted, non-owner reader role.

    Scoring through the owner or a role with table-level privilege would let a
    star or hidden-column read pass, so a score would no longer describe the
    boundary production enforces (#730, #760).
    """


def verify_reader_role(database_url: str) -> None:
    """Refuse to score unless *database_url* is a non-owner column reader.

    The checks are made in PostgreSQL rather than trusted from the DSN: the
    connected role must not own ``clean_jobs``, must not be a superuser (both
    bypass grants), must hold no table-level ``SELECT`` or write privilege, must
    read every visible column, and must be refused every hidden column.
    """
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            role, superuser = connection.execute(
                text(
                    "SELECT current_user, rolsuper FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            ).one()
            owner = connection.execute(
                text(
                    "SELECT pg_get_userbyid(relowner) FROM pg_class "
                    "WHERE oid = 'public.clean_jobs'::regclass"
                )
            ).scalar_one()
            if superuser:
                raise ReaderRoleError(
                    f"scoring role {role!r} is a superuser; it bypasses the column grants"
                )
            if role == owner:
                raise ReaderRoleError(
                    f"scoring role {role!r} owns clean_jobs; the owner bypasses the column grants"
                )
            if connection.execute(
                text(
                    "SELECT has_table_privilege(current_user, "
                    "'public.clean_jobs', 'SELECT')"
                )
            ).scalar_one():
                raise ReaderRoleError(
                    f"scoring role {role!r} has table-level SELECT on clean_jobs"
                )
            for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                if connection.execute(
                    text(
                        "SELECT has_table_privilege(current_user, "
                        "'public.clean_jobs', :privilege)"
                    ),
                    {"privilege": privilege},
                ).scalar_one():
                    raise ReaderRoleError(
                        f"scoring role {role!r} has {privilege} on clean_jobs"
                    )
            missing = [
                column
                for column in VISIBLE_COLUMN_NAMES
                if not connection.execute(
                    text(
                        "SELECT has_column_privilege(current_user, "
                        "'public.clean_jobs', :column, 'SELECT')"
                    ),
                    {"column": column},
                ).scalar_one()
            ]
            if missing:
                raise ReaderRoleError(
                    f"scoring role {role!r} cannot read the contract columns: "
                    + ", ".join(missing)
                )
            readable_hidden = [
                column
                for column in HIDDEN_COLUMN_NAMES
                if connection.execute(
                    text(
                        "SELECT has_column_privilege(current_user, "
                        "'public.clean_jobs', :column, 'SELECT')"
                    ),
                    {"column": column},
                ).scalar_one()
            ]
            if readable_hidden:
                raise ReaderRoleError(
                    f"scoring role {role!r} can read hidden columns: "
                    + ", ".join(readable_hidden)
                )
    finally:
        engine.dispose()


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
    engine = create_engine(database_url or fixture_reader_database_url())
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
    """Compare row identity, a count-only aggregate, an empty result, or full row sets.

    An id-less generated query must never pass on two empty results. SQL errors
    are infrastructure failures, not bad model answers.
    """
    if mode not in {"ids_only", "aggregate_count", "zero_results", "rows_equal"}:
        raise ValueError(f"Unknown SQL comparison mode: {mode}")
    if mode in {"ids_only", "zero_results"} and "id" not in (projected_columns(reference_sql) or []):
        raise ValueError("Reference SQL must project id")
    reference_match = _SELECT.match(reference_sql)
    if mode == "aggregate_count" and not _COUNT.fullmatch(reference_match[1] if reference_match else ""):
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
        generated_match = _SELECT.match(generated_sql)
        if not generated_match or not _COUNT.fullmatch(generated_match[1]):
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
    if mode == "rows_equal":
        # Grouped and two-figure results carry no single identity column, so the
        # full row set is compared order-insensitively, with values compared as
        # their string form (the same normalization the id modes use).
        actual = Counter(json.dumps(row, default=str, sort_keys=True) for row in generated)
        expected_rows = Counter(json.dumps(row, default=str, sort_keys=True) for row in reference)
        return {
            **details,
            "status": "PASS" if actual == expected_rows else "FAIL",
            "missing_rows": [json.loads(key) for key in (expected_rows - actual).elements()],
            "unexpected_rows": [json.loads(key) for key in (actual - expected_rows).elements()],
        }
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
