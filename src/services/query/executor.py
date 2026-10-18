"""Execute one validated SQL statement inside bounds, on the agent role.

Two independent bounds, both read from ``agent.query`` in
``config/settings.yaml``:

- **A server-side statement timeout.** Set per transaction with ``set_config``,
  so a query that is more expensive than expected is cancelled by PostgreSQL
  rather than by a Python timer that would leave it running.
- **A byte budget on the returned rows.** The executor measures what it is
  about to hand back and refuses rather than letting an unbounded result
  travel into the agent's memory.

Read-only enforcement stays here too: the transaction is marked read-only so a
write that ever slipped past ``validate_sql`` is refused by PostgreSQL itself.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from psycopg.errors import UndefinedColumn

from src.core.config import settings
from src.core.db import agent_session_factory


class ExecutorError(Exception):
    """Raised when validated SQL fails to execute against the database."""


class UndefinedColumnError(ExecutorError):
    """Raised when the generated query refers to a column outside the contract."""


class QueryTimeoutError(ExecutorError):
    """Raised when the server cancelled a statement that ran past its budget."""


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


def execute_validated_sql(sql: str) -> list[dict[str, Any]]:
    limits = execution_limits()
    try:
        with agent_session_factory() as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            session.execute(
                text("SELECT set_config('statement_timeout', :ms, true)"),
                {"ms": str(limits["statement_timeout_ms"])},
            ).scalar()
            result = session.execute(text(sql))
            rows = [dict(row) for row in result.mappings().all()]
            if _row_bytes(rows) > limits["max_result_bytes"]:
                raise ResultTooLargeError(
                    "The query returned more data than this agent is allowed to read."
                )
            return rows
    except ExecutorError:
        raise
    except (OperationalError, DBAPIError) as exc:
        if isinstance(getattr(exc, "orig", None), UndefinedColumn):
            raise UndefinedColumnError("Query referenced an unavailable column") from exc
        if _is_timeout(exc):
            raise QueryTimeoutError(
                "The query took too long and was stopped."
            ) from exc
        raise ExecutorError(f"Failed to execute query: {exc}") from exc


def _row_bytes(rows: list[dict[str, Any]]) -> int:
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
