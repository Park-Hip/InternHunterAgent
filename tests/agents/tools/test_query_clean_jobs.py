from __future__ import annotations

import unittest
from unittest.mock import patch

from src.services.query.executor import ExecutorError
from src.services.query.models import ValidationResult


class QueryCleanJobsToolTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_happy_path_returns_formatted_answer(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT title, company FROM clean_jobs LIMIT 5"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title, company FROM clean_jobs LIMIT 5"
        )
        mock_execute_validated_sql.return_value = [
            {"title": "Data Analyst Intern", "company": "Acme"},
            {"title": "ML Intern", "company": "Globex"},
        ]

        result = await query_clean_jobs.ainvoke({"question": "What internships are available?"})

        self.assertIn("Found 2 result(s)", result)
        self.assertIn("title", result)
        self.assertIn("company", result)
        self.assertIn("Acme", result)
        self.assertIn("Globex", result)

    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_no_rows_returns_no_results_message(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs WHERE company = 'Nope'"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs WHERE company = 'Nope'"
        )
        mock_execute_validated_sql.return_value = []

        result = await query_clean_jobs.ainvoke({"question": "Any jobs at Nope?"})

        self.assertIn("No matching internship job postings", result)

    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_validator_rejection_returns_refusal_string_without_executing(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "DROP TABLE clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=False, sql="DROP TABLE clean_jobs", reason="Only SELECT statements are allowed"
        )

        result = await query_clean_jobs.ainvoke({"question": "Delete everything"})

        self.assertIn("I can't run that query", result)
        self.assertIn("Only SELECT statements are allowed", result)
        mock_execute_validated_sql.assert_not_called()

    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_executor_error_returns_refusal_string_without_raising(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(valid=True, sql="SELECT title FROM clean_jobs")
        mock_execute_validated_sql.side_effect = ExecutorError("connection refused")

        result = await query_clean_jobs.ainvoke({"question": "What internships are available?"})

        self.assertIn("database error", result)
        self.assertNotIn("connection refused", result)


if __name__ == "__main__":
    unittest.main()
