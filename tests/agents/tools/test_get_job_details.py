"""Unit tests for the facts-only ``get_job_details`` behavior (#702).

The tool returns ``JobDetailsResult`` and raises ``ToolFailure``; it never
composes a sentence and never renders a key=value line, so the tests assert the
request order, the cap, the JSON-native values, and the failure vocabulary.
"""

from __future__ import annotations

import datetime as dt
import decimal
import unittest
from unittest.mock import MagicMock, patch

from src.agents.tools.failures import ToolFailure
from src.services.query.executor import (
    ExecutorError,
    QueryTimeoutError,
    ResultTooLargeError,
    UndefinedColumnError,
)
from src.services.query.models import JobDetailsResult


class GetJobDetailsBehaviorTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_fetches_details_in_request_order(
        self, mock_fetch_job_details: MagicMock
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.return_value = [
            {"id": 2, "title": "Intern B"},
            {"id": 1, "title": "Intern A"},
        ]

        result = await run_get_job_details([1, 2])

        self.assertEqual(
            result,
            JobDetailsResult(
                jobs=[{"id": 1, "title": "Intern A"}, {"id": 2, "title": "Intern B"}],
                not_found=[],
                not_fetched=[],
            ),
        )
        mock_fetch_job_details.assert_called_once_with([1, 2])

    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_duplicate_ids_are_fetched_once_keeping_the_first_occurrence(
        self, mock_fetch_job_details: MagicMock
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.return_value = [{"id": 2, "title": "Intern B"}]

        result = await run_get_job_details([2, 1, 2])

        mock_fetch_job_details.assert_called_once_with([2, 1])
        self.assertEqual(result.jobs, [{"id": 2, "title": "Intern B"}])

    @patch("src.agents.tools.get_job_details.load_max_detail_ids")
    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_ids_over_the_cap_are_reported_not_fetched(
        self, mock_fetch_job_details: MagicMock, mock_load_max_detail_ids: MagicMock
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_load_max_detail_ids.return_value = 2
        mock_fetch_job_details.return_value = [{"id": 1, "title": "Intern A"}]

        result = await run_get_job_details([1, 2, 3])

        mock_fetch_job_details.assert_called_once_with([1, 2])
        self.assertEqual(result.not_fetched, [3])
        self.assertEqual(result.not_found, [2])

    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_a_missing_id_is_reported_not_found(
        self, mock_fetch_job_details: MagicMock
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.return_value = []

        result = await run_get_job_details([999999])

        self.assertEqual(result.jobs, [])
        self.assertEqual(result.not_found, [999999])
        self.assertEqual(result.not_fetched, [])

    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_values_are_shaped_into_json_native_types(
        self, mock_fetch_job_details: MagicMock
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.return_value = [
            {
                "id": 7,
                "created_on": dt.date(2026, 10, 18),
                "salary_min": decimal.Decimal("17500625"),
                "salary_currency": None,
            }
        ]

        result = await run_get_job_details([7])

        self.assertEqual(
            result.jobs,
            [
                {
                    "id": 7,
                    "created_on": "2026-10-18",
                    "salary_min": 17500625,
                    "salary_currency": None,
                }
            ],
        )

    async def test_empty_ids_return_an_empty_result_without_a_read(self) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        with patch(
            "src.services.query.executor.agent_session_factory"
        ) as mock_session_factory:
            result = await run_get_job_details([])

        self.assertEqual(
            result, JobDetailsResult(jobs=[], not_found=[], not_fetched=[])
        )
        mock_session_factory.assert_not_called()


class GetJobDetailsFailureTests(unittest.IsolatedAsyncioTestCase):
    """Each failure kind carries its exact model-facing detail."""

    @patch("src.agents.tools.get_job_details.logger")
    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def _fail(self, side_effect, mock_fetch_job_details, mock_logger):
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.side_effect = side_effect
        with self.assertRaises(ToolFailure) as raised:
            await run_get_job_details([1])
        return raised.exception, mock_logger

    async def test_an_unknown_column_failure_names_the_column(self) -> None:
        failure, logger = await self._fail(
            UndefinedColumnError('column "remote" does not exist')
        )

        self.assertEqual(failure.kind, "unknown_column")
        self.assertEqual(failure.detail, 'column "remote" does not exist')
        self.assertEqual(logger.warning.call_args.args[0], "get_job_details.unknown_column")

    async def test_a_timeout_states_the_limit(self) -> None:
        failure, logger = await self._fail(QueryTimeoutError(2000))

        self.assertEqual(failure.kind, "timeout")
        self.assertEqual(failure.detail, "statement exceeded the 2000 ms limit")
        self.assertEqual(logger.warning.call_args.args[0], "get_job_details.timeout")

    async def test_a_result_over_the_byte_budget(self) -> None:
        failure, logger = await self._fail(
            ResultTooLargeError(
                "The query returned more data than this agent is allowed to read."
            )
        )

        self.assertEqual(failure.kind, "too_large")
        self.assertEqual(
            failure.detail, "result exceeds the byte budget; select fewer columns"
        )
        self.assertEqual(logger.warning.call_args.args[0], "get_job_details.too_large")

    async def test_an_unavailable_database_never_carries_the_driver_message(self) -> None:
        failure, logger = await self._fail(
            ExecutorError("Failed to execute query: connection refused to db.internal")
        )

        self.assertEqual(failure.kind, "unavailable")
        self.assertEqual(failure.detail, "the database could not run the query")
        self.assertNotIn("db.internal", str(failure))
        self.assertEqual(logger.error.call_args.args[0], "get_job_details.db_error")


if __name__ == "__main__":
    unittest.main()
