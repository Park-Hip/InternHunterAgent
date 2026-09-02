from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain.messages import AIMessage, HumanMessage

from src.agents.runtime.react_agent import AgentRuntime
from src.agents.service import (
    FALLBACK_ANSWER,
    generate_agent_response,
    stream_agent_response,
)


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    @asynccontextmanager
    async def _trace_context(trace_id: str | None):
        yield trace_id

    @staticmethod
    def _chunk(
        content: str,
        tool_call_chunks: list[dict[str, str]] | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(content=content, tool_call_chunks=tool_call_chunks or [])

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_ainvoke_builds_message_payload_and_returns_request_trace_id(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_get_langfuse_client,
    ) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {
            "messages": [
                HumanMessage(content="what time is it?"),
                AIMessage(content="The current time is 14:01:52."),
            ]
        }
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.return_value = self._trace_context("trace-123")
        mock_client = mock_get_langfuse_client.return_value
        mock_client.get_trace_url.return_value = (
            "https://cloud.langfuse.com/project/p/traces/trace-123"
        )
        runtime = AgentRuntime(agent=fake_agent)

        result = await runtime.ainvoke(
            "what time is it?", session_id="session-1", user_id="user-1"
        )

        self.assertEqual(
            result,
            {
                "answer": "The current time is 14:01:52.",
                "trace_id": "trace-123",
                "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-123",
            },
        )
        mock_build_langfuse_config.assert_called_once_with(entry_point="api:chat")
        mock_langfuse_request_trace.assert_called_once_with(
            entry_point="api:chat",
            trace_name="agent-chat",
            session_id="session-1",
            user_id="user-1",
        )
        fake_agent.ainvoke.assert_awaited_once_with(
            {"messages": [HumanMessage(content="what time is it?")]},
            config={
                "callbacks": ["handler"],
                "configurable": {"thread_id": "session-1"},
            },
        )
        mock_client.flush.assert_called_once()
        mock_client.get_trace_url.assert_called_once_with(trace_id="trace-123")

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_yields_filtered_tokens_then_metadata(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_get_langfuse_client,
    ) -> None:
        async def _fake_stream(*_args, **_kwargs):
            yield (
                self._chunk(
                    content="",
                    tool_call_chunks=[{"name": "query_clean_jobs", "args": "{}"}],
                ),
                {"langgraph_node": "model"},
            )
            yield (
                self._chunk(content="SELECT id FROM clean_jobs"),
                {"langgraph_node": "tools"},
            )
            yield (self._chunk(content="There are "), {"langgraph_node": "model"})
            yield (self._chunk(content="3 roles."), {"langgraph_node": "model"})

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.return_value = self._trace_context("trace-123")
        mock_client = mock_get_langfuse_client.return_value
        mock_client.get_trace_url.return_value = (
            "https://cloud.langfuse.com/project/p/traces/trace-123"
        )
        runtime = AgentRuntime(agent=fake_agent)
        latency = MagicMock()

        events = [
            event
            async for event in runtime.astream(
                "list 3 data engineer jobs",
                session_id="session-1",
                user_id="user-1",
                latency=latency,
            )
        ]

        self.assertEqual(
            events,
            [
                {"type": "token", "text": "There are "},
                {"type": "token", "text": "3 roles."},
                {
                    "type": "metadata",
                    "trace_id": "trace-123",
                    "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-123",
                },
            ],
        )
        mock_build_langfuse_config.assert_called_once_with(
            entry_point="api:chat-stream"
        )
        mock_langfuse_request_trace.assert_called_once_with(
            entry_point="api:chat-stream",
            trace_name="agent-chat-stream",
            session_id="session-1",
            user_id="user-1",
        )
        mock_client.flush.assert_called_once()
        mock_client.get_trace_url.assert_called_once_with(trace_id="trace-123")
        latency.complete.assert_called_once_with("success")

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_streaming_flushes_exports_before_emitting_the_trace_url(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_get_langfuse_client,
    ) -> None:
        """The trace is readable server-side before its URL reaches the client."""
        call_order: list[str] = []

        async def _fake_stream(*_args, **_kwargs):
            yield (self._chunk(content="answer"), {"langgraph_node": "model"})

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.return_value = self._trace_context("trace-123")
        mock_client = mock_get_langfuse_client.return_value
        mock_client.flush.side_effect = lambda: call_order.append("flush")
        mock_client.get_trace_url.return_value = "https://traces/trace-123"
        runtime = AgentRuntime(agent=fake_agent)

        stream = stream_agent_response("hello", runtime=runtime, session_id="session-1")
        async for event in stream:
            call_order.append(f"event:{event['type']}")

        self.assertEqual(
            call_order,
            [
                "event:session",
                "event:token",
                "flush",
                "event:metadata",
                "event:done",
            ],
        )
        mock_client.flush.assert_called_once()

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_flushes_exports_when_the_consumer_disconnects(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_get_langfuse_client,
    ) -> None:
        """Closing the stream mid-flight still drains the trace to Langfuse."""

        @asynccontextmanager
        async def _request_trace(**_kwargs):
            yield "trace-disconnect"

        async def _fake_stream(*_args, **_kwargs):
            yield (self._chunk(content="first token"), {"langgraph_node": "model"})
            await asyncio.Event().wait()

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.side_effect = _request_trace
        mock_client = mock_get_langfuse_client.return_value
        runtime = AgentRuntime(agent=fake_agent)
        latency = MagicMock()

        stream = runtime.astream(
            "disconnect", session_id="session-disconnect", latency=latency
        )
        self.assertEqual(await anext(stream), {"type": "token", "text": "first token"})
        await stream.aclose()

        mock_client.flush.assert_called_once()
        latency.complete.assert_called_once_with("cancelled")

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_does_not_leak_tool_calls_sql_or_raw_tool_output(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        _mock_get_langfuse_client,
    ) -> None:
        async def _fake_stream(*_args, **_kwargs):
            yield (
                self._chunk(
                    content="",
                    tool_call_chunks=[{"name": "query_clean_jobs", "args": "{}"}],
                ),
                {"langgraph_node": "model"},
            )
            yield (
                self._chunk(content="SELECT id FROM clean_jobs"),
                {"langgraph_node": "tools"},
            )
            yield (
                self._chunk(content="There are 3 roles."),
                {"langgraph_node": "model"},
            )

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {}
        mock_langfuse_request_trace.return_value = self._trace_context(None)
        runtime = AgentRuntime(agent=fake_agent)

        events = [event async for event in runtime.astream("list 3 data engineer jobs")]
        streamed_text = "".join(
            event["text"] for event in events if event["type"] == "token"
        )

        self.assertEqual(streamed_text, "There are 3 roles.")
        self.assertNotIn("SELECT", streamed_text)
        self.assertNotIn("clean_jobs", streamed_text)
        self.assertNotIn("query_clean_jobs", streamed_text)
        self.assertNotIn("list 3 data engineer jobs", streamed_text)

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_ainvoke_omits_thread_id_when_no_session_id(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_get_langfuse_client,
    ) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {
            "messages": [AIMessage(content="The current time is 14:01:52.")]
        }
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.return_value = self._trace_context(None)
        runtime = AgentRuntime(agent=fake_agent)

        result = await runtime.ainvoke("what time is it?")

        fake_agent.ainvoke.assert_awaited_once_with(
            {"messages": [HumanMessage(content="what time is it?")]},
            config={"callbacks": ["handler"]},
        )
        self.assertIsNone(result["trace_url"])
        mock_get_langfuse_client.return_value.get_trace_url.assert_not_called()

    def test_extract_answer_returns_empty_string_on_invalid_response(self) -> None:
        runtime = AgentRuntime(agent=AsyncMock())

        self.assertEqual(runtime._extract_answer({"messages": []}), "")
        self.assertEqual(runtime._extract_answer("oops"), "")
        self.assertEqual(runtime._extract_answer(None), "")
        self.assertEqual(
            runtime._extract_answer({"messages": [AIMessage(content="")]}), ""
        )
        self.assertEqual(
            runtime._extract_answer({"messages": [AIMessage(content="   ")]}), ""
        )

        class _NonStringContent:
            content = 123

        self.assertEqual(
            runtime._extract_answer({"messages": [_NonStringContent()]}), ""
        )

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.record_agent_response_failure")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_ainvoke_returns_empty_answer_when_agent_returns_no_messages(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_record_agent_response_failure,
        _mock_get_langfuse_client,
    ) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {"messages": []}
        mock_build_langfuse_config.return_value = {}
        mock_langfuse_request_trace.return_value = self._trace_context(None)

        result = await AgentRuntime(agent=fake_agent).ainvoke("what time is it?")

        self.assertEqual(result["answer"], "")
        self.assertEqual(result["failure_category"], "messages_empty")
        mock_record_agent_response_failure.assert_called_once_with(
            category="messages_empty"
        )

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_generate_agent_response_falls_back_on_empty_agent_answer(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        _mock_get_langfuse_client,
    ) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {"messages": []}
        mock_build_langfuse_config.return_value = {}
        mock_langfuse_request_trace.return_value = self._trace_context(None)
        runtime = AgentRuntime(agent=fake_agent)

        result = await generate_agent_response(
            query="what time is it?", runtime=runtime
        )

        self.assertEqual(result["answer"], FALLBACK_ANSWER)

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    @patch("src.agents.tracing.langfuse.get_langfuse_client")
    @patch("src.agents.tracing.langfuse._langfuse_handler", object())
    async def test_malformed_response_records_failure_category_on_enabled_trace(
        self,
        mock_tracing_get_client,
        mock_build_langfuse_config,
        mock_runtime_get_client,
    ) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {"messages": []}
        client = MagicMock()
        client.get_current_trace_id.return_value = "trace-malformed"
        mock_tracing_get_client.return_value = client
        mock_runtime_get_client.return_value = client
        mock_build_langfuse_config.return_value = {}

        result = await generate_agent_response(
            query="what time is it?", runtime=AgentRuntime(agent=fake_agent)
        )

        self.assertEqual(result["answer"], FALLBACK_ANSWER)
        client.update_current_span.assert_called_once_with(
            metadata={"agent_response_failure_category": "messages_empty"},
            level="WARNING",
        )

    def test_extract_answer_classifies_malformed_response_shapes(self) -> None:
        runtime = AgentRuntime(agent=AsyncMock())

        class _NonStringContent:
            content = 123

        cases = (
            ("oops", "response_not_dict"),
            ({}, "messages_missing"),
            ({"messages": "oops"}, "messages_not_list"),
            ({"messages": []}, "messages_empty"),
            ({"messages": [_NonStringContent()]}, "message_content_not_text"),
            ({"messages": [AIMessage(content="   ")]}, "message_content_empty"),
        )

        for response, expected_category in cases:
            with self.subTest(response=response):
                answer, category = runtime._extract_answer_with_failure_category(response)
                self.assertEqual(answer, "")
                self.assertEqual(category, expected_category)

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_ainvoke_concurrent_requests_keep_their_context_and_trace_ids(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_get_langfuse_client,
    ) -> None:
        current_trace_id: ContextVar[str | None] = ContextVar(
            "current_trace_id", default=None
        )
        barrier = asyncio.Barrier(2)
        observed_contexts: dict[str, str | None] = {}

        @asynccontextmanager
        async def _request_trace(**kwargs):
            trace_id = f"trace-{kwargs['session_id']}"
            token = current_trace_id.set(trace_id)
            try:
                yield trace_id
            finally:
                current_trace_id.reset(token)

        async def _fake_invoke(messages, **_kwargs):
            query = messages["messages"][0].content
            await barrier.wait()
            observed_contexts[query] = current_trace_id.get()
            return {"messages": [AIMessage(content=query)]}

        fake_agent = AsyncMock()
        fake_agent.ainvoke.side_effect = _fake_invoke
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.side_effect = _request_trace
        mock_client = mock_get_langfuse_client.return_value
        mock_client.get_trace_url.side_effect = lambda *, trace_id: (
            f"https://traces/{trace_id}"
        )
        runtime = AgentRuntime(agent=fake_agent)

        first, second = await asyncio.gather(
            runtime.ainvoke("first", session_id="first"),
            runtime.ainvoke("second", session_id="second"),
        )

        self.assertEqual(
            observed_contexts,
            {"first": "trace-first", "second": "trace-second"},
        )
        self.assertEqual(first["trace_id"], "trace-first")
        self.assertEqual(second["trace_id"], "trace-second")
        self.assertEqual(first["trace_url"], "https://traces/trace-first")
        self.assertEqual(second["trace_url"], "https://traces/trace-second")

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_concurrent_requests_keep_their_context_and_trace_ids(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_get_langfuse_client,
    ) -> None:
        """Suspended streams retain independent Langfuse context and trace URLs."""
        current_trace_id: ContextVar[str | None] = ContextVar(
            "current_trace_id", default=None
        )
        barrier = asyncio.Barrier(2)
        observed_contexts: dict[str, str | None] = {}
        closed_trace_ids: set[str] = set()

        @asynccontextmanager
        async def _request_trace(**kwargs):
            trace_id = f"trace-{kwargs['session_id']}"
            token = current_trace_id.set(trace_id)
            try:
                yield trace_id
            finally:
                closed_trace_ids.add(trace_id)
                current_trace_id.reset(token)

        async def _fake_stream(messages, **_kwargs):
            query = messages["messages"][0].content
            await barrier.wait()
            observed_contexts[query] = current_trace_id.get()
            yield (self._chunk(content=query), {"langgraph_node": "model"})

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.side_effect = _request_trace
        mock_client = mock_get_langfuse_client.return_value
        mock_client.get_trace_url.side_effect = lambda *, trace_id: (
            f"https://traces/{trace_id}"
        )
        runtime = AgentRuntime(agent=fake_agent)

        async def _collect(query: str) -> dict[str, str | None]:
            events = [event async for event in runtime.astream(query, session_id=query)]
            return events[-1]

        first, second = await asyncio.gather(_collect("first"), _collect("second"))

        self.assertEqual(
            observed_contexts, {"first": "trace-first", "second": "trace-second"}
        )
        self.assertEqual(closed_trace_ids, {"trace-first", "trace-second"})
        self.assertEqual(first["trace_id"], "trace-first")
        self.assertEqual(second["trace_id"], "trace-second")
        self.assertEqual(first["trace_url"], "https://traces/trace-first")
        self.assertEqual(second["trace_url"], "https://traces/trace-second")

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_cancels_the_producer_and_closes_its_trace_on_disconnect(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        _mock_get_langfuse_client,
    ) -> None:
        producer_cancelled = asyncio.Event()
        trace_closed = asyncio.Event()

        @asynccontextmanager
        async def _request_trace(**_kwargs):
            try:
                yield "trace-disconnect"
            finally:
                trace_closed.set()

        async def _fake_stream(*_args, **_kwargs):
            try:
                yield (self._chunk(content="first token"), {"langgraph_node": "model"})
                await asyncio.Event().wait()
            finally:
                producer_cancelled.set()

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.side_effect = _request_trace
        runtime = AgentRuntime(agent=fake_agent)

        stream = runtime.astream("disconnect", session_id="session-disconnect")
        self.assertEqual(await anext(stream), {"type": "token", "text": "first token"})
        await stream.aclose()

        self.assertTrue(producer_cancelled.is_set())
        self.assertTrue(trace_closed.is_set())
