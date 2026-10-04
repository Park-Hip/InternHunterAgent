from __future__ import annotations

import unittest
from unittest.mock import patch

from src.services.query.executor import ExecutorError


class GetJobDetailsBehaviorTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_happy_path_returns_plain_string_with_description(
        self, mock_fetch_job_details
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.return_value = [
            {"id": 1, "title": "Data Analyst Intern", "description": "Full description text"},
        ]

        result = await run_get_job_details([1])

        self.assertIsInstance(result, str)
        self.assertIn("Data Analyst Intern", result)
        self.assertIn("Full description text", result)

    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_the_surrogate_key_is_not_rendered_in_the_detail_answer(
        self, mock_fetch_job_details
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.return_value = [
            {"id": 18, "title": "AI Expert", "company": "Viettel High Tech", "location": "Hanoi"},
        ]

        result = await run_get_job_details([18])

        self.assertNotIn("id=", result)
        self.assertNotIn("id=18", result)

    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_every_other_stored_value_is_still_reproduced_exactly(
        self, mock_fetch_job_details
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.return_value = [
            {
                "id": 18,
                "title": "AI Expert",
                "company": "Viettel High Tech",
                "location": "Hanoi",
                "source_url": "https://example.test/ai-expert",
                "is_salary_negotiable": False,
            },
        ]

        result = await run_get_job_details([18])

        for column, value in (
            ("title", "AI Expert"),
            ("company", "Viettel High Tech"),
            ("location", "Hanoi"),
            ("source_url", "https://example.test/ai-expert"),
            ("is_salary_negotiable", "False"),
        ):
            self.assertIn(f"{column}={value}", result)

    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_the_structured_artifact_keeps_the_key_for_chaining(
        self, mock_fetch_job_details
    ) -> None:
        from src.agents.tools.get_job_details import _table_from_detail_rows

        mock_fetch_job_details.return_value = [{"id": 18, "title": "AI Expert"}]

        table = _table_from_detail_rows([{"id": 18, "title": "AI Expert"}])

        self.assertIn("id", table.columns)
        self.assertEqual(table.rows, [[18, "AI Expert"]])

    @patch("src.agents.tools.get_job_details.load_max_detail_ids")
    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_capped_detail_answer_still_hides_the_key_for_every_row(
        self, mock_fetch_job_details, mock_load_max_detail_ids
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_load_max_detail_ids.return_value = 2
        mock_fetch_job_details.return_value = [
            {"id": 1, "title": "Intern A"},
            {"id": 2, "title": "Intern B"},
        ]

        result = await run_get_job_details([1, 2, 3])

        self.assertIn("2 trong số 3", result)
        self.assertIn("Intern A", result)
        self.assertIn("Intern B", result)
        self.assertNotIn("id=", result)

    @patch("src.agents.tools.get_job_details.load_max_detail_ids")
    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_id_cap_holds_and_notice_present(
        self, mock_fetch_job_details, mock_load_max_detail_ids
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_load_max_detail_ids.return_value = 2
        mock_fetch_job_details.return_value = [
            {"id": 1, "title": "Intern A"},
            {"id": 2, "title": "Intern B"},
        ]

        result = await run_get_job_details([1, 2, 3])

        mock_fetch_job_details.assert_called_once_with([1, 2])
        self.assertIn("2 trong số 3", result)

    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_missing_id_degrades_gracefully(self, mock_fetch_job_details) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.return_value = []

        result = await run_get_job_details([999999])

        self.assertIn("Không tìm thấy tin tuyển dụng nào với mã 999999", result)

    async def test_empty_ids_returns_guidance_without_hitting_db(self) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        with patch("src.agents.tools.get_job_details.fetch_job_details") as mock_fetch_job_details:
            result = await run_get_job_details([])

            self.assertIsInstance(result, str)
            self.assertEqual(
                result,
                "Vui lòng chỉ định mã tin tuyển dụng bạn muốn xem chi tiết hoặc tìm kiếm "
                "trước bằng query_clean_jobs.",
            )
            mock_fetch_job_details.assert_not_called()

    @patch("src.agents.tools.get_job_details.logger")
    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_executor_error_returns_safe_string_without_leaking(
        self, mock_fetch_job_details, mock_logger
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.side_effect = ExecutorError("connection refused")

        result = await run_get_job_details([1])

        self.assertIn("lỗi cơ sở dữ liệu", result)
        self.assertNotIn("connection refused", result)

    @patch("src.agents.tools.get_job_details.logger")
    @patch("src.agents.tools.get_job_details.fetch_job_details")
    async def test_executor_error_is_logged(
        self, mock_fetch_job_details, mock_logger
    ) -> None:
        from src.agents.tools.get_job_details import run_get_job_details

        mock_fetch_job_details.side_effect = ExecutorError("connection refused")

        await run_get_job_details([1])

        mock_logger.error.assert_called_once()
        self.assertEqual(mock_logger.error.call_args.args[0], "get_job_details.db_error")
        self.assertIn("connection refused", mock_logger.error.call_args.kwargs["error"])


if __name__ == "__main__":
    unittest.main()