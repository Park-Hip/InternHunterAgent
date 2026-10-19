"""Behavior tests for the query_clean_jobs tool (#702).

The tool returns typed facts, never sentences, and raises ``ToolFailure`` for
every failure kind. These tests assert the facts, the statement that ran, the
failure vocabulary, and what is published to the tool-event holder. No model
call and no database: ``execute_bounded_select`` is replaced by a fake.
"""

from __future__ import annotations

import datetime as dt
import json
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider

from src.agents.runtime.tool_events import (
    ToolResultFacts,
    new_result_facts,
    reset_result_holder,
    set_result_holder,
)
from src.agents.tools.failures import ToolFailure
from src.services.query.executor import (
    ExecutorError,
    QueryTimeoutError,
    ResultTooLargeError,
    UndefinedColumnError,
)
from src.services.query.models import BoundedRows, ValidationResult
from tests.langfuse_prompts import native_prompt_client, prompt_link

from src.agents.tools.query_clean_jobs import SQL_GENERATION_OBSERVATION_NAME

HAPPY_SQL = "SELECT id, title FROM clean_jobs WHERE location ILIKE '%Hanoi%'"


@contextmanager
def _bound_holder() -> Iterator[ToolResultFacts]:
    """Bind the holder the agent middleware would bind for one tool call."""
    holder = new_result_facts()
    token = set_result_holder(holder)
    try:
        yield holder
    finally:
        reset_result_holder(token)


class QueryCleanJobsBehaviorTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_a_capped_listing_returns_the_rows_and_the_real_total(
        self, mock_generate_sql, mock_validate_sql, mock_execute
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = HAPPY_SQL
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=HAPPY_SQL)
        mock_execute.return_value = BoundedRows(
            columns=["id", "title", "description"],
            rows=[[index, f"Intern {index}", "a description blob"] for index in range(1, 21)],
            total_rows=161,
        )

        with _bound_holder() as holder:
            result = await run_query_clean_jobs("internships in Hanoi")

        self.assertEqual(result.sql, f"{HAPPY_SQL} LIMIT 20")
        self.assertEqual(result.columns, ["id", "title"])
        self.assertEqual(len(result.rows), 20)
        self.assertEqual(result.rows[0], [1, "Intern 1"])
        self.assertEqual(result.row_count, 20)
        self.assertEqual(result.total_rows, 161)
        mock_execute.assert_called_once_with(HAPPY_SQL, 20)

        self.assertEqual(holder.row_count, 161)
        self.assertTrue(holder.truncated)
        self.assertTrue(holder.published)

    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_no_match_returns_zero_rows_and_the_columns_that_would_be_shown(
        self, mock_generate_sql, mock_validate_sql, mock_execute
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = "SELECT title FROM clean_jobs WHERE company = 'Nope'"
        mock_validate_sql.return_value = ValidationResult(
            valid=True, sql="SELECT title FROM clean_jobs WHERE company = 'Nope'"
        )
        mock_execute.return_value = BoundedRows(
            columns=["title"], rows=[], total_rows=0
        )

        with _bound_holder() as holder:
            result = await run_query_clean_jobs("any jobs at Nope?")

        self.assertEqual(result.columns, ["title"])
        self.assertEqual(result.rows, [])
        self.assertEqual(result.row_count, 0)
        self.assertEqual(result.total_rows, 0)
        self.assertEqual(holder.row_count, 0)
        self.assertFalse(holder.truncated)

    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_a_count_reaches_the_model_as_one_row_and_publishes_the_number(
        self, mock_generate_sql, mock_validate_sql, mock_execute
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        sql = "SELECT count(*) AS count FROM clean_jobs WHERE is_internship = true"
        mock_generate_sql.return_value = sql
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=sql)
        mock_execute.return_value = BoundedRows(columns=["count"], rows=[[70]], total_rows=1)

        with _bound_holder() as holder:
            result = await run_query_clean_jobs("how many internships are there?")

        self.assertEqual(result.columns, ["count"])
        self.assertEqual(result.rows, [[70]])
        self.assertEqual(result.row_count, 1)
        self.assertEqual(holder.row_count, 70)
        self.assertFalse(holder.truncated)

    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_a_zero_count_is_a_zero_row_not_a_missing_fact(
        self, mock_generate_sql, mock_validate_sql, mock_execute
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        sql = "SELECT count(*) AS count FROM clean_jobs WHERE salary_currency = 'JPY'"
        mock_generate_sql.return_value = sql
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=sql)
        mock_execute.return_value = BoundedRows(columns=["count"], rows=[[0]], total_rows=1)

        with _bound_holder() as holder:
            result = await run_query_clean_jobs("how many jobs pay in yen?")

        self.assertEqual(result.rows, [[0]])
        self.assertEqual(holder.row_count, 0)

    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_any_other_summary_publishes_no_count(
        self, mock_generate_sql, mock_validate_sql, mock_execute
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        sql = "SELECT AVG(salary_min) AS average FROM clean_jobs"
        mock_generate_sql.return_value = sql
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=sql)
        mock_execute.return_value = BoundedRows(
            columns=["average"], rows=[[17500625.5]], total_rows=1
        )

        with _bound_holder() as holder:
            result = await run_query_clean_jobs("average salary?")

        self.assertEqual(result.rows, [[17500625.5]])
        self.assertIsNone(holder.row_count)
        self.assertFalse(holder.truncated)
        self.assertTrue(holder.published)

    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_the_newest_matches_come_back_without_any_caveat_sentence(
        self, mock_generate_sql, mock_validate_sql, mock_execute
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        sql = (
            "SELECT id, title FROM clean_jobs WHERE description ILIKE '%intern%'"
            " ORDER BY id DESC LIMIT 5"
        )
        mock_generate_sql.return_value = sql
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=sql)
        mock_execute.return_value = BoundedRows(
            columns=["id", "title"],
            rows=[[9, "Intern Z"], [8, "Intern Y"]],
            total_rows=2,
        )

        result = await run_query_clean_jobs("the newest internships")

        self.assertEqual(result.sql, sql)
        self.assertEqual(
            set(result.model_dump()),
            {"sql", "columns", "rows", "row_count", "total_rows"},
        )
        mock_execute.assert_called_once_with(
            "SELECT id, title FROM clean_jobs WHERE description ILIKE '%intern%'"
            " ORDER BY id DESC",
            5,
        )
        payload = json.dumps(result.model_dump(), ensure_ascii=False)
        self.assertNotIn("kết quả", payload)
        self.assertNotIn("Tìm thấy", payload)

    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_values_are_json_native(
        self, mock_generate_sql, mock_validate_sql, mock_execute
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        sql = (
            "SELECT id, salary_min, salary_max, salary_currency, created_on"
            " FROM clean_jobs"
        )
        mock_generate_sql.return_value = sql
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=sql)
        mock_execute.return_value = BoundedRows(
            columns=[
                "id",
                "salary_min",
                "salary_max",
                "salary_currency",
                "created_on",
            ],
            rows=[[7, None, None, None, dt.date(2026, 10, 18)]],
            total_rows=1,
        )

        result = await run_query_clean_jobs("the salary of job 7")

        self.assertEqual(result.rows, [[7, None, None, None, "2026-10-18"]])

    @patch("src.agents.tools.query_clean_jobs.logger")
    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_a_rejected_statement_raises_with_the_validator_reason(
        self, mock_generate_sql, mock_validate_sql, mock_execute, mock_logger
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = "DROP TABLE clean_jobs"
        mock_validate_sql.return_value = ValidationResult(
            valid=False,
            sql="DROP TABLE clean_jobs",
            reason="Only SELECT statements are allowed",
        )

        with _bound_holder() as holder:
            with self.assertRaises(ToolFailure) as raised:
                await run_query_clean_jobs("delete everything")

        self.assertEqual(raised.exception.kind, "rejected")
        self.assertEqual(raised.exception.detail, "Only SELECT statements are allowed")
        self.assertEqual(
            str(raised.exception), "rejected: Only SELECT statements are allowed"
        )
        self.assertFalse(holder.published)
        mock_execute.assert_not_called()
        mock_logger.warning.assert_called_once_with(
            "query_clean_jobs.sql_rejected",
            reason="Only SELECT statements are allowed",
        )

    @patch("src.agents.tools.query_clean_jobs.logger")
    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_an_unknown_column_failure_names_the_column(
        self, mock_generate_sql, mock_validate_sql, mock_execute, mock_logger
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        sql = "SELECT remote FROM clean_jobs"
        mock_generate_sql.return_value = sql
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=sql)
        mock_execute.side_effect = UndefinedColumnError(
            'column "remote" does not exist'
        )

        with _bound_holder() as holder:
            with self.assertRaises(ToolFailure) as raised:
                await run_query_clean_jobs("what does remote hold?")

        self.assertEqual(raised.exception.kind, "unknown_column")
        self.assertEqual(raised.exception.detail, 'column "remote" does not exist')
        self.assertFalse(holder.published)
        mock_logger.warning.assert_called_once_with(
            "query_clean_jobs.unknown_column", error='column "remote" does not exist'
        )

    @patch("src.agents.tools.query_clean_jobs.logger")
    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_a_timeout_reports_the_configured_limit(
        self, mock_generate_sql, mock_validate_sql, mock_execute, mock_logger
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = HAPPY_SQL
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=HAPPY_SQL)
        mock_execute.side_effect = QueryTimeoutError(2000)

        with _bound_holder() as holder:
            with self.assertRaises(ToolFailure) as raised:
                await run_query_clean_jobs("slow question")

        self.assertEqual(raised.exception.kind, "timeout")
        self.assertEqual(raised.exception.detail, "statement exceeded the 2000 ms limit")
        self.assertFalse(holder.published)
        mock_logger.warning.assert_called_once_with(
            "query_clean_jobs.timeout", error="statement exceeded the 2000 ms limit"
        )

    @patch("src.agents.tools.query_clean_jobs.logger")
    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_a_result_over_the_byte_budget_asks_for_fewer_columns(
        self, mock_generate_sql, mock_validate_sql, mock_execute, mock_logger
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = HAPPY_SQL
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=HAPPY_SQL)
        mock_execute.side_effect = ResultTooLargeError(
            "The query returned more data than this agent is allowed to read."
        )

        with _bound_holder() as holder:
            with self.assertRaises(ToolFailure) as raised:
                await run_query_clean_jobs("every column please")

        self.assertEqual(raised.exception.kind, "too_large")
        self.assertEqual(
            raised.exception.detail,
            "result exceeds the byte budget; select fewer columns",
        )
        self.assertFalse(holder.published)
        mock_logger.warning.assert_called_once()

    @patch("src.agents.tools.query_clean_jobs.logger")
    @patch("src.agents.tools.query_clean_jobs.execute_bounded_select")
    @patch("src.agents.tools.query_clean_jobs.validate_sql")
    @patch("src.agents.tools.query_clean_jobs.generate_sql")
    async def test_an_unavailable_database_never_leaks_the_driver_message(
        self, mock_generate_sql, mock_validate_sql, mock_execute, mock_logger
    ) -> None:
        from src.agents.tools.query_clean_jobs import run_query_clean_jobs

        mock_generate_sql.return_value = HAPPY_SQL
        mock_validate_sql.return_value = ValidationResult(valid=True, sql=HAPPY_SQL)
        mock_execute.side_effect = ExecutorError(
            "connection to server at \"db.internal\" failed: connection refused"
        )

        with _bound_holder() as holder:
            with self.assertRaises(ToolFailure) as raised:
                await run_query_clean_jobs("any internships?")

        self.assertEqual(raised.exception.kind, "unavailable")
        self.assertEqual(
            raised.exception.detail, "the database could not run the query"
        )
        self.assertNotIn("db.internal", raised.exception.detail)
        self.assertFalse(holder.published)
        self.assertEqual(
            mock_logger.error.call_args.args[0], "query_clean_jobs.db_error"
        )
        self.assertIn("connection refused", mock_logger.error.call_args.kwargs["error"])


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
    @patch("src.agents.tools.query_clean_jobs.build_model")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context_resolution_async")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt_resolution_async"
    )
    async def test_generate_sql_uses_managed_text_and_links_generation(
        self, sql_prompt, schema_prompt, mock_build_model
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
        mock_build_model.return_value = fake_model
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
        mock_build_model.assert_called_once_with("sql_generation")
        self.assertEqual(fake_client.observation_kwargs["as_type"], "generation")
        self.assertEqual(
            fake_client.observation_kwargs["name"], SQL_GENERATION_OBSERVATION_NAME
        )
        self.assertEqual(
            fake_client.observation_kwargs["model"], "deepseek/deepseek-flash"
        )
        self.assertIs(
            fake_client.observation_kwargs["prompt"],
            sql_prompt.return_value.prompt_client,
        )

    @patch("src.agents.tools.query_clean_jobs.build_model")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context_resolution_async")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt_resolution_async"
    )
    async def test_generate_sql_forwards_ambient_callbacks_to_nested_model(
        self, sql_prompt, schema_prompt, mock_build_model
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
        mock_build_model.return_value = fake_model

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

    @patch("src.agents.tools.query_clean_jobs.build_model")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context_resolution_async")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt_resolution_async"
    )
    async def test_generate_sql_flattens_list_content(
        self, sql_prompt, schema_prompt, mock_build_model
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
        mock_build_model.return_value = fake_model

        with patch(
            "src.agents.tools.query_clean_jobs.get_langfuse_client", return_value=None
        ):
            self.assertEqual(await generate_sql("any question"), "SELECT 1")

    @patch("src.agents.tools.query_clean_jobs.build_model")
    @patch("src.agents.tools.query_clean_jobs.load_schema_context_resolution_async")
    @patch(
        "src.agents.tools.query_clean_jobs.load_sql_generation_prompt_resolution_async"
    )
    async def test_generate_sql_runs_model_without_langfuse_when_tracing_disabled(
        self, sql_prompt, schema_prompt, mock_build_model
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
        mock_build_model.return_value = fake_model

        with patch(
            "src.agents.tools.query_clean_jobs.get_langfuse_client", return_value=None
        ):
            self.assertEqual(await generate_sql("any question"), "SELECT 2")

        fake_model.ainvoke.assert_awaited_once()
        self.assertEqual(len(fake_model.ainvoke.call_args.args), 1)


if __name__ == "__main__":
    unittest.main()
