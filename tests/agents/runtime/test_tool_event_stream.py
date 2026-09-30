"""Prove tool events actually reach the public stream, end to end.

The middleware tests assert the seam in isolation. This drives a real LangGraph
agent through `AgentRuntime.astream` with a scripted fake model, and asserts the
tool lifecycle appears in the emitted events. It is the test that would fail if
the emitter binding, the context propagation into the producer task, or the
service's event forwarding were wrong.

No network, no credentials, no database.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import tool

from src.agents.runtime.middleware import build_tool_observation_middleware
from src.agents.runtime.react_agent import AgentRuntime


@tool
def query_clean_jobs(question: str) -> str:
    """Search job postings."""
    return "Tìm thấy 214 kết quả với các cột: id, title, company."


class _ScriptedToolCallingModel(GenericFakeChatModel):
    """Calls a tool once, then answers using the result.

    Parameterised so a test can point it at its own tool without redefining the
    scripted sequence.
    """

    messages: list = []
    tool_name: str = "query_clean_jobs"
    tool_arg: str = "question"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        already_called = any(getattr(m, "type", None) == "tool" for m in messages)
        if not already_called:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.tool_name,
                        "args": {self.tool_arg: "AI Engineer ở Đà Nẵng"},
                        "id": "call_1",
                    }
                ],
            )
        else:
            message = AIMessage(content="Có 214 tin phù hợp.")
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tool_specs, **kwargs):
        return self

    def _chunks(self, messages, stop=None, run_manager=None, **kwargs):
        for generation in self._generate(
            messages, stop, run_manager, **kwargs
        ).generations:
            m = generation.message
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=m.content,
                    tool_calls=getattr(m, "tool_calls", None) or [],
                    id=m.id,
                )
            )

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        yield from self._chunks(messages, stop, run_manager, **kwargs)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self._chunks(messages, stop, run_manager, **kwargs):
            yield chunk


class ToolEventStreamTests(unittest.IsolatedAsyncioTestCase):
    async def _collect(self) -> list[dict]:
        agent = create_agent(
            model=_ScriptedToolCallingModel(),
            tools=[query_clean_jobs],
            middleware=[build_tool_observation_middleware()],
        )
        runtime = AgentRuntime(agent=agent)

        with patch(
            "src.agents.runtime.react_agent.get_langfuse_client", return_value=None
        ), patch("src.agents.runtime.react_agent.langfuse_request_trace") as trace, patch(
            "src.agents.runtime.react_agent.build_langfuse_config", return_value={}
        ):
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def _null_trace(*args, **kwargs):
                yield None

            trace.return_value = _null_trace()
            return [event async for event in runtime.astream("xin chào")]

    async def test_tool_lifecycle_reaches_the_stream(self) -> None:
        events = await self._collect()
        tool_events = [e for e in events if e.get("type") == "tool"]

        self.assertTrue(tool_events, f"no tool event reached the stream: {events}")
        self.assertEqual([e["status"] for e in tool_events], ["running", "ok"])
        self.assertEqual(tool_events[0]["name"], "query_clean_jobs")
        self.assertEqual(tool_events[0]["call_id"], "call_1")
        self.assertEqual(
            tool_events[0]["arguments"], {"question": "AI Engineer ở Đà Nẵng"}
        )
        self.assertIsInstance(tool_events[-1]["duration_ms"], int)

    async def test_tool_events_arrive_before_the_answer(self) -> None:
        """A card is only useful while the agent is still working, so the tool
        event must precede the first token."""
        events = await self._collect()
        types = [e.get("type") for e in events]
        self.assertIn("tool", types)
        self.assertIn("token", types)
        self.assertLess(
            types.index("tool"),
            types.index("token"),
            f"tool event must precede the first token, got {types}",
        )


if __name__ == "__main__":
    unittest.main()