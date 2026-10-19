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
from psycopg.errors import UndefinedColumn

from src.core.config import settings
from src.core.db import agent_session_factory
from src.services.query.models import BoundedRows


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


class QueryTimeoutError(ExecutorError):
    """Raised when the server cancelled a statement that ran past its budget."""

    def __init__(self, timeout_ms: int) -> None:
        super().__init__(f"statement exceeded the {timeout_ms} ms limit")
        self.timeout_ms = timeout_ms


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
def _bounded_session() -> Iterator[Session]:
    """One agent-role session with the read-only and timeout bounds applied.

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


def execute_bounded_select(base_sql: str, limit: int) -> BoundedRows:
    """Run ``base_sql`` under a hard row limit and report the real match total.

    ``base_sql`` is a validated SELECT with any trailing LIMIT/OFFSET already
    removed; ``resolve_bounds`` produces one in that shape. The statement that
    runs is ``base_sql LIMIT <limit>``.

    When the fetch fills its limit, a companion
    ``SELECT count(*) FROM (base_sql) AS q`` runs in the same transaction, so
    both statements see one snapshot and the total is the number of rows the
    query matches without any LIMIT ("20 of 161"). The byte budget is checked
    before that count runs, and both statements are bounded by the session's
    statement timeout.
    """
    limits = execution_limits()
    with _bounded_session() as session:
        result = session.execute(text(f"{base_sql} LIMIT {limit}"))
        # Columns come from the result itself, so an empty result still names
        # the columns it would have returned.
        columns = list(result.keys())
        rows = [list(row) for row in result.all()]
        if row_bytes(rows) > limits["max_result_bytes"]:
            raise ResultTooLargeError(
                "The query returned more data than this agent is allowed to read."
            )
        if len(rows) == limit:
            total_rows = int(
                session.execute(
                    text(f"SELECT count(*) FROM ({base_sql}) AS q")
                ).scalar_one()
            )
        else:
            total_rows = len(rows)
    return BoundedRows(columns=columns, rows=rows, total_rows=total_rows)


def _map_db_error(exc: OperationalError | DBAPIError, timeout_ms: int) -> ExecutorError:
    """Translate one driver failure into the executor's error vocabulary."""
    orig = getattr(exc, "orig", None)
    if isinstance(orig, UndefinedColumn):
        message_primary = getattr(getattr(orig, "diag", None), "message_primary", None)
        return UndefinedColumnError(message_primary or "unknown column")
    if _is_timeout(exc):
        return QueryTimeoutError(timeout_ms)
    return ExecutorError(f"Failed to execute query: {exc}")


def row_bytes(rows: list[Any]) -> int:
    """A stable, cheap size measure for a result set."""
    if not rows:
        return 0
    return len(json.dumps(rows, default=str, ensure_ascii=False).encode("utf-8"))


def _is_timeout(exc: Exception) -> bool:
    """Whether the failure is the server cancelling a statement."""
    for candidate in (exc, getattr(exc, "orig", None)):
        if candidate is None:
            continue
        if type(candidate).__name__ in {"QueryCanceled", "LockNotAvailable", "StatementTimeout"}:
            return True
        if "timeout" in str(candidate).casefold() or "canceling statement" in str(candidate).casefold():
            return True
    return False
