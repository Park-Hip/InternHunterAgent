"""Prove a real row count reaches the stream, and that zero is not faked.

Three failure modes this guards, all of which would be invisible:

1. The count is lost on the way from the typed query result to the browser,
   which is the whole point of the change.
2. A refused or failed query publishes `0` and the interface shows "no results"
   for a question that was never asked of the database. Absent and zero are
   different facts, and only the tool knows which it has. A failure publishes
   nothing at all (#702): the tool raises, and the card reports the error.
3. An aggregate result publishes the result table's row count as a match count,
   so a count query's card reads "1 kết quả" while the answer says 11 (#677).
   A count publishes the number it counted; any other summary publishes nothing.
"""

from __future__ import annotations

import asyncio
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from src.agents.models import RuntimeOutput, StreamMetadataEvent, StreamToolEvent
from src.agents.runtime.tool_events import (
    bind_tool_event_emitter,
    new_result_facts,
    publish_tool_result,
    reset_tool_event_emitter,
    reset_result_holder,
    set_result_holder,
)
from src.agents.tools import query_clean_jobs as qcj
from src.agents.tools.failures import ToolFailure
from src.services.query.executor import ExecutorError
from src.services.query.models import BoundedRows, ValidationResult


class _Collector:
    def __init__(self) -> None:
        self.events: list[StreamToolEvent] = []

    async def __call__(self, payload: StreamToolEvent) -> None:
        self.events.append(payload)


class ToolResultFactsTests(unittest.IsolatedAsyncioTestCase):
    async def test_facts_reach_the_ok_event(self) -> None:
        """A tool that publishes facts gets them folded into its single event."""
        from langchain.agents import create_agent
        from langchain_core.tools import tool

        from src.agents.runtime.middleware import build_tool_observation_middleware
        from src.agents.runtime.react_agent import AgentRuntime
        from tests.agents.runtime.test_tool_event_stream import (
            _fixed_agent_factory,
            _ScriptedToolCallingModel,
        )

        @tool
        def counted(request: str) -> str:
            """A tool that knows its row count."""
            publish_tool_result(row_count=214, truncated=False)
            return "Tìm thấy 214 kết quả."

        agent = create_agent(
            model=_ScriptedToolCallingModel(tool_name="counted", tool_arg="request"),
            tools=[counted],
            middleware=[build_tool_observation_middleware()],
        )
        runtime = AgentRuntime(agent_factory=_fixed_agent_factory(agent))

        collector = _Collector()
        token = bind_tool_event_emitter(collector)
        try:
            with patch(
                "src.agents.runtime.react_agent.langfuse_request_trace"
            ) as trace, patch(
                "src.agents.runtime.react_agent.build_langfuse_config", return_value={}
            ):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def _null_trace(*args, **kwargs):
                    yield None

                trace.return_value = _null_trace()
                completion_event = asyncio.Event()
                events: list[RuntimeOutput] = []
                async for event in runtime.astream(
                    "xin chào", completion_event=completion_event
                ):
                    events.append(event)
                    if isinstance(event, StreamMetadataEvent):
                        completion_event.set()
        finally:
            reset_tool_event_emitter(token)

        ok = [e for e in events if isinstance(e, StreamToolEvent) and e.status == "ok"]
        self.assertTrue(ok, f"no ok tool event: {events}")
        self.assertEqual(ok[0].row_count, 214)
        self.assertFalse(ok[0].truncated)


class NoFakeZeroTests(unittest.IsolatedAsyncioTestCase):
    """A refused or failed query must publish no count, never zero."""

    def _token(self) -> None:
        self.holder = new_result_facts()
        token = set_result_holder(self.holder)
        self.addCleanup(reset_result_holder, token)

    async def test_rejected_sql_publishes_no_count(self) -> None:
        self._token()
        rejected = ValidationResult(
            valid=False, sql="DROP TABLE x", reason="denied"
        )
        with patch.object(qcj, "generate_sql", return_value="DROP TABLE x"), patch.object(
            qcj, "validate_sql", return_value=rejected
        ):
            with self.assertRaises(ToolFailure) as raised:
                await qcj.run_query_clean_jobs("x")

        self.assertEqual(raised.exception.kind, "rejected")
        self.assertFalse(
            self.holder.published,
            "a rejected query must publish nothing; zero means 'searched, found nothing'",
        )

    async def test_database_error_publishes_no_count(self) -> None:
        self._token()
        valid = ValidationResult(valid=True, sql="SELECT 1")
        with patch.object(qcj, "generate_sql", return_value="SELECT 1"), patch.object(
            qcj, "validate_sql", return_value=valid
        ), patch.object(
            qcj, "execute_bounded_select", side_effect=ExecutorError("down")
        ):
            with self.assertRaises(ToolFailure) as raised:
                await qcj.run_query_clean_jobs("x")

        self.assertEqual(raised.exception.kind, "unavailable")
        self.assertFalse(
            self.holder.published,
            "a failed query must publish nothing; the card reports the error instead",
        )


class AggregateResultPublishingTests(unittest.IsolatedAsyncioTestCase):
    """An aggregate publishes a total or nothing, never its result row count."""

    def _holder(self) -> None:
        self.holder = new_result_facts()
        token = set_result_holder(self.holder)
        self.addCleanup(reset_result_holder, token)

    async def _run_query(
        self,
        sql: str,
        columns: list[str],
        rows: list[list[object]],
        *,
        total_rows: int,
        max_rows: int = 20,
    ) -> None:
        validation = ValidationResult(valid=True, sql=sql)
        with ExitStack() as stack:
            stack.enter_context(patch.object(qcj, "generate_sql", return_value=sql))
            stack.enter_context(
                patch.object(qcj, "validate_sql", return_value=validation)
            )
            stack.enter_context(
                patch.object(
                    qcj,
                    "execute_bounded_select",
                    return_value=BoundedRows(
                        columns=columns, rows=rows, total_rows=total_rows
                    ),
                )
            )
            stack.enter_context(
                patch.object(qcj, "load_max_rows", return_value=max_rows)
            )
            await qcj.run_query_clean_jobs("có bao nhiêu tin tuyển dụng ở Hà Nội?")

    async def test_count_query_publishes_the_counted_total(self) -> None:
        """The issue's case: a count of 11 must not reach the card as 1."""
        self._holder()

        await self._run_query(
            "SELECT COUNT(*) AS count FROM clean_jobs WHERE location ILIKE '%Hanoi%'",
            ["count"],
            [[11]],
            total_rows=1,
        )

        self.assertEqual(self.holder.row_count, 11)
        self.assertFalse(self.holder.truncated)

    async def test_count_query_that_counted_zero_publishes_zero(self) -> None:
        """A zero count is a real zero, so the no-answer state can fire."""
        self._holder()

        await self._run_query(
            "SELECT COUNT(*) AS count FROM clean_jobs WHERE location ILIKE '%Nope%'",
            ["count"],
            [[0]],
            total_rows=1,
        )

        self.assertEqual(self.holder.row_count, 0)

    async def test_other_aggregate_publishes_no_count(self) -> None:
        self._holder()

        await self._run_query(
            "SELECT AVG(salary_min) AS average FROM clean_jobs",
            ["average"],
            [[17500625.5]],
            total_rows=1,
        )

        self.assertTrue(self.holder.published)
        self.assertIsNone(self.holder.row_count)

    async def test_grouped_count_publishes_no_count(self) -> None:
        self._holder()

        await self._run_query(
            "SELECT location, COUNT(*) AS count FROM clean_jobs GROUP BY location",
            ["location", "count"],
            [["Hanoi", 4], ["Da Nang", 2]],
            total_rows=2,
        )

        self.assertTrue(self.holder.published)
        self.assertIsNone(self.holder.row_count)

    async def test_a_capped_listing_publishes_the_real_match_total(self) -> None:
        """The card says "20 of 161", so the count is the match total, not the page."""
        self._holder()

        await self._run_query(
            "SELECT id, title FROM clean_jobs",
            ["id", "title"],
            [[index, f"Intern {index}"] for index in range(1, 21)],
            total_rows=161,
        )

        self.assertEqual(self.holder.row_count, 161)
        self.assertTrue(self.holder.truncated)

    async def test_an_uncapped_listing_publishes_its_own_count(self) -> None:
        self._holder()

        await self._run_query(
            "SELECT id, title FROM clean_jobs WHERE location ILIKE '%Hue%'",
            ["id", "title"],
            [[1, "Intern A"], [2, "Intern B"]],
            total_rows=2,
        )

        self.assertEqual(self.holder.row_count, 2)
        self.assertFalse(self.holder.truncated)


class ResultFactsTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_fresh_holder_does_not_inherit_the_previous_call(self) -> None:
        first = new_result_facts()
        token = set_result_holder(first)
        try:
            publish_tool_result(row_count=7, truncated=True)
            self.assertEqual(first.row_count, 7)
            self.assertTrue(first.truncated)

            second = new_result_facts()
            set_result_holder(second)
            self.assertIsNone(
                second.row_count,
                "consecutive calls must not inherit a stale row count",
            )
        finally:
            reset_result_holder(token)

    async def test_publishing_with_no_holder_is_a_no_op(self) -> None:
        self.addCleanup(reset_tool_event_emitter, bind_tool_event_emitter(None))
        publish_tool_result(row_count=5)  # must not raise


if __name__ == "__main__":
    unittest.main()
