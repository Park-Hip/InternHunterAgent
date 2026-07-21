import re
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.query.executor import ExecutorError
from src.services.query.job_details import fetch_job_details


CONTRACT_COLUMNS = (
    "id",
    "title",
    "company",
    "role",
    "description",
    "tech_stack",
    "location",
    "source_url",
    "job_level",
    "listing_expires_on",
    "created_on",
    "is_internship",
    "salary_min",
    "salary_max",
    "salary_currency",
    "is_salary_negotiable",
)

# Present in clean_jobs but deliberately outside prompts.schema_context.
OUT_OF_CONTRACT_COLUMNS = (
    "is_active",
    "first_seen_at",
    "last_seen_at",
    "posted_date",
    "source",
    "external_id",
)


def _selected_columns(statement: str) -> set[str]:
    """Return the whole column tokens the SELECT projects.

    Whole-token parsing, not substring matching: "source" is a substring of the
    allowlisted "source_url" and "external_id" of "id", so a naive assertNotIn
    against the raw SQL would fail on correct code and invite weakening the guard.
    """
    match = re.search(r"SELECT\s+(.*?)\s+FROM\s", statement, re.IGNORECASE | re.DOTALL)
    if match is None:
        raise AssertionError(f"Could not parse a SELECT ... FROM clause from: {statement!r}")
    return {token.strip() for token in match.group(1).split(",")}


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
    def test_selects_exactly_the_schema_context_column_contract(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Guard: the projection must mirror config/prompts.yaml -> prompts.schema_context.

        schema_context tells the model that unlisted columns do not exist. If this
        query ever widens (a SELECT * regression, or a new column added to the table
        without updating schema_context), the agent silently gains vocabulary the
        prompt denies it. Both directions are asserted: a dropped column and a leak.
        """
        session = _mock_session(mock_session_factory)
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.return_value = mock_result

        fetch_job_details([1])

        statement = str(session.execute.call_args_list[1].args[0])
        selected = _selected_columns(statement)

        self.assertNotIn("*", statement, "wildcard SELECT leaks every column to the agent")

        for column in CONTRACT_COLUMNS:
            self.assertIn(column, selected, f"contract column {column} is not selected")

        for column in OUT_OF_CONTRACT_COLUMNS:
            self.assertNotIn(column, selected, f"out-of-contract column {column} leaked")

        # Catches anything outside both lists too (e.g. a column added to the table later).
        self.assertEqual(selected, set(CONTRACT_COLUMNS))

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
