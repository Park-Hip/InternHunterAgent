from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from types import SimpleNamespace
import unittest
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from src.agents.runtime.prompts import ResolvedPromptBundle
from src.agents.runtime.react_agent import AgentRuntime
from src.agents.service import stream_agent_response
from src.agents.tracing.prompt_registry import ResolvedPrompt


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

    @staticmethod
    def _prompts(system_version: str) -> ResolvedPromptBundle:
        return ResolvedPromptBundle(
            system=ResolvedPrompt(
                "system",
                "resumi-system",
                system_version,
                system_version,
                None,
                False,
            ),
            schema_context=ResolvedPrompt(
                "schema_context", "resumi-schema-context", "schema", "31", None, False
            ),
            sql_generation=ResolvedPrompt(
                "sql_generation", "resumi-sql-generation", "SQL", "19", None, False
            ),
        )

    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config", return_value={})
    async def test_concurrent_streams_keep_their_resolved_system_agents(
        self,
        _mock_build_langfuse_config,
        mock_langfuse_request_trace,
    ) -> None:
        first_prompts = self._prompts("system-44")
        second_prompts = self._prompts("system-45")
        first_resolved = asyncio.Event()
        second_resolved = asyncio.Event()
        resolution_count = 0

        async def resolve_prompts() -> ResolvedPromptBundle:
            nonlocal resolution_count
            resolution_count += 1
            if resolution_count == 1:
                first_resolved.set()
                await second_resolved.wait()
                return first_prompts
            await first_resolved.wait()
            second_resolved.set()
            return second_prompts

        async def build_agent(**kwargs):
            system_prompt = kwargs.get("system_prompt")
            content = system_prompt.content if system_prompt is not None else "release"
            agent = MagicMock()

            async def stream(*_args, **_kwargs):
                yield self._chunk(content), {"langgraph_node": "model"}

            agent.astream = stream
            return agent

        mock_langfuse_request_trace.side_effect = lambda **_kwargs: self._trace_context(
            None
        )
        with (
            patch(
                "src.agents.runtime.react_agent.resolve_prompt_bundle_async",
                resolve_prompts,
            ),
            patch("src.agents.runtime.react_agent.agent_factory", build_agent),
        ):
            runtime = AgentRuntime()

            async def collect() -> list[str]:
                return [
                    event["text"]
                    async for event in runtime.astream("question")
                    if event["type"] == "token"
                ]

            first, second = await asyncio.gather(collect(), collect())

        self.assertEqual(first, ["system-44"])
        self.assertEqual(second, ["system-45"])

    @patch("src.agents.runtime.react_agent.langfuse_trace_url")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_yields_filtered_tokens_then_metadata(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_langfuse_trace_url,
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
        mock_langfuse_trace_url.return_value = (
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
                observation=latency,
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
            on_span_started=latency.attach_trace,
            prompts=ANY,
        )
        mock_langfuse_trace_url.assert_called_once_with(trace_id="trace-123")
        latency.complete.assert_called_once_with("success")

    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config", return_value={})
    async def test_astream_leaves_empty_stream_ttft_for_the_visible_fallback(
        self,
        _mock_build_langfuse_config,
        mock_langfuse_request_trace,
    ) -> None:
        # The tracing seam is stubbed exactly as its sibling tests stub it. Without
        # this the runtime opens a real Langfuse trace, so the assertion about a
        # None trace id only holds when credentials happen to be absent, and the
        # test reaches the network to find out.
        mock_langfuse_request_trace.return_value = self._trace_context(None)

        async def _fake_stream(*_args, **_kwargs):
            if False:
                yield None

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        latency = MagicMock()
        runtime = AgentRuntime(agent=fake_agent)

        events = [
            event async for event in runtime.astream("hello", observation=latency)
        ]

        self.assertEqual(
            events, [{"type": "metadata", "trace_id": None, "trace_url": None}]
        )
        latency.mark_user_visible.assert_not_called()
        latency.complete.assert_called_once_with("success")

    @patch("src.agents.runtime.react_agent.build_langfuse_config", return_value={})
    async def test_streaming_never_calls_the_langfuse_client(
        self,
        _mock_build_langfuse_config,
    ) -> None:
        """A finished turn does no client I/O: no trace URL lookup, no flush (#699).

        The request trace runs against a client whose `get_trace_url` and
        `flush` raise, and the project id stays unresolved, so an unreachable
        Langfuse cannot fail or delay the turn; the metadata still arrives with
        the trace id and a null trace URL.
        """

        async def _fake_stream(*_args, **_kwargs):
            yield (self._chunk(content="answer"), {"langgraph_node": "model"})

        async def resolve_prompts() -> ResolvedPromptBundle:
            return self._prompts("system-699")

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        client = MagicMock()
        client.get_current_trace_id.return_value = "trace-699"
        client.start_as_current_observation.return_value.__enter__.return_value = None
        client.start_as_current_observation.return_value.__exit__.return_value = None
        client.get_trace_url.side_effect = AssertionError(
            "get_trace_url is request-path I/O"
        )
        client.flush.side_effect = AssertionError("flush is request-path I/O")
        propagate = MagicMock()
        propagate.return_value.__enter__.return_value = None
        propagate.return_value.__exit__.return_value = None
        runtime = AgentRuntime(agent=fake_agent)

        with (
            patch(
                "src.agents.runtime.react_agent.resolve_prompt_bundle_async",
                resolve_prompts,
            ),
            patch("src.agents.tracing.langfuse._langfuse_handler", object()),
            patch(
                "src.agents.tracing.langfuse.get_langfuse_client",
                return_value=client,
            ),
            patch("src.agents.tracing.langfuse.propagate_attributes", propagate),
            patch("src.agents.tracing.langfuse._project_id", None),
        ):
            events = [event async for event in runtime.astream("hello")]

        self.assertEqual(
            events,
            [
                {"type": "token", "text": "answer"},
                {"type": "metadata", "trace_id": "trace-699", "trace_url": None},
            ],
        )
        client.get_trace_url.assert_not_called()
        client.flush.assert_not_called()

    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_streaming_keeps_the_request_trace_in_one_runtime_task(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
    ) -> None:
        current_trace: ContextVar[str | None] = ContextVar(
            "current_trace", default=None
        )

        @asynccontextmanager
        async def _request_trace(**_kwargs):
            token = current_trace.set("trace-stream")
            try:
                yield "trace-stream"
            finally:
                current_trace.reset(token)

        async def _fake_stream(*_args, **_kwargs):
            self.assertEqual(current_trace.get(), "trace-stream")
            yield (self._chunk(content="first"), {"langgraph_node": "model"})
            self.assertEqual(current_trace.get(), "trace-stream")
            yield (self._chunk(content="second"), {"langgraph_node": "model"})

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_langfuse_request_trace.side_effect = _request_trace
        runtime = AgentRuntime(agent=fake_agent)

        events = [
            event async for event in stream_agent_response("hello", runtime=runtime)
        ]

        self.assertEqual(
            [event["type"] for event in events],
            ["session", "token", "token", "metadata", "done"],
        )

    @patch("src.agents.runtime.react_agent.build_langfuse_config", return_value={})
    async def test_astream_disconnect_completes_the_observation_without_flushing(
        self,
        _mock_build_langfuse_config,
    ) -> None:
        """Closing the stream mid-flight ends the span as cancelled, with no client I/O.

        The flush that used to drain the trace on disconnect is gone (#699); the
        client is rigged to raise if `flush` is called.
        """

        async def _fake_stream(*_args, **_kwargs):
            yield (self._chunk(content="first token"), {"langgraph_node": "model"})
            await asyncio.Event().wait()

        async def resolve_prompts() -> ResolvedPromptBundle:
            return self._prompts("system-699")

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        client = MagicMock()
        client.get_current_trace_id.return_value = "trace-disconnect"
        client.start_as_current_observation.return_value.__enter__.return_value = None
        client.start_as_current_observation.return_value.__exit__.return_value = None
        client.flush.side_effect = AssertionError("flush is request-path I/O")
        propagate = MagicMock()
        propagate.return_value.__enter__.return_value = None
        propagate.return_value.__exit__.return_value = None
        runtime = AgentRuntime(agent=fake_agent)
        latency = MagicMock()

        with (
            patch(
                "src.agents.runtime.react_agent.resolve_prompt_bundle_async",
                resolve_prompts,
            ),
            patch("src.agents.tracing.langfuse._langfuse_handler", object()),
            patch(
                "src.agents.tracing.langfuse.get_langfuse_client",
                return_value=client,
            ),
            patch("src.agents.tracing.langfuse.propagate_attributes", propagate),
        ):
            stream = runtime.astream(
                "disconnect", session_id="session-disconnect", observation=latency
            )
            self.assertEqual(
                await anext(stream), {"type": "token", "text": "first token"}
            )
            await stream.aclose()

        client.flush.assert_not_called()
        latency.complete.assert_called_once_with("cancelled")

    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_does_not_leak_tool_calls_sql_or_raw_tool_output(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
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

    @patch("src.agents.runtime.react_agent.langfuse_trace_url")
    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_concurrent_requests_keep_their_context_and_trace_ids(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
        mock_langfuse_trace_url,
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
        mock_langfuse_trace_url.side_effect = lambda *, trace_id: (
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

    @patch("src.agents.runtime.react_agent.langfuse_request_trace")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_cancels_the_producer_and_closes_its_trace_on_disconnect(
        self,
        mock_build_langfuse_config,
        mock_langfuse_request_trace,
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
