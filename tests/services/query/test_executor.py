import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.query.executor import ExecutorError, execute_validated_sql


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
