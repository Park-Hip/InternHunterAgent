"""Run compiled statements inside bounds, on the least-privilege role.

Three independent bounds, because each one covers a failure the others do not:

- **A read-only transaction on the agent role.** The role itself holds
  ``SELECT`` only, so a write is refused by PostgreSQL even if a future
  compiler bug emitted one. The transaction default is set again here, so a
  plan compiled by mistake still cannot write.
- **A server-side statement timeout.** Set per transaction with
  ``set_config``, so a plan that is more expensive than expected is cancelled
  by the server rather than by a Python timer that would leave the query
  running.
- **A byte budget on the returned rows.** The executor measures what it is
  about to hand back and refuses rather than materializing an unbounded result
  in the agent's memory.

This module imports ``src.core.db`` for the agent session factory and nothing
from ``src.api``, ``src.agents``, or the tracing layer.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, ResourceClosedError, StatementError

from src.core.config import settings
from src.core.db import agent_session_factory
from src.services.query.compiler import CompiledQuery


class QueryExecutionError(RuntimeError):
    """A compiled query could not be run. The message is safe to show."""


class QueryTimeoutError(QueryExecutionError):
    """The server cancelled a statement that ran past its budget."""


class ResultTooLargeError(QueryExecutionError):
    """The rows returned would exceed the configured byte budget."""


def execution_limits() -> dict[str, int]:
    query = settings.config_yaml.get("agent", {}).get("query")
    if not isinstance(query, dict):
        raise ValueError("Missing 'agent.query' section in config/settings.yaml")

    def positive_int(name: str) -> int:
        value = query.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"agent.query.{name} must be a positive integer in config/settings.yaml")
        return value

    return {
        "statement_timeout_ms": positive_int("statement_timeout_ms"),
        "max_result_bytes": positive_int("max_result_bytes"),
    }


class BoundedExecutor:
    """Runs a compiled query and returns each statement's rows by role."""

    def __init__(self, session_factory: Any = None, limits: dict[str, int] | None = None) -> None:
        self._session_factory = session_factory or agent_session_factory
        self._limits = limits or execution_limits()

    def run(self, compiled: CompiledQuery) -> dict[str, list[dict[str, Any]]]:
        """Execute every statement in one read-only transaction."""
        try:
            with self._session_factory() as session:
                # Three settings, all before the first data statement:
                # transaction_read_only for the transaction about to run,
                # default_transaction_read_only so a later transaction cannot
                # write either, and a server-side statement timeout so an
                # over-expensive plan is cancelled by PostgreSQL rather than by
                # a Python timer. The results are consumed so no cursor is left
                # open.
                session.execute(
                    text("SELECT set_config('transaction_read_only', 'on', true)")
                ).scalar()
                session.execute(
                    text("SELECT set_config('default_transaction_read_only', 'on', true)")
                ).scalar()
                session.execute(
                    text("SELECT set_config('statement_timeout', :ms, true)"),
                    {"ms": str(self._limits["statement_timeout_ms"])},
                ).scalar()
                results: dict[str, list[dict[str, Any]]] = {}
                budget = self._limits["max_result_bytes"]
                spent = 0
                for statement in compiled.statements:
                    rows = [dict(row) for row in session.execute(text(statement.sql), statement.params).mappings().all()]
                    spent += _row_bytes(rows)
                    if spent > budget:
                        raise ResultTooLargeError(
                            "The query returned more data than this agent is allowed to read. "
                            "Ask for a narrower question."
                        )
                    results[statement.role] = rows
                return results
        except QueryExecutionError:
            raise
        except (OperationalError, DBAPIError, StatementError) as exc:
            if _is_timeout(exc):
                raise QueryTimeoutError(
                    "The query took too long and was stopped. Ask for a narrower question."
                ) from exc
            raise QueryExecutionError(
                "The database could not answer that question. Try a narrower one."
            ) from exc
        except ResourceClosedError as exc:
            # A statement that returns no rows at all, such as a write, means
            # the plan was not produced by the compiler. Refuse it rather than
            # reporting an empty answer for a mutation.
            raise QueryExecutionError(
                "That request was refused before it ran. Try a narrower question."
            ) from exc


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
