from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from langchain.messages import AIMessage, HumanMessage

from src.agents.runtime.react_agent import AgentRuntime


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
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
        runtime = AgentRuntime(agent=fake_agent)

        result = await runtime.ainvoke("what time is it?", session_id="session-1", user_id="user-1")

        self.assertEqual(
            result,
            {
                "answer": "The current time is 14:01:52.",
                "trace_id": "trace-123",
            },
        )
        mock_build_langfuse_config.assert_called_once_with(session_id="session-1", user_id="user-1")
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
        runtime = AgentRuntime(agent=fake_agent)

        await runtime.ainvoke("what time is it?")

        fake_agent.ainvoke.assert_awaited_once_with(
            {"messages": [HumanMessage(content="what time is it?")]},
            config={"callbacks": ["handler"]},
        )

    def test_extract_answer_raises_on_empty_messages(self) -> None:
        runtime = AgentRuntime(agent=AsyncMock())

        with self.assertRaises(ValueError) as ctx:
            runtime._extract_answer({"messages": []})

        self.assertIn("did not contain any messages", str(ctx.exception))
