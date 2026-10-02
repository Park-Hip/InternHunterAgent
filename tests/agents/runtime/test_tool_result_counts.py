"""Prove a real row count reaches the stream, and that zero is not faked.

Two failure modes this guards, both of which would be invisible:

1. The count is lost on the way from `TableArtifact` to the browser, which is the
   whole point of the change.
2. A refused or failed query publishes `0` and the interface shows "no results"
   for a question that was never asked of the database. Absent and zero are
   different facts, and only the tool knows which it has.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.agents.runtime.tool_events import (
    bind_tool_event_emitter,
    new_result_facts,
    publish_tool_result,
    reset_tool_event_emitter,
    reset_result_holder,
    set_result_holder,
)
from src.agents.tools import query_clean_jobs as qcj
from src.agents.tools import v0_query_jobs as v0q
from src.services.query.plan import QueryShape
from src.services.query.results import QueryResult, QueryState


class _Collector:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def __call__(self, payload: dict) -> None:
        self.events.append(payload)


class ToolResultFactsTests(unittest.IsolatedAsyncioTestCase):
    async def test_facts_reach_the_ok_event(self) -> None:
        """A tool that publishes facts gets them folded into its single event."""
        from langchain.agents import create_agent
        from langchain_core.tools import tool

        from src.agents.runtime.middleware import build_tool_observation_middleware
        from src.agents.runtime.react_agent import AgentRuntime
        from tests.agents.runtime.test_tool_event_stream import _ScriptedToolCallingModel

        @tool
        def counted(question: str) -> str:
            """A tool that knows its row count."""
            publish_tool_result(row_count=214, truncated=False)
            return "Tìm thấy 214 kết quả."

        agent = create_agent(
            model=_ScriptedToolCallingModel(tool_name="counted", tool_arg="question"),
            tools=[counted],
            middleware=[build_tool_observation_middleware()],
        )
        runtime = AgentRuntime(agent=agent)

        collector = _Collector()
        token = bind_tool_event_emitter(collector)
        try:
            with patch(
                "src.agents.runtime.react_agent.get_langfuse_client", return_value=None
            ), patch(
                "src.agents.runtime.react_agent.langfuse_request_trace"
            ) as trace, patch(
                "src.agents.runtime.react_agent.build_langfuse_config", return_value={}
            ):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def _null_trace(*args, **kwargs):
                    yield None

                trace.return_value = _null_trace()
                events = [e async for e in runtime.astream("xin chào")]
        finally:
            reset_tool_event_emitter(token)

        ok = [e for e in events if e.get("type") == "tool" and e.get("status") == "ok"]
        self.assertTrue(ok, f"no ok tool event: {events}")
        self.assertEqual(ok[0]["row_count"], 214)
        self.assertFalse(ok[0]["truncated"])


class NoFakeZeroTests(unittest.IsolatedAsyncioTestCase):
    """A refused or failed query must publish no count, never zero."""

    def _token(self) -> None:
        self.holder = new_result_facts()
        token = set_result_holder(self.holder)
        self.addCleanup(reset_result_holder, token)

    async def test_rejected_sql_publishes_no_count(self) -> None:
        self._token()
        invalid = type("V", (), {"valid": False, "reason": "denied", "sql": ""})()
        with patch.object(qcj, "generate_sql", return_value="DROP TABLE x"), patch.object(
            qcj, "validate_sql", return_value=invalid
        ):
            await qcj.run_query_clean_jobs("x")

        facts = self.holder
        self.assertTrue(facts.published)
        self.assertIsNone(
            facts.row_count,
            "a rejected query must not publish zero; zero means 'searched, found nothing'",
        )

    async def test_database_error_publishes_no_count(self) -> None:
        self._token()
        valid = type("V", (), {"valid": True, "reason": "", "sql": "SELECT 1"})()
        with patch.object(qcj, "generate_sql", return_value="SELECT 1"), patch.object(
            qcj, "validate_sql", return_value=valid
        ), patch.object(
            qcj, "execute_validated_sql", side_effect=qcj.ExecutorError("down")
        ):
            await qcj.run_query_clean_jobs("x")

        facts = self.holder
        self.assertTrue(facts.published)
        self.assertIsNone(facts.row_count)


class ServedPathPublishesTests(unittest.IsolatedAsyncioTestCase):
    """`query_jobs` is the only tool bound when `agent.agent_v0` is on.

    Without a publish call here the `tool` event carries no count, and the
    interface cannot tell a real zero-match from a turn that found nothing.
    """

    def setUp(self) -> None:
        self.holder = new_result_facts()
        token = set_result_holder(self.holder)
        self.addCleanup(reset_result_holder, token)

    def _result(self, **overrides) -> QueryResult:
        base = {"state": QueryState.ANSWERED, "shape": QueryShape.LIST}
        base.update(overrides)
        return QueryResult(**base)

    def _run(self, result: QueryResult | None = None, request: dict | None = None) -> None:
        service = None if result is None else MagicMock()
        if service is not None:
            service.answer.return_value = result
        v0q.run_query_jobs(
            request if request is not None else {"shape": "count"}, service=service
        )

    def test_a_zero_match_publishes_zero(self) -> None:
        """Zero is the signal the interface keys its no-answer state to."""
        self._run(self._result(state=QueryState.EMPTY, match_total=0))
        self.assertTrue(self.holder.published)
        self.assertEqual(self.holder.row_count, 0)

    def test_the_published_count_is_the_match_total_not_the_displayed_rows(self) -> None:
        """A bare number would imply the answer shows every match."""
        self._run(
            self._result(match_total=214, displayed_count=20, truncated=True, rows=[{}] * 20)
        )
        self.assertEqual(self.holder.row_count, 214)
        self.assertTrue(self.holder.truncated)

    def test_a_result_under_the_cap_is_not_truncated(self) -> None:
        self._run(self._result(match_total=7, displayed_count=7, rows=[{}] * 7))
        self.assertEqual(self.holder.row_count, 7)
        self.assertFalse(self.holder.truncated)

    def test_a_refusal_publishes_no_count(self) -> None:
        """A question never asked of the database must not read as a zero."""
        self._run(
            QueryResult(
                state=QueryState.UNSUPPORTED,
                shape=QueryShape.COUNT,
                message="'Đà Lạt' is not a city this data holds.",
            )
        )
        self.assertTrue(self.holder.published)
        self.assertIsNone(self.holder.row_count)

    def test_a_rejected_request_publishes_no_count(self) -> None:
        """The request never reached the service, so there is nothing to count."""
        self._run(request={"shape": "sql"})
        self.assertTrue(self.holder.published)
        self.assertIsNone(self.holder.row_count)


class ServedPathReachesTheStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_served_tool_facts_reach_the_stream(self) -> None:
        """The whole wiring: the governed tool, the real middleware, the real event."""
        from langchain.agents import create_agent
        from langchain_core.tools import tool

        from src.agents.runtime.middleware import build_tool_observation_middleware
        from src.agents.runtime.react_agent import AgentRuntime
        from tests.agents.runtime.test_tool_event_stream import _ScriptedToolCallingModel

        @tool
        def query_jobs(request: dict) -> str:
            """The governed query core, as served."""
            service = MagicMock()
            service.answer.return_value = QueryResult(
                state=QueryState.EMPTY, shape=QueryShape.LIST, match_total=0
            )
            return v0q.run_query_jobs(request, service=service)

        agent = create_agent(
            model=_ScriptedToolCallingModel(
                tool_name="query_jobs",
                tool_args={"request": {"shape": "count"}},
            ),
            tools=[query_jobs],
            middleware=[build_tool_observation_middleware()],
        )
        runtime = AgentRuntime(agent=agent)

        collector = _Collector()
        token = bind_tool_event_emitter(collector)
        try:
            with patch(
                "src.agents.runtime.react_agent.get_langfuse_client", return_value=None
            ), patch("src.agents.runtime.react_agent.langfuse_request_trace") as trace, patch(
                "src.agents.runtime.react_agent.build_langfuse_config", return_value={}
            ):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def _null_trace(*args, **kwargs):
                    yield None

                trace.side_effect = _null_trace
                events = [e async for e in runtime.astream("xin chào")]
        finally:
            reset_tool_event_emitter(token)

        ok = [e for e in events if e.get("type") == "tool" and e.get("status") == "ok"]
        self.assertTrue(ok, f"no ok tool event: {events}")
        self.assertEqual(ok[0]["row_count"], 0)
        self.assertFalse(ok[0]["truncated"])


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