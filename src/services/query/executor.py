"""Execute one validated SQL statement inside bounds, on the agent role.

Two independent bounds, both read from ``agent.query`` in
``config/settings.yaml``:

- **A server-side statement timeout.** Set per transaction with ``set_config``,
  so a query that is more expensive than expected is cancelled by PostgreSQL
  rather than by a Python timer that would leave it running.
- **A byte budget on the returned rows.** The executor measures what it is
  about to hand back and refuses rather than letting an unbounded result
  travel into the agent's memory.

Read-only enforcement stays here too: the transaction is marked read-only, at
repeatable read so a companion count sees the same snapshot as the fetch, so a
write that ever slipped past ``validate_sql`` is refused by PostgreSQL itself.

One bounded session serves every read, including the detail fetch, so the
timeout and the byte budget cannot be forgotten by a second caller (#702 E6).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session
from psycopg.errors import InsufficientPrivilege, UndefinedColumn

from src.core.config import settings
from src.core.db import agent_session_factory
from src.services.query.models import BoundedRows
from src.services.query.sql_validator import has_id_tiebreak


class ExecutorError(Exception):
    """Raised when validated SQL fails to execute against the database."""


class UndefinedColumnError(ExecutorError):
    """Raised when the generated query refers to a column outside the contract.

    Carries PostgreSQL's own primary message (``column "remote" does not
    exist``) so the tool can name the missing column to the model, which the
    old fixed refusal sentence never did (#702).
    """

    def __init__(self, message_primary: str) -> None:
        super().__init__(message_primary)
        self.message_primary = message_primary


class PermissionDeniedError(ExecutorError):
    """Raised when PostgreSQL refuses the agent role access to clean_jobs.

    The role holds column-level ``SELECT`` on the 16 contract columns only, so
    a statement that reads a hidden column, a whole row, or a table-level star
    fails with SQLSTATE 42501 (#722). The message is fixed and safe: the driver
    message and any host detail never travel to the model.
    """

    def __init__(self) -> None:
        super().__init__("permission denied for clean_jobs")


class QueryTimeoutError(ExecutorError):
    """Raised when the server cancelled a statement that ran past its budget."""

    def __init__(self, timeout_ms: int) -> None:
        super().__init__(f"statement exceeded the {timeout_ms} ms limit")
        self.timeout_ms = timeout_ms


class SqlStatementRejectedError(ExecutorError):
    """Raised when PostgreSQL refuses the generated statement deterministically.

    SQLSTATE class 42 is "syntax error or access rule violation": a syntax
    error (42601), a grouping error (42803), a datatype mismatch (42804), an
    undefined function (42883), and the rest. Each is a mistake in the
    statement that the model can rewrite, not a database outage (#751).

    Carries the server's primary message so the tool can relay an actionable
    detail to the model (#744). The message names the problem in the generated
    statement, never the database host, so it is safe to send to the model.

    Two class 42 codes keep their own handlers: the ``clean_jobs`` column
    grant (42501) is :class:`PermissionDeniedError`, and an unknown column
    (42703) is :class:`UndefinedColumnError`.
    """

    def __init__(self, message_primary: str) -> None:
        super().__init__(message_primary)
        self.message_primary = message_primary


class UnstableOrderError(ExecutorError):
    """Raised when a page starts at an offset without a total order.

    PostgreSQL promises no row order for a query without ORDER BY, and an
    order on a non-unique column can swap tied rows between calls. Either way,
    an OFFSET page can repeat or skip rows, so the statement is refused before
    it runs (#727). The detail names the fix for the model.
    """

    def __init__(self) -> None:
        super().__init__(
            "a page with OFFSET needs a stable order: include id in the "
            "ORDER BY, for example ORDER BY created_on DESC NULLS LAST, id"
        )


class ResultTooLargeError(ExecutorError):
    """Raised when the rows to return would exceed the configured byte budget."""


def execution_limits() -> dict[str, int]:
    query = settings.config_yaml.get("agent", {}).get("query")
    if not isinstance(query, dict):
        raise ValueError("Missing 'agent.query' section in config/settings.yaml")

    def positive_int(name: str) -> int:
        value = query.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"agent.query.{name} must be a positive integer in config/settings.yaml"
            )
        return value

    return {
        "statement_timeout_ms": positive_int("statement_timeout_ms"),
        "max_result_bytes": positive_int("max_result_bytes"),
    }


@contextmanager
def bounded_session() -> Iterator[Session]:
    """One agent-role session with the read-only and timeout bounds applied.

    This is the public seam the details fetch shares so both reads keep one
    timeout, one read-only transaction, and one byte budget (#702 E6).

    ``SET TRANSACTION`` must be the first statement of the transaction: it is
    read-only at repeatable read, so every statement in the session sees one
    snapshot and a write is refused by PostgreSQL itself.
    """
    limits = execution_limits()
    try:
        with agent_session_factory() as session:
            session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            )
            session.execute(
                text("SELECT set_config('statement_timeout', :ms, true)"),
                {"ms": str(limits["statement_timeout_ms"])},
            ).scalar()
            yield session
    except ExecutorError:
        raise
    except (OperationalError, DBAPIError) as exc:
        raise _map_db_error(exc, limits["statement_timeout_ms"]) from exc


def execute_bounded_select(base_sql: str, limit: int, offset: int = 0) -> BoundedRows:
    """Run ``base_sql`` under a hard row limit and report the real match total.

    ``base_sql`` is a validated SELECT with its own LIMIT/OFFSET/FETCH clause
    already removed; ``resolve_bounds`` produces one in that shape. The statement
    that runs is ``base_sql LIMIT <limit>``, followed by ``OFFSET <offset>`` when
    the page starts after the first row.

    The companion ``SELECT count(*) FROM (base_sql) AS q`` always counts the
    base query without LIMIT or OFFSET. It runs when the offset is non-zero or
    the fetch fills its limit, so a short last page and an empty page past the
    end both state the whole match set ("20 of 161"). Both statements run in
    one transaction, so they see one snapshot. The byte budget is checked
    before that count runs, and both statements are bounded by the session's
    statement timeout.

    An offset page is refused unless ``base_sql`` has a top-level ORDER BY
    that includes ``id``. Without a total order PostgreSQL may return the rows
    in a different order between the two calls, so the page would repeat or
    skip rows (#727).
    """
    if offset > 0 and not has_id_tiebreak(base_sql):
        raise UnstableOrderError()

    limits = execution_limits()
    with bounded_session() as session:
        statement = f"{base_sql} LIMIT {limit}"
        if offset:
            statement += f" OFFSET {offset}"
        result = session.execute(text(statement))
        # Columns come from the result itself, so an empty result still names
        # the columns it would have returned.
        columns = list(result.keys())
        rows = [list(row) for row in result.all()]
        if row_bytes(rows) > limits["max_result_bytes"]:
            raise ResultTooLargeError(
                "The query returned more data than this agent is allowed to read."
            )
        if offset > 0 or len(rows) == limit:
            total_rows = int(
                session.execute(
                    text(f"SELECT count(*) FROM ({base_sql}) AS q")
                ).scalar_one()
            )
        else:
            total_rows = len(rows)
    return BoundedRows(columns=columns, rows=rows, total_rows=total_rows)


def _map_db_error(exc: OperationalError | DBAPIError, timeout_ms: int) -> ExecutorError:
    """Translate one driver failure into the executor's error vocabulary.

    The mapping keys on SQLSTATE, never on the error text (#744). A message
    that happens to say "timeout" without SQLSTATE 57014 is a connection
    outage, not the statement budget, so a connection timeout stays
    ``unavailable`` while a cancelled statement stays ``timeout``.

    SQLSTATE class 42 is the generated statement's own mistake - syntax,
    grouping, datatypes, function signatures - so it is a rejection the model
    can rewrite, not an outage (#751). The two codes that already had a kind
    keep it: the ``clean_jobs`` column grant (42501) and an unknown column
    (42703).
    """
    orig = getattr(exc, "orig", None)
    sqlstate = _sqlstate(orig)
    message_primary = _message_primary(orig)

    if isinstance(orig, UndefinedColumn) or sqlstate == "42703":
        return UndefinedColumnError(message_primary or "unknown column")
    if _is_clean_jobs_privilege_denial(orig):
        return PermissionDeniedError()
    if sqlstate == "42501":
        # A denial on another object is an operational grant fault, not a
        # mistake in the model's statement, so it stays an outage.
        return ExecutorError(f"Failed to execute query: {exc}")
    if sqlstate == "57014":
        return QueryTimeoutError(timeout_ms)
    if sqlstate is not None and sqlstate.startswith("42"):
        return SqlStatementRejectedError(
            message_primary or "the database rejected the generated statement"
        )
    return ExecutorError(f"Failed to execute query: {exc}")


def _message_primary(orig: object) -> str | None:
    """Return the server's primary diagnostic message, or ``None``.

    Only ``diag.message_primary`` is relayed: it describes the offending
    statement and never carries the driver's connection detail, which can name
    the database host.
    """
    message = getattr(getattr(orig, "diag", None), "message_primary", None)
    if isinstance(message, str) and message:
        return message
    return None


def _sqlstate(orig: object) -> str | None:
    """Return the SQLSTATE of a driver error, or ``None`` when unknown.

    Prefers the server diagnostic (``diag.sqlstate``) and falls back to the
    psycopg exception class code, which the driver sets for every error type it
    recognises. A client-side connection failure carries neither, so it falls
    through to the generic ``unavailable`` mapping instead of being bucketed by
    a misleading message.
    """
    if orig is None:
        return None
    diag_sqlstate = getattr(getattr(orig, "diag", None), "sqlstate", None)
    if isinstance(diag_sqlstate, str) and diag_sqlstate:
        return diag_sqlstate
    cls_sqlstate = getattr(orig, "sqlstate", None)
    if isinstance(cls_sqlstate, str) and cls_sqlstate:
        return cls_sqlstate
    return None


def _is_clean_jobs_privilege_denial(orig: object) -> bool:
    """Whether the driver refused clean_jobs access for lack of privilege.

    Only SQLSTATE 42501 that names the table counts. A denial on another
    object stays a generic executor failure, so a misclassified error cannot
    tell the model to rewrite a query that was never about the column set.
    """
    if not isinstance(orig, InsufficientPrivilege):
        return False
    table_name = getattr(getattr(orig, "diag", None), "table_name", None)
    if table_name == "clean_jobs":
        return True
    return "clean_jobs" in str(orig)


def row_bytes(rows: list[Any]) -> int:
    """A stable, cheap size measure for a result set."""
    if not rows:
        return 0
    return len(json.dumps(rows, default=str, ensure_ascii=False).encode("utf-8"))
