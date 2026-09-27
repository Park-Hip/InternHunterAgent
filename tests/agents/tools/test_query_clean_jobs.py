from __future__ import annotations

import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider

from src.agents.runtime.prompts import load_behavior_glossary
from src.services.query.executor import ExecutorError, UndefinedColumnError
from src.services.query.models import ValidationResult
from tests.langfuse_prompts import native_prompt_client, prompt_link

from src.agents.tools.query_clean_jobs import SQL_GENERATION_OBSERVATION_NAME


class QueryCleanJobsBehaviorTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_happy_path_returns_formatted_answer(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = "SELECT title, company FROM clean_jobs LIMIT 5"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title, company FROM clean_jobs LIMIT 5"
        )
        mock_execute_validated_sql.return_value = [
            {"title": "Data Analyst Intern", "company": "Acme"},
            {"title": "ML Intern", "company": "Globex"},
        ]

        result = await run_query_clean_jobs("What internships are available?")

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
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = (
            "SELECT title FROM clean_jobs WHERE company = 'Nope'"
        )
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs WHERE company = 'Nope'"
        )
        mock_execute_validated_sql.return_value = []

        result = await run_query_clean_jobs("Any jobs at Nope?")

        self.assertEqual(result, load_behavior_glossary()["ZERO_RESULTS"])
        self.assertNotIn("internship", result.lower())

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
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = "DROP TABLE clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=False,
            sql="DROP TABLE clean_jobs",
            reason="Only SELECT statements are allowed",
        )

        result = await run_query_clean_jobs("Delete everything")

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
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs"
        )
        mock_execute_validated_sql.side_effect = ExecutorError("connection refused")

        result = await run_query_clean_jobs("What internships are available?")

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
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs"
        )
        mock_execute_validated_sql.side_effect = ExecutorError("connection refused")

        await run_query_clean_jobs("What internships are available?")

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
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = "SELECT application_deadline FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT application_deadline FROM clean_jobs"
        )
        mock_execute_validated_sql.side_effect = UndefinedColumnError("unknown column")

        result = await run_query_clean_jobs("What is the deadline?")

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
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

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

        result = await run_query_clean_jobs("jobs in Hanoi")

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
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        sql = "SELECT id, title FROM clean_jobs ORDER BY salary_max DESC NULLS LAST LIMIT 2"
        mock_generate_sql.return_value = sql
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=sql)
        mock_execute_validated_sql.return_value = [
            {"id": 1, "title": "Data Analyst Intern"},
            {"id": 2, "title": "ML Intern"},
        ]
        mock_load_max_rows.return_value = 20

        result = await run_query_clean_jobs(
            "show me the top 2 highest-paying internships"
        )

        self.assertIn("Tìm thấy 2 kết quả", result)
        self.assertNotIn("vẫn còn kết quả phù hợp", result)

    @patch("src.agents.tools.query_clean_jobs.execute_validated_sql")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_count_result_passes_through_without_truncation_notice(
        self, mock_generate_sql, mock_validate_sql, mock_execute_validated_sql
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = "SELECT COUNT(*) FROM clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT COUNT(*) FROM clean_jobs"
        )
        mock_execute_validated_sql.return_value = [{"count": 42}]

        result = await run_query_clean_jobs("how many jobs are there?")

        self.assertIn("42", result)
        self.assertNotIn("Đang hiển thị", result)


class _FakeGeneration:
    def __init__(self) -> None:
        self.updated: dict = {}

    def update(self, **kwargs) -> None:
        self.updated.update(kwargs)


@contextmanager
def _fake_observation(**observed):
    fake_generation = _FakeGeneration()
    observed["generation"] = fake_generation
    yield fake_generation


class _RecordingLangfuseClient:
    def __init__(self) -> None:
        self.observation_kwargs: dict | None = None

    def start_as_current_observation(self, **kwargs):
        self.observation_kwargs = kwargs
        cm = _fake_observation
        return cm()


class GenerateSqlContentCoercionTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context_resolution_async")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt_resolution_async"
    )
    async def test_generate_sql_uses_managed_text_and_links_generation(
        self, sql_prompt, schema_prompt, mock_provider
    ) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql
        from src.agents.tracing.prompt_registry import ResolvedPrompt

        sql_prompt.return_value = ResolvedPrompt(
            surface="sql_generation",
            name="resumi-sql-generation",
            content="REMOTE SQL",
            version="4",
            prompt_client=native_prompt_client("resumi-sql-generation", 4),
            is_fallback=False,
        )
        schema_prompt.return_value = ResolvedPrompt(
            surface="schema_context",
            name="resumi-schema-context",
            content="REMOTE SCHEMA",
            version="7",
            prompt_client=object(),
            is_fallback=False,
        )
        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(return_value=SimpleNamespace(content="SELECT 1"))
        fake_provider = mock_provider.return_value
        fake_provider.build_model.return_value = fake_model
        fake_provider.deployment_for.return_value = SimpleNamespace(
            model="deepseek/deepseek-v4-flash"
        )
        fake_client = _RecordingLangfuseClient()

        with patch(
            "src.agents.tools.query_clean_jobs.get_langfuse_client",
            return_value=fake_client,
        ):
            self.assertEqual(await generate_sql("any question"), "SELECT 1")

        self.assertEqual(
            fake_model.ainvoke.call_args.args[0][0].content,
            "REMOTE SQL\n\nREMOTE SCHEMA\n\nQuestion: any question",
        )
        fake_provider.build_model.assert_called_once_with("sql_generation")
        fake_provider.deployment_for.assert_called_once_with("sql_generation")
        self.assertEqual(fake_client.observation_kwargs["as_type"], "generation")
        self.assertEqual(
            fake_client.observation_kwargs["name"], SQL_GENERATION_OBSERVATION_NAME
        )
        self.assertEqual(
            fake_client.observation_kwargs["model"], "deepseek/deepseek-v4-flash"
        )
        self.assertIs(
            fake_client.observation_kwargs["prompt"],
            sql_prompt.return_value.prompt_client,
        )

    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context_resolution_async")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt_resolution_async"
    )
    async def test_generate_sql_forwards_ambient_callbacks_to_nested_model(
        self, sql_prompt, schema_prompt, mock_provider
    ) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql
        from src.agents.tracing.prompt_registry import ResolvedPrompt
        from langchain_core.runnables.config import var_child_runnable_config

        handler = object()
        sql_prompt.return_value = ResolvedPrompt(
            "sql_generation",
            "resumi-sql-generation",
            "PROMPT",
            "4",
            native_prompt_client("resumi-sql-generation", 4),
            False,
        )
        schema_prompt.return_value = ResolvedPrompt(
            "schema_context", "schema", "SCHEMA", "v1", None, True
        )
        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(return_value=SimpleNamespace(content="SELECT 7"))
        mock_provider.return_value.build_model.return_value = fake_model
        mock_provider.return_value.deployment_for.return_value = SimpleNamespace(
            model="m"
        )

        tracer = TracerProvider().get_tracer(__name__)
        token = var_child_runnable_config.set({"callbacks": [handler]})
        try:
            with (
                patch(
                    "src.agents.tools.query_clean_jobs.get_langfuse_client"
                ) as langfuse_client,
                tracer.start_as_current_span("query_clean_jobs") as span,
            ):
                self.assertEqual(await generate_sql("q"), "SELECT 7")
                span_attributes = dict(span.attributes or {})
        finally:
            var_child_runnable_config.reset(token)

        self.assertEqual(prompt_link(span_attributes), ("resumi-sql-generation", 4))
        self.assertEqual(
            fake_model.ainvoke.call_args.kwargs["config"],
            {"callbacks": [handler]},
        )
        langfuse_client.assert_not_called()

    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context_resolution_async")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt_resolution_async"
    )
    async def test_generate_sql_flattens_list_content(
        self, sql_prompt, schema_prompt, mock_provider
    ) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql
        from src.agents.tracing.prompt_registry import ResolvedPrompt

        fallback = ResolvedPrompt("sql_generation", "sql", "PROMPT", "v1", None, True)
        sql_prompt.return_value = fallback
        schema_prompt.return_value = ResolvedPrompt(
            "schema_context", "schema", "SCHEMA", "v1", None, True
        )
        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(
            return_value=SimpleNamespace(content=[{"text": "SELECT "}, {"text": "1"}])
        )
        fake_provider = mock_provider.return_value
        fake_provider.build_model.return_value = fake_model
        fake_provider.deployment_for.return_value = SimpleNamespace(model="m")

        with patch(
            "src.agents.tools.query_clean_jobs.get_langfuse_client", return_value=None
        ):
            self.assertEqual(await generate_sql("any question"), "SELECT 1")

    @patch("src.agents.tools.query_clean_jobs.AgentProvider")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context_resolution_async")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt_resolution_async"
    )
    async def test_generate_sql_runs_model_without_langfuse_when_tracing_disabled(
        self, sql_prompt, schema_prompt, mock_provider
    ) -> None:
        from src.agents.tools.query_clean_jobs import generate_sql
        from src.agents.tracing.prompt_registry import ResolvedPrompt

        sql_prompt.return_value = ResolvedPrompt(
            "sql_generation", "sql", "PROMPT", "v1", None, True
        )
        schema_prompt.return_value = ResolvedPrompt(
            "schema_context", "schema", "SCHEMA", "v1", None, True
        )
        fake_model = MagicMock()
        fake_model.ainvoke = AsyncMock(return_value=SimpleNamespace(content="SELECT 2"))
        mock_provider.return_value.build_model.return_value = fake_model
        mock_provider.return_value.deployment_for.return_value = SimpleNamespace(
            model="m"
        )

        with patch(
            "src.agents.tools.query_clean_jobs.get_langfuse_client", return_value=None
        ):
            self.assertEqual(await generate_sql("any question"), "SELECT 2")

        fake_model.ainvoke.assert_awaited_once()
        self.assertEqual(len(fake_model.ainvoke.call_args.args), 1)


if __name__ == "__main__":
    unittest.main()
