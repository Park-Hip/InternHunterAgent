import unittest
from unittest.mock import MagicMock, patch

from psycopg.errors import UndefinedColumn
from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.query.executor import (
    ExecutorError,
    QueryTimeoutError,
    ResultTooLargeError,
    UndefinedColumnError,
    execute_validated_sql,
    execution_limits,
)


def _mock_session(mock_session_factory: MagicMock) -> MagicMock:
    session = mock_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return session


class ExecuteValidatedSqlTests(unittest.TestCase):
    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_result_rows_to_list_of_dicts(self, mock_agent_session_factory: MagicMock) -> None:
        session = _mock_session(mock_agent_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"title": "Data Analyst", "company": "Acme"},
            {"title": "ML Intern", "company": "Globex"},
        ]
        session.execute.return_value = mock_result

        rows = execute_validated_sql("SELECT title, company FROM clean_jobs")

        self.assertEqual(
            rows,
            [
                {"title": "Data Analyst", "company": "Acme"},
                {"title": "ML Intern", "company": "Globex"},
            ],
        )

    @patch("src.services.query.executor.agent_session_factory")
    def test_sets_read_only_transaction_before_running_query(self, mock_agent_session_factory: MagicMock) -> None:
        session = _mock_session(mock_agent_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.return_value = mock_result

        execute_validated_sql("SELECT title FROM clean_jobs")

        first_statement = str(session.execute.call_args_list[0].args[0])
        self.assertIn("READ ONLY", first_statement.upper())

    @patch("src.services.query.executor.agent_session_factory")
    def test_sets_statement_timeout_from_config_before_running_query(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.return_value = mock_result

        execute_validated_sql("SELECT title FROM clean_jobs")

        timeout_call = session.execute.call_args_list[1]
        self.assertIn("set_config('statement_timeout'", str(timeout_call.args[0]))
        self.assertEqual(
            timeout_call.args[1],
            {"ms": str(execution_limits()["statement_timeout_ms"])},
        )

    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_statement_timeout_to_query_timeout_error(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.side_effect = [
            mock_result,
            mock_result,
            OperationalError(
                "SELECT pg_sleep(3)", {}, Exception("canceling statement due to statement timeout")
            ),
        ]

        with self.assertRaises(QueryTimeoutError):
            execute_validated_sql("SELECT title FROM clean_jobs")

    @patch("src.services.query.executor.execution_limits")
    @patch("src.services.query.executor.agent_session_factory")
    def test_refuses_result_above_byte_budget(
        self, mock_agent_session_factory: MagicMock, mock_execution_limits: MagicMock
    ) -> None:
        mock_execution_limits.return_value = {
            "statement_timeout_ms": 2000,
            "max_result_bytes": 16,
        }
        session = _mock_session(mock_agent_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [{"title": "a title too long"}]
        session.execute.return_value = mock_result

        with self.assertRaises(ResultTooLargeError):
            execute_validated_sql("SELECT title FROM clean_jobs")

    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_undefined_column_before_the_timeout_check(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = OperationalError(
            "SELECT missing FROM clean_jobs",
            {},
            UndefinedColumn("column \"missing\" does not exist"),
        )

        with self.assertRaises(UndefinedColumnError):
            execute_validated_sql("SELECT missing FROM clean_jobs")

    @patch("src.services.query.executor.agent_session_factory")
    def test_raises_executor_error_on_operational_error(self, mock_agent_session_factory: MagicMock) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("connection refused"))

        with self.assertRaises(ExecutorError):
            execute_validated_sql("SELECT title FROM clean_jobs")

    @patch("src.services.query.executor.agent_session_factory")
    def test_raises_executor_error_on_dbapi_error(self, mock_agent_session_factory: MagicMock) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = DBAPIError("SELECT 1", {}, Exception("db failure"))

        with self.assertRaises(ExecutorError):
            execute_validated_sql("SELECT title FROM clean_jobs")

    @patch("src.services.query.executor.agent_session_factory")
    def test_session_is_closed_on_failure(self, mock_agent_session_factory: MagicMock) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("boom"))

        with self.assertRaises(ExecutorError):
            execute_validated_sql("SELECT title FROM clean_jobs")

        session.__exit__.assert_called_once()

    @patch("src.services.query.executor.agent_session_factory")
    def test_session_is_closed_on_success(self, mock_agent_session_factory: MagicMock) -> None:
        session = _mock_session(mock_agent_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.return_value = mock_result

        execute_validated_sql("SELECT title FROM clean_jobs")

        session.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
