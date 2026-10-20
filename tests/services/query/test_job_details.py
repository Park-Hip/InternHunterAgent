"""Unit tests for the bounded job-details read.

The read shares the executor's bounded session with the listing tool (#702 E6),
so the statement order, the byte budget, and the error mapping are asserted
here at the seam the details path uses. The column contract guard stays: this
projection is the application contract in `src/core/column_contract.py`.
"""

import re
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.column_contract import HIDDEN_COLUMN_NAMES, VISIBLE_COLUMN_NAMES
from src.services.query.executor import (
    ExecutorError,
    QueryTimeoutError,
    ResultTooLargeError,
    execution_limits,
)
from src.services.query.job_details import fetch_job_details


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


def _detail_result(rows: list[dict]) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    return result


def _statements(session: MagicMock) -> list[str]:
    return [str(call.args[0]) for call in session.execute.call_args_list]


class FetchJobDetailsTests(unittest.TestCase):
    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_result_rows_to_list_of_dicts_incl_description(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _detail_result(
            [{"id": 1, "title": "Data Analyst", "description": "full text here"}]
        )

        rows = fetch_job_details([1])

        self.assertEqual(
            rows,
            [{"id": 1, "title": "Data Analyst", "description": "full text here"}],
        )

    def test_empty_ids_returns_empty_list_without_hitting_db(self) -> None:
        with patch("src.services.query.executor.agent_session_factory") as mock_factory:
            rows = fetch_job_details([])

            self.assertEqual(rows, [])
            mock_factory.assert_not_called()

    @patch("src.services.query.executor.agent_session_factory")
    def test_applies_the_transaction_bounds_before_the_read(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _detail_result([])

        fetch_job_details([1])

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
        self.assertIn("FROM clean_jobs WHERE id = ANY(:ids)", statements[2])
        self.assertEqual(len(statements), 3)

    @patch("src.services.query.executor.agent_session_factory")
    def test_ids_are_passed_as_bound_param_not_interpolated(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _detail_result([])

        fetch_job_details([1, 2, 3])

        read_call = session.execute.call_args_list[2]
        statement, params = read_call.args
        self.assertNotIn("1", str(statement))
        self.assertEqual(params, {"ids": [1, 2, 3]})

    @patch("src.services.query.executor.agent_session_factory")
    def test_selects_exactly_the_schema_context_column_contract(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        """Guard: the projection must equal the application column contract.

        The contract tells the model that unlisted columns do not exist. If this
        query ever widens (a SELECT * regression, or a new column added to the table
        without updating the contract), the agent silently gains vocabulary the
        prompt denies it. Both directions are asserted: a dropped column and a leak.
        """
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _detail_result([])

        fetch_job_details([1])

        statement = str(session.execute.call_args_list[2].args[0])
        selected = _selected_columns(statement)

        self.assertNotIn("*", statement, "wildcard SELECT leaks every column to the agent")

        for column in VISIBLE_COLUMN_NAMES:
            self.assertIn(column, selected, f"contract column {column} is not selected")

        for column in HIDDEN_COLUMN_NAMES:
            self.assertNotIn(column, selected, f"out-of-contract column {column} leaked")

        # Catches anything outside both lists too (e.g. a column added to the table later).
        self.assertEqual(selected, set(VISIBLE_COLUMN_NAMES))

    @patch("src.services.query.job_details.execution_limits")
    @patch("src.services.query.executor.agent_session_factory")
    def test_refuses_a_result_above_the_byte_budget(
        self,
        mock_agent_session_factory: MagicMock,
        mock_execution_limits: MagicMock,
    ) -> None:
        mock_execution_limits.return_value = {
            "statement_timeout_ms": 2000,
            "max_result_bytes": 16,
        }
        session = _mock_session(mock_agent_session_factory)
        session.execute.return_value = _detail_result(
            [{"id": 1, "description": "a description far longer than sixteen bytes"}]
        )

        with self.assertRaises(ResultTooLargeError):
            fetch_job_details([1])

    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_a_driver_failure_to_an_executor_error(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            MagicMock(),
            MagicMock(),
            OperationalError("SELECT 1", {}, Exception("connection refused")),
        ]

        with self.assertRaises(ExecutorError):
            fetch_job_details([1])

    @patch("src.services.query.executor.agent_session_factory")
    def test_maps_a_statement_timeout(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            MagicMock(),
            MagicMock(),
            OperationalError(
                "SELECT description FROM clean_jobs WHERE id = ANY(:ids)",
                {},
                Exception("canceling statement due to statement timeout"),
            ),
        ]

        with self.assertRaises(QueryTimeoutError) as raised:
            fetch_job_details([1])

        self.assertEqual(
            raised.exception.timeout_ms, execution_limits()["statement_timeout_ms"]
        )

    @patch("src.services.query.executor.agent_session_factory")
    def test_raises_executor_error_on_dbapi_error(
        self, mock_agent_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_agent_session_factory)
        session.execute.side_effect = [
            MagicMock(),
            MagicMock(),
            DBAPIError("SELECT 1", {}, Exception("db failure")),
        ]

        with self.assertRaises(ExecutorError):
            fetch_job_details([1])


if __name__ == "__main__":
    unittest.main()
