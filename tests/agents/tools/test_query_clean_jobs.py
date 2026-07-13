from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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

    @patch("src.agents.tools.query_clean_jobs.load_max_rows")
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_wide_result_is_truncated_with_honest_notice(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql, mock_load_max_rows
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(valid=True, sql="SELECT title FROM clean_jobs")
        mock_execute_validated_sql.return_value = [
            {"title": "Intern A", "description": "long blob"},
            {"title": "Intern B", "description": "long blob"},
            {"title": "Intern C", "description": "long blob"},
        ]
        mock_load_max_rows.return_value = 2

        result = await query_clean_jobs.ainvoke({"question": "jobs in Hanoi"})

        self.assertIn("Showing the first 2 results", result)
        self.assertIn("there are more", result)
        self.assertNotIn("long blob", result)

    @patch("src.agents.tools.query_clean_jobs.load_max_rows")
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_explicit_user_requested_count_is_honored_without_truncation_notice(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql, mock_load_max_rows
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        sql = "SELECT id, title FROM clean_jobs ORDER BY salary_max DESC NULLS LAST LIMIT 2"
        mock_generate_sql.return_value = sql
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=sql)
        mock_execute_validated_sql.return_value = [
            {"id": 1, "title": "Data Analyst Intern"},
            {"id": 2, "title": "ML Intern"},
        ]
        mock_load_max_rows.return_value = 20

        result = await query_clean_jobs.ainvoke({"question": "show me the top 2 highest-paying internships"})

        self.assertIn("Found 2 result(s)", result)
        self.assertNotIn("there are more", result)

    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_count_result_passes_through_without_truncation_notice(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT COUNT(*) FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(valid=True, sql="SELECT COUNT(*) FROM clean_jobs")
        mock_execute_validated_sql.return_value = [{"count": 42}]

        result = await query_clean_jobs.ainvoke({"question": "how many jobs are there?"})

        self.assertIn("42", result)
        self.assertNotIn("Showing", result)


class GenerateSqlContentCoercionTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.tools.query_clean_jobs.load_sql_generation_prompt", return_value="PROMPT")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA")
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_flattens_list_content(self, mock_provider, *_) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(
            return_value=SimpleNamespace(
                content=[{"type": "text", "text": "SELECT title "}, {"type": "text", "text": "FROM clean_jobs"}]
            )
        )
        mock_provider.return_value.build_model.return_value = fake_model

        self.assertEqual(await generate_sql("any question"), "SELECT title FROM clean_jobs")

    @patch("src.agents.tools.query_clean_jobs.load_sql_generation_prompt", return_value="PROMPT")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA")
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_str_content_unchanged(self, mock_provider, *_) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(return_value=SimpleNamespace(content="  SELECT 1  "))
        mock_provider.return_value.build_model.return_value = fake_model

        self.assertEqual(await generate_sql("any question"), "SELECT 1")

    @patch("src.agents.tools.query_clean_jobs.load_sql_generation_prompt", return_value="PROMPT")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA")
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_unrecognized_block_list_yields_empty_string(self, mock_provider, *_) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(return_value=SimpleNamespace(content=[{"type": "reasoning"}, 42]))
        mock_provider.return_value.build_model.return_value = fake_model

        self.assertEqual(await generate_sql("any question"), "")


if __name__ == "__main__":
    unittest.main()
