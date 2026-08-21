from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain.messages import AIMessage, HumanMessage

from src.agents.runtime.react_agent import AgentRuntime
from src.agents.service import FALLBACK_ANSWER, generate_agent_response


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def _chunk(
        self,
        content: str,
        tool_call_chunks: list[dict[str, str]] | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(content=content, tool_call_chunks=tool_call_chunks or [])

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.get_langfuse_handler")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_ainvoke_builds_message_payload_and_returns_answer_and_trace_id(
        self,
        mock_build_langfuse_config,
        mock_get_langfuse_handler,
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
        mock_handler = mock_get_langfuse_handler.return_value
        mock_handler.last_trace_id = "trace-123"
        mock_client = mock_get_langfuse_client.return_value
        mock_client.get_trace_url.return_value = "https://cloud.langfuse.com/project/p/traces/trace-123"
        runtime = AgentRuntime(agent=fake_agent)

        result = await runtime.ainvoke("what time is it?", session_id="session-1", user_id="user-1")

        self.assertEqual(
            result,
            {
                "answer": "The current time is 14:01:52.",
                "trace_id": "trace-123",
                "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-123",
            },
        )
        mock_client.get_trace_url.assert_called_once_with(trace_id="trace-123")
        mock_build_langfuse_config.assert_called_once_with(
            session_id="session-1",
            user_id="user-1",
            entry_point="api:chat",
        )
        fake_agent.ainvoke.assert_awaited_once_with(
            {"messages": [HumanMessage(content="what time is it?")]},
            config={
                "callbacks": ["handler"],
                "configurable": {"thread_id": "session-1"},
            },
        )
        mock_client.flush.assert_called_once()
        payload = fake_agent.ainvoke.await_args.args[0]
        self.assertIn("messages", payload)
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0].content, "what time is it?")

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.get_langfuse_handler")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_yields_filtered_tokens_then_metadata(
        self,
        mock_build_langfuse_config,
        mock_get_langfuse_handler,
        mock_get_langfuse_client,
    ) -> None:
        async def _fake_stream(*args, **kwargs):
            yield (
                self._chunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "query_clean_jobs",
                            "args": '{"query": "list 3 data engineer jobs"}',
                        }
                    ],
                ),
                {"langgraph_node": "model"},
            )
            yield (
                self._chunk(content="SELECT id, title FROM clean_jobs"),
                {"langgraph_node": "tools"},
            )
            yield (self._chunk(content="There are "), {"langgraph_node": "model"})
            yield (self._chunk(content="3 roles."), {"langgraph_node": "model"})

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_handler = mock_get_langfuse_handler.return_value
        mock_handler.last_trace_id = "trace-123"
        mock_client = mock_get_langfuse_client.return_value
        mock_client.get_trace_url.return_value = "https://cloud.langfuse.com/project/p/traces/trace-123"
        runtime = AgentRuntime(agent=fake_agent)

        stream = runtime.astream("list 3 data engineer jobs", session_id="session-1", user_id="user-1")
        self.assertTrue(hasattr(stream, "__aiter__"))
        events = [event async for event in stream]

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
            session_id="session-1",
            user_id="user-1",
            entry_point="api:chat-stream",
        )
        mock_client.flush.assert_called_once()
        mock_client.get_trace_url.assert_called_once_with(trace_id="trace-123")

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.get_langfuse_handler")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_astream_does_not_leak_tool_calls_sql_or_raw_tool_output(
        self,
        mock_build_langfuse_config,
        mock_get_langfuse_handler,
        mock_get_langfuse_client,
    ) -> None:
        async def _fake_stream(*args, **kwargs):
            yield (
                self._chunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "query_clean_jobs",
                            "args": '{"query": "list 3 data engineer jobs"}',
                        }
                    ],
                ),
                {"langgraph_node": "model"},
            )
            yield (
                self._chunk(content="SELECT id, title FROM clean_jobs"),
                {"langgraph_node": "tools"},
            )
            yield (self._chunk(content="There are "), {"langgraph_node": "model"})
            yield (self._chunk(content="3 roles."), {"langgraph_node": "model"})

        fake_agent = AsyncMock()
        fake_agent.astream = _fake_stream
        mock_build_langfuse_config.return_value = {}
        mock_get_langfuse_handler.return_value.last_trace_id = None
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
    @patch("src.agents.runtime.react_agent.get_langfuse_handler")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_ainvoke_omits_thread_id_when_no_session_id(
        self,
        mock_build_langfuse_config,
        mock_get_langfuse_handler,
        mock_get_langfuse_client,
    ) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {
            "messages": [AIMessage(content="The current time is 14:01:52.")]
        }
        mock_build_langfuse_config.return_value = {"callbacks": ["handler"]}
        mock_get_langfuse_handler.return_value.last_trace_id = None
        mock_client = mock_get_langfuse_client.return_value
        runtime = AgentRuntime(agent=fake_agent)

        result = await runtime.ainvoke("what time is it?")

        fake_agent.ainvoke.assert_awaited_once_with(
            {"messages": [HumanMessage(content="what time is it?")]},
            config={"callbacks": ["handler"]},
        )
        self.assertIsNone(result["trace_url"])
        mock_client.get_trace_url.assert_not_called()

    def test_extract_answer_returns_empty_string_on_empty_messages(self) -> None:
        runtime = AgentRuntime(agent=AsyncMock())

        self.assertEqual(runtime._extract_answer({"messages": []}), "")

    def test_extract_answer_returns_empty_string_on_non_dict_response(self) -> None:
        runtime = AgentRuntime(agent=AsyncMock())

        self.assertEqual(runtime._extract_answer("oops"), "")
        self.assertEqual(runtime._extract_answer(None), "")

    def test_extract_answer_returns_empty_string_on_unreadable_final_content(self) -> None:
        runtime = AgentRuntime(agent=AsyncMock())

        self.assertEqual(
            runtime._extract_answer({"messages": [AIMessage(content="")]}), ""
        )
        self.assertEqual(
            runtime._extract_answer({"messages": [AIMessage(content="   ")]}), ""
        )
        class _NonStrContent:
            content = 123

        self.assertEqual(
            runtime._extract_answer({"messages": [_NonStrContent()]}), ""
        )

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.get_langfuse_handler")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_ainvoke_returns_empty_answer_when_no_messages(
        self,
        mock_build_langfuse_config,
        mock_get_langfuse_handler,
        mock_get_langfuse_client,
    ) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {"messages": []}
        mock_build_langfuse_config.return_value = {}
        mock_get_langfuse_handler.return_value.last_trace_id = None
        runtime = AgentRuntime(agent=fake_agent)

        result = await runtime.ainvoke("what time is it?")

        self.assertEqual(result["answer"], "")

    @patch("src.agents.runtime.react_agent.get_langfuse_client")
    @patch("src.agents.runtime.react_agent.get_langfuse_handler")
    @patch("src.agents.runtime.react_agent.build_langfuse_config")
    async def test_generate_agent_response_falls_back_on_empty_agent_answer(
        self,
        mock_build_langfuse_config,
        mock_get_langfuse_handler,
        mock_get_langfuse_client,
    ) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {"messages": []}
        mock_build_langfuse_config.return_value = {}
        mock_get_langfuse_handler.return_value.last_trace_id = None
        runtime = AgentRuntime(agent=fake_agent)

        result = await generate_agent_response(query="what time is it?", runtime=runtime)

        self.assertEqual(result["answer"], FALLBACK_ANSWER)
