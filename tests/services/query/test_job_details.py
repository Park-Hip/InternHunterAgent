import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.query.executor import ExecutorError
from src.services.query.job_details import fetch_job_details


def _mock_session(mock_session_factory: MagicMock) -> MagicMock:
    session = mock_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return session


class FetchJobDetailsTests(unittest.TestCase):
    @patch("src.services.query.job_details.session_factory")
    def test_maps_result_rows_to_list_of_dicts_incl_description(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"id": 1, "title": "Data Analyst", "description": "full text here"},
        ]
        session.execute.return_value = mock_result

        rows = fetch_job_details([1])

        self.assertEqual(
            rows,
            [{"id": 1, "title": "Data Analyst", "description": "full text here"}],
        )

    def test_empty_ids_returns_empty_list_without_hitting_db(self) -> None:
        with patch("src.services.query.job_details.session_factory") as mock_session_factory:
            rows = fetch_job_details([])

            self.assertEqual(rows, [])
            mock_session_factory.assert_not_called()

    @patch("src.services.query.job_details.session_factory")
    def test_sets_read_only_transaction_before_running_query(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.return_value = mock_result

        fetch_job_details([1])

        first_statement = str(session.execute.call_args_list[0].args[0])
        self.assertIn("READ ONLY", first_statement.upper())

    @patch("src.services.query.job_details.session_factory")
    def test_ids_are_passed_as_bound_param_not_interpolated(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.return_value = mock_result

        fetch_job_details([1, 2, 3])

        second_call = session.execute.call_args_list[1]
        statement, params = second_call.args
        self.assertNotIn("1", str(statement))
        self.assertEqual(params, {"ids": [1, 2, 3]})

    @patch("src.services.query.job_details.session_factory")
    def test_raises_executor_error_on_operational_error(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("connection refused"))

        with self.assertRaises(ExecutorError):
            fetch_job_details([1])

    @patch("src.services.query.job_details.session_factory")
    def test_raises_executor_error_on_dbapi_error(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = DBAPIError("SELECT 1", {}, Exception("db failure"))

        with self.assertRaises(ExecutorError):
            fetch_job_details([1])


if __name__ == "__main__":
    unittest.main()
