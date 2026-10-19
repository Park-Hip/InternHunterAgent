"""Unit tests for the bounded read executor (#702).

The mock pins the statement sequence one bounded read must issue: the
read-only repeatable-read transaction, the per-transaction statement timeout,
the bounded fetch, and - only when the fetch filled its limit - the companion
count. The real-database behavior (read-only refusal, the timeout firing, the
byte budget, the count's value) is proven in test_executor_bounds.py.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from psycopg.errors import InsufficientPrivilege, UndefinedColumn
from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.query.executor import (
    ExecutorError,
    PermissionDeniedError,
    QueryTimeoutError,
    ResultTooLargeError,
    UndefinedColumnError,
    execute_bounded_select,
    execution_limits,
)

BASE_SQL = "SELECT id, title FROM clean_jobs WHERE is_internship = true"


class _UndefinedColumnWithPrimary(UndefinedColumn):
    """A driver error carrying PostgreSQL's primary message, as on the wire."""

    @property
    def diag(self) -> SimpleNamespace:
        return SimpleNamespace(message_primary='column "remote" does not exist')


class _UndefinedColumnWithoutPrimary(UndefinedColumn):
    """A driver error with no server diagnostic attached."""

    diag = None


class _PrivilegeDeniedOnCleanJobs(InsufficientPrivilege):
    """SQLSTATE 42501 whose diagnostic names the table, as on the wire."""

    @property
    def diag(self) -> SimpleNamespace:
        return SimpleNamespace(table_name="clean_jobs")


class _PrivilegeDeniedByMessage(InsufficientPrivilege):
    """SQLSTATE 42501 with no diagnostic; only the message names the table."""

    diag = None


class _PrivilegeDeniedElsewhere(InsufficientPrivilege):
    """SQLSTATE 42501 about another object, which must stay unavailable."""

    diag = None


def _mock_session(mock_agent_session_factory: MagicMock) -> MagicMock:
    session = mock_agent_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return session


def _result(
    columns: list[str], rows: list[list], total: int = 0
) -> MagicMock:
    result = MagicMock()
    result.keys.return_value = list(columns)
    result.all.return_value = list(rows)
    result.scalar.return_value = total
    # The companion count reads a single value with scalar_one().
    result.scalar_one.return_value = total
    return result


def _statements(session: MagicMock) -> list[str]:
    return [str(call.args[0]) for call in session.execute.call_args_list]


class ExecuteBoundedSelectTests(unittest.TestCase):
    @patch("src.services.query.executor.agent_session_factory")
    def test_applies_transaction_bounds_before_the_bounded_fetch(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _result(
            ["id", "title"], [[1, "Data Analyst"], [2, "ML Intern"]]
        )

        bounded = execute_bounded_select(BASE_SQL, 20)

        statements = _statements(session)
        self.assertEqual(
            statements[0],
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        )
        self.assertEqual(
            statements[1], "SELECT set_config('statement_timeout', :ms, true)"
        )
        self.assertEqual(
            session.execute.call_args_list[1].args[1],
            {"ms": str(execution_limits()["statement_timeout_ms"])},
        )
        self.assertEqual(statements[2], f"{BASE_SQL} LIMIT 20")
        self.assertEqual(
            bounded.columns, ["id", "title"]
        )
        self.assertEqual(bounded.rows, [[1, "Data Analyst"], [2, "ML Intern"]])
        self.assertEqual(bounded.total_rows, 2)

    @patch("src.services.query.executor.agent_session_factory")
    def test_counts_the_real_total_when_the_fetch_fills_its_limit(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _result(
            ["id"], [[index] for index in range(20)], total=161
        )

        bounded = execute_bounded_select(BASE_SQL, 20)

        statements = _statements(session)
        self.assertEqual(len(statements), 4)
        self.assertEqual(statements[3], f"SELECT count(*) FROM ({BASE_SQL}) AS q")
        self.assertEqual(bounded.rows, [[index] for index in range(20)])
        self.assertEqual(bounded.total_rows, 161)

    @patch("src.services.query.executor.agent_session_factory")
    def test_skips_the_count_when_the_fetch_is_short(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _result(["id"], [[1], [2]])

        bounded = execute_bounded_select(BASE_SQL, 20)

        self.assertEqual(len(_statements(session)), 3)
        self.assertEqual(bounded.total_rows, 2)

    @patch("src.services.query.executor.agent_session_factory")
    def test_applies_the_page_offset_after_the_limit(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _result(
            ["id"], [[index] for index in range(21, 26)], total=161
        )

        bounded = execute_bounded_select(BASE_SQL, 5, 20)

        statements = _statements(session)
        self.assertEqual(statements[2], f"{BASE_SQL} LIMIT 5 OFFSET 20")
        self.assertEqual(bounded.rows, [[index] for index in range(21, 26)])
        self.assertEqual(bounded.total_rows, 161)

    @patch("src.services.query.executor.agent_session_factory")
    def test_counts_when_the_offset_is_non_zero_even_if_the_page_is_short(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        # A last page has fewer rows than the limit, but its total is still the
        # whole match set, not the page length. The count must run.
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _result(["id"], [[21], [22], [23]], total=23)

        bounded = execute_bounded_select(BASE_SQL, 20, 20)

        statements = _statements(session)
        self.assertEqual(len(statements), 4)
        self.assertEqual(statements[3], f"SELECT count(*) FROM ({BASE_SQL}) AS q")
        self.assertEqual(bounded.rows, [[21], [22], [23]])
        self.assertEqual(bounded.total_rows, 23)

    @patch("src.services.query.executor.agent_session_factory")
    def test_keeps_the_columns_of_an_empty_result(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _result(["id", "title"], [])

        bounded = execute_bounded_select(BASE_SQL, 20)

        self.assertEqual(bounded.columns, ["id", "title"])
        self.assertEqual(bounded.rows, [])
        self.assertEqual(bounded.total_rows, 0)
        self.assertEqual(len(_statements(session)), 3)

    @patch("src.services.query.executor.execution_limits")
    @patch("src.services.query.executor.agent_session_factory")
    def test_refuses_a_result_above_the_byte_budget_before_counting(
        self,
        mock_agent_session_factory: MagicMock,
        mock_execution_limits: MagicMock,
    ) -> None:
        mock_execution_limits.return_value = {
            "statement_timeout_ms": 2000,
            "max_result_bytes": 16,
        }
        session = _mock_session(mock_agent_session_factory)
        # A full window, so only the budget can stop the companion count.
        session.execute.return_value = _result(["title"], [["a title too long"]], total=161)

        with self.assertRaises(ResultTooLargeError):
            execute_bounded_select(BASE_SQL, 1)

        self.assertEqual(len(_statements(session)), 3)

    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_an_undefined_column_to_its_postgres_message(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            OperationalError(
                "SELECT remote FROM clean_jobs",
                {},
                _UndefinedColumnWithPrimary('column "remote" does not exist'),
            ),
        ]

        with self.assertRaises(UndefinedColumnError) as raised:
            execute_bounded_select(BASE_SQL, 20)

        self.assertEqual(
            raised.exception.message_primary, 'column "remote" does not exist'
        )

    @patch("src.services.query.executor.agent_session_factory")
    def test_falls_back_when_the_driver_error_has_no_primary_message(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            OperationalError(
                "SELECT remote FROM clean_jobs",
                {},
                _UndefinedColumnWithoutPrimary('column "remote" does not exist'),
            ),
        ]

        with self.assertRaises(UndefinedColumnError) as raised:
            execute_bounded_select(BASE_SQL, 20)

        self.assertEqual(raised.exception.message_primary, "unknown column")

    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_a_clean_jobs_privilege_denial_to_permission_denied_error(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            DBAPIError(
                "SELECT * FROM clean_jobs",
                {},
                _PrivilegeDeniedOnCleanJobs(
                    "permission denied for table clean_jobs"
                ),
            ),
        ]

        with self.assertRaises(PermissionDeniedError):
            execute_bounded_select(BASE_SQL, 20)

    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_a_privilege_denial_named_only_by_its_message(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            DBAPIError(
                "SELECT source FROM clean_jobs",
                {},
                _PrivilegeDeniedByMessage(
                    "permission denied for table clean_jobs"
                ),
            ),
        ]

        with self.assertRaises(PermissionDeniedError):
            execute_bounded_select(BASE_SQL, 20)

    @patch("src.services.query.executor.agent_session_factory")
    def test_leaves_a_privilege_denial_on_another_object_unavailable(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            DBAPIError(
                "SELECT 1",
                {},
                _PrivilegeDeniedElsewhere("permission denied for schema public"),
            ),
        ]

        with self.assertRaises(ExecutorError) as raised:
            execute_bounded_select(BASE_SQL, 20)

        self.assertNotIsInstance(raised.exception, PermissionDeniedError)

    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_statement_timeout_to_query_timeout_error(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            OperationalError(
                "SELECT pg_sleep(3)",
                {},
                Exception("canceling statement due to statement timeout"),
            ),
        ]

        with self.assertRaises(QueryTimeoutError) as raised:
            execute_bounded_select(BASE_SQL, 20)

        self.assertEqual(
            raised.exception.timeout_ms, execution_limits()["statement_timeout_ms"]
        )
        self.assertEqual(
            str(raised.exception),
            "statement exceeded the"
            f" {execution_limits()['statement_timeout_ms']} ms limit",
        )

    @patch("src.services.query.executor.agent_session_factory")
    def test_raises_executor_error_on_operational_error(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            OperationalError("SELECT 1", {}, Exception("connection refused")),
        ]

        with self.assertRaises(ExecutorError) as raised:
            execute_bounded_select(BASE_SQL, 20)

        self.assertIn("connection refused", str(raised.exception))

    @patch("src.services.query.executor.agent_session_factory")
    def test_raises_executor_error_on_dbapi_error(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            DBAPIError("SELECT 1", {}, Exception("db failure")),
        ]

        with self.assertRaises(ExecutorError):
            execute_bounded_select(BASE_SQL, 20)

    @patch("src.services.query.executor.agent_session_factory")
    def test_closes_the_session_on_success(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _result([], [])

        execute_bounded_select(BASE_SQL, 20)

        session.__exit__.assert_called_once()

    @patch("src.services.query.executor.agent_session_factory")
    def test_closes_the_session_on_failure(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            _result([], []),
            _result([], []),
            OperationalError("SELECT 1", {}, Exception("boom")),
        ]

        with self.assertRaises(ExecutorError):
            execute_bounded_select(BASE_SQL, 20)

        session.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
