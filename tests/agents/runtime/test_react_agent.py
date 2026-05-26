from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from langchain.messages import AIMessage, HumanMessage

from src.agents.runtime.react_agent import AgentRuntime


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_ainvoke_builds_message_payload_and_returns_last_message_content(self) -> None:
        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {
            "messages": [
                HumanMessage(content="what time is it?"),
                AIMessage(content="The current time is 14:01:52."),
            ]
        }
        runtime = AgentRuntime(agent=fake_agent)

        answer = await runtime.ainvoke("what time is it?")

        self.assertEqual(answer, "The current time is 14:01:52.")
        fake_agent.ainvoke.assert_awaited_once()
        payload = fake_agent.ainvoke.await_args.args[0]
        self.assertIn("messages", payload)
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0].content, "what time is it?")

