from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.runtime.prompts import load_behavior_glossary
from src.services.query.executor import ExecutorError, UndefinedColumnError
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

        result = await query_clean_jobs.ainvoke(
            {"question": "What internships are available?"}
        )

        self.assertIn("Tìm thấy 2 kết quả", result)
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

        mock_generate_sql.return_value = (
            "SELECT title FROM clean_jobs WHERE company = 'Nope'"
        )
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs WHERE company = 'Nope'"
        )
        mock_execute_validated_sql.return_value = []

        result = await query_clean_jobs.ainvoke({"question": "Any jobs at Nope?"})

        self.assertEqual(result, load_behavior_glossary()["ZERO_RESULTS"])
        self.assertNotIn("internship", result.lower())

    def test_description_covers_ai_data_roles_and_search_use(self) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        description = query_clean_jobs.description

        self.assertIn("AI and data job and internship postings", description)
        self.assertIn("before get_job_details", description)
        self.assertIn("user's question", description)
        self.assertNotIn("internship job postings", description)

    @patch("src.agents.tools.query_clean_jobs.logger")
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_validator_rejection_returns_refusal_string_without_executing(
        self,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_validated_sql,
        mock_logger,
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "DROP TABLE clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=False,
            sql="DROP TABLE clean_jobs",
            reason="Only SELECT statements are allowed",
        )

        result = await query_clean_jobs.ainvoke({"question": "Delete everything"})

        self.assertIn("Tôi không thể chạy truy vấn đó", result)
        self.assertIn("Only SELECT statements are allowed", result)
        mock_execute_validated_sql.assert_not_called()
        mock_logger.warning.assert_called_once_with(
            "query_clean_jobs.sql_rejected",
            reason="Only SELECT statements are allowed",
        )

    @patch("src.agents.tools.query_clean_jobs.logger")
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_executor_error_returns_refusal_string_without_raising(
        self,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_validated_sql,
        mock_logger,
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs"
        )
        mock_execute_validated_sql.side_effect = ExecutorError("connection refused")

        result = await query_clean_jobs.ainvoke(
            {"question": "What internships are available?"}
        )

        self.assertIn("lỗi cơ sở dữ liệu", result)
        self.assertNotIn("connection refused", result)

    @patch("src.agents.tools.query_clean_jobs.logger")
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_executor_error_is_logged(
        self,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_validated_sql,
        mock_logger,
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs"
        )
        mock_execute_validated_sql.side_effect = ExecutorError("connection refused")

        await query_clean_jobs.ainvoke({"question": "What internships are available?"})

        mock_logger.error.assert_called_once()
        self.assertEqual(
            mock_logger.error.call_args.args[0], "query_clean_jobs.db_error"
        )
        self.assertIn("connection refused", mock_logger.error.call_args.kwargs["error"])

    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_unknown_column_returns_absent_field_glossary(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT application_deadline FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT application_deadline FROM clean_jobs"
        )
        mock_execute_validated_sql.side_effect = UndefinedColumnError("unknown column")

        result = await query_clean_jobs.ainvoke({"question": "What is the deadline?"})

        self.assertEqual(result, load_behavior_glossary()["ABSENT_FIELD"])

    @patch("src.agents.tools.query_clean_jobs.load_max_rows")
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_wide_result_is_truncated_with_honest_notice(
        self,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_validated_sql,
        mock_load_max_rows,
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs"
        )
        mock_execute_validated_sql.return_value = [
            {"title": "Intern A", "description": "long blob"},
            {"title": "Intern B", "description": "long blob"},
            {"title": "Intern C", "description": "long blob"},
        ]
        mock_load_max_rows.return_value = 2

        result = await query_clean_jobs.ainvoke({"question": "jobs in Hanoi"})

        self.assertIn(load_behavior_glossary()["TRUNCATION"], result)
        self.assertNotIn("long blob", result)

    @patch("src.agents.tools.query_clean_jobs.load_max_rows")
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_explicit_user_requested_count_is_honored_without_truncation_notice(
        self,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_validated_sql,
        mock_load_max_rows,
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

        result = await query_clean_jobs.ainvoke(
            {"question": "show me the top 2 highest-paying internships"}
        )

        self.assertIn("Tìm thấy 2 kết quả", result)
        self.assertNotIn("vẫn còn kết quả phù hợp", result)

    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_count_result_passes_through_without_truncation_notice(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import query_clean_jobs

        mock_generate_sql.return_value = "SELECT COUNT(*) FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT COUNT(*) FROM clean_jobs"
        )
        mock_execute_validated_sql.return_value = [{"count": 42}]

        result = await query_clean_jobs.ainvoke(
            {"question": "how many jobs are there?"}
        )

        self.assertIn("42", result)
        self.assertNotIn("Đang hiển thị", result)


class GenerateSqlContentCoercionTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.tools.query_clean_jobs.get_langfuse_client")
    @patch("src.agents.tools.query_clean_jobs.get_sql_generation_prompt_reference")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt",
        return_value="YAML PROMPT",
    )
    @patch(
        "src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA"
    )
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_creates_a_linked_child_generation_without_using_remote_prompt_text(
        self,
        mock_provider,
        _mock_schema_context,
        _mock_sql_prompt,
        mock_prompt_reference,
        mock_langfuse_client,
    ) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(return_value=SimpleNamespace(content="SELECT 1"))
        mock_provider.return_value.build_model.return_value = fake_model
        prompt_reference = SimpleNamespace(
            prompt="REMOTE PROMPT", name="resumi-sql-generation", version=4
        )
        mock_prompt_reference.return_value = prompt_reference
        client = MagicMock()
        client.start_as_current_observation.return_value.__enter__.return_value = (
            MagicMock()
        )
        mock_langfuse_client.return_value = client

        self.assertEqual(await generate_sql("any question"), "SELECT 1")

        client.start_as_current_observation.assert_called_once_with(
            as_type="generation",
            name="sql_generation",
            input={"question": "any question"},
            prompt=prompt_reference,
        )
        client.start_as_current_observation.return_value.__enter__.return_value.update.assert_called_once_with(
            output="SELECT 1"
        )
        model_messages = fake_model.ainvoke.call_args.args[0]
        self.assertIn("YAML PROMPT", model_messages[0].content)
        self.assertNotIn("REMOTE PROMPT", model_messages[0].content)

    @patch("src.agents.tools.query_clean_jobs.get_langfuse_client", return_value=None)
    @patch(
        "src.agents.tools.query_clean_jobs.get_sql_generation_prompt_reference",
        return_value=None,
    )
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt",
        return_value="PROMPT",
    )
    @patch(
        "src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA"
    )
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_is_unchanged_when_tracing_has_no_client(
        self, mock_provider, *_
    ) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(return_value=SimpleNamespace(content="SELECT 1"))
        mock_provider.return_value.build_model.return_value = fake_model

        self.assertEqual(await generate_sql("any question"), "SELECT 1")
        fake_model.ainvoke.assert_awaited_once()

    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt",
        return_value="PROMPT",
    )
    @patch(
        "src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA"
    )
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_flattens_list_content(self, mock_provider, *_) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(
            return_value=SimpleNamespace(
                content=[
                    {"type": "text", "text": "SELECT title "},
                    {"type": "text", "text": "FROM clean_jobs"},
                ]
            )
        )
        mock_provider.return_value.build_model.return_value = fake_model

        self.assertEqual(
            await generate_sql("any question"), "SELECT title FROM clean_jobs"
        )

    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt",
        return_value="PROMPT",
    )
    @patch(
        "src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA"
    )
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_str_content_unchanged(self, mock_provider, *_) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(
            return_value=SimpleNamespace(content="  SELECT 1  ")
        )
        mock_provider.return_value.build_model.return_value = fake_model

        self.assertEqual(await generate_sql("any question"), "SELECT 1")

    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt",
        return_value="PROMPT",
    )
    @patch(
        "src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA"
    )
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_unrecognized_block_list_yields_empty_string(
        self, mock_provider, *_
    ) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(
            return_value=SimpleNamespace(content=[{"type": "reasoning"}, 42])
        )
        mock_provider.return_value.build_model.return_value = fake_model

        self.assertEqual(await generate_sql("any question"), "")

    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt",
        return_value="PROMPT",
    )
    @patch(
        "src.agents.tools.query_clean_jobs.load_schema_context", return_value="SCHEMA"
    )
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    async def test_generate_sql_uses_sql_generation_profile(
        self, mock_provider, _mock_schema_context, _mock_sql_prompt
    ) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql

        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(return_value=SimpleNamespace(content="SELECT 1"))
        mock_provider.return_value.build_model.return_value = fake_model

        self.assertEqual(await generate_sql("any question"), "SELECT 1")
        mock_provider.return_value.build_model.assert_called_once_with("sql_generation")


if __name__ == "__main__":
    unittest.main()
