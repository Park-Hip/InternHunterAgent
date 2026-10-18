"""Pin #671: an interrupted tool call must not break the conversation.

A turn cancelled while a tool runs is checkpointed mid-step: the assistant's
tool call has no tool result, and a provider rejects the replay of that
history. These tests cover the repair middleware in isolation and through a
real graph whose checkpoint a cancellation leaves mid-tool, then run the next
turn exactly as a user would.

No network, no credentials, no database.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import unittest

from pydantic import PrivateAttr

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Overwrite

from src.agents.runtime.middleware import (
    INTERRUPTED_TOOL_CALL_CONTENT,
    build_interrupted_tool_call_repair_middleware,
)


def _tool_call(call_id: str, name: str = "query_clean_jobs") -> dict:
    return {"name": name, "args": {"question": "Hà Nội"}, "id": call_id}


def _dangling_tool_call_ids(messages) -> set[str]:
    """The ids an assistant asked for that no tool message answers."""
    answered = {
        message.tool_call_id for message in messages if isinstance(message, ToolMessage)
    }
    return {
        call["id"]
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call.get("id") and call["id"] not in answered
    }


class InterruptedToolCallRepairUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.middleware = build_interrupted_tool_call_repair_middleware()

    def test_one_dangling_call_is_answered_directly_after_the_call(self) -> None:
        question = HumanMessage(content="Có bao nhiêu tin ở Hà Nội?")
        call = AIMessage(content="", tool_calls=[_tool_call("call_671")])

        update = self.middleware.before_model({"messages": [question, call]}, None)

        self.assertIsInstance(update["messages"], Overwrite)
        repaired = update["messages"].value
        self.assertEqual(len(repaired), 3)
        self.assertIs(repaired[0], question)
        self.assertIs(repaired[1], call)
        synthetic = repaired[2]
        self.assertIsInstance(synthetic, ToolMessage)
        self.assertEqual(synthetic.tool_call_id, "call_671")
        self.assertEqual(synthetic.name, "query_clean_jobs")
        self.assertEqual(synthetic.status, "error")
        self.assertEqual(synthetic.content, INTERRUPTED_TOOL_CALL_CONTENT)

    def test_only_the_missing_id_is_answered_when_a_real_result_exists(self) -> None:
        question = HumanMessage(content="question")
        call = AIMessage(
            content="",
            tool_calls=[_tool_call("call_1"), _tool_call("call_2")],
        )
        real_result = ToolMessage(content="result one", tool_call_id="call_1")

        update = self.middleware.before_model(
            {"messages": [question, call, real_result]}, None
        )

        repaired = update["messages"].value
        self.assertEqual(len(repaired), 4)
        self.assertIs(repaired[1], call)
        synthetic = repaired[2]
        self.assertIsInstance(synthetic, ToolMessage)
        self.assertEqual(synthetic.tool_call_id, "call_2")
        self.assertEqual(synthetic.status, "error")
        # The real result is kept, after the repair of the missing id.
        self.assertIs(repaired[3], real_result)
        self.assertEqual(_dangling_tool_call_ids(repaired), set())

    def test_each_dangling_call_of_repeated_assistant_turns_is_answered(self) -> None:
        first = AIMessage(content="", tool_calls=[_tool_call("call_1")])
        second = AIMessage(content="", tool_calls=[_tool_call("call_2")])

        update = self.middleware.before_model(
            {"messages": [HumanMessage(content="one"), first, second]}, None
        )

        repaired = update["messages"].value
        synthetic = [
            message for message in repaired if isinstance(message, ToolMessage)
        ]
        self.assertEqual(
            [message.tool_call_id for message in synthetic], ["call_1", "call_2"]
        )
        self.assertEqual(_dangling_tool_call_ids(repaired), set())

    def test_a_healthy_thread_produces_no_state_update(self) -> None:
        healthy = [
            HumanMessage(content="question"),
            AIMessage(content="", tool_calls=[_tool_call("call_1")]),
            ToolMessage(content="result", tool_call_id="call_1"),
            AIMessage(content="answer"),
        ]

        self.assertIsNone(self.middleware.before_model({"messages": healthy}, None))


class InterruptedToolCallRepairAsyncHookTests(unittest.IsolatedAsyncioTestCase):
    async def test_abefore_model_repairs_like_before_model(self) -> None:
        middleware = build_interrupted_tool_call_repair_middleware()
        question = HumanMessage(content="question")
        call = AIMessage(content="", tool_calls=[_tool_call("call_671")])

        update = await middleware.abefore_model({"messages": [question, call]}, None)

        self.assertIsInstance(update["messages"], Overwrite)
        repaired = update["messages"].value
        self.assertEqual(
            [type(message).__name__ for message in repaired],
            ["HumanMessage", "AIMessage", "ToolMessage"],
        )


class _ScriptedToolCallingModel(GenericFakeChatModel):
    """Asks for the tool when the latest turn has no result, else answers.

    This mirrors the model the runtime serves: it can retry a call the repair
    answered synthetically, because the thread is a valid sequence again.
    """

    messages: list = []
    _seen: list = PrivateAttr(default_factory=list)
    _calls: int = PrivateAttr(default=0)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self._seen.append(list(messages))
        latest_human = max(
            index
            for index, message in enumerate(messages)
            if isinstance(message, HumanMessage)
        )
        answered = any(
            isinstance(message, ToolMessage) for message in messages[latest_human + 1 :]
        )
        if answered:
            answer = AIMessage(content="Còn 11 tin ở Đà Nẵng.")
        else:
            self._calls += 1
            answer = AIMessage(
                content="", tool_calls=[_tool_call(f"call_{self._calls}")]
            )
        return ChatResult(generations=[ChatGeneration(message=answer)])

    def bind_tools(self, tool_specs, **kwargs):
        return self

    def _chunks(self, messages, stop=None, run_manager=None, **kwargs):
        for generation in self._generate(
            messages, stop, run_manager, **kwargs
        ).generations:
            message = generation.message
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=message.content,
                    tool_calls=getattr(message, "tool_calls", None) or [],
                    id=message.id,
                )
            )

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        yield from self._chunks(messages, stop, run_manager, **kwargs)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self._chunks(messages, stop, run_manager, **kwargs):
            yield chunk

    @property
    def seen(self) -> list:
        return self._seen


class InterruptedToolCallRepairGraphTests(unittest.IsolatedAsyncioTestCase):
    async def _cancel_mid_tool(
        self, agent, config, tool_started: asyncio.Event
    ) -> None:
        async def consume() -> None:
            async for _update in agent.astream(
                {
                    "messages": [
                        HumanMessage(content="Có bao nhiêu tin tuyển dụng ở Hà Nội?")
                    ]
                },
                config=config,
            ):
                pass

        task = asyncio.create_task(consume())
        await asyncio.wait_for(tool_started.wait(), timeout=10)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def test_a_cancelled_tool_call_is_repaired_on_the_next_turn(self) -> None:
        tool_started = asyncio.Event()
        release_tool = asyncio.Event()

        @tool
        async def query_clean_jobs(question: str) -> str:
            """Search job postings."""
            tool_started.set()
            await release_tool.wait()
            return "214 results"

        model = _ScriptedToolCallingModel()
        agent = create_agent(
            model=model,
            tools=[query_clean_jobs],
            checkpointer=InMemorySaver(),
            middleware=[build_interrupted_tool_call_repair_middleware()],
        )
        config = {"configurable": {"thread_id": "interrupted-tool-call"}}

        await self._cancel_mid_tool(agent, config, tool_started)

        # The cancellation leaves the half-finished step in storage: the call
        # with no result, which is what every later turn would replay.
        damaged = (await agent.aget_state(config)).values["messages"]
        self.assertEqual(
            [type(message).__name__ for message in damaged],
            ["HumanMessage", "AIMessage"],
        )
        self.assertEqual(_dangling_tool_call_ids(damaged), {"call_1"})

        # The repair does not stop the model from calling the tool again for the
        # new question; release the gate so that retry returns instead of blocking.
        release_tool.set()
        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [HumanMessage(content="Còn ở Đà Nẵng thì sao?")]},
                config=config,
            ),
            timeout=10,
        )

        self.assertEqual(result["messages"][-1].content, "Còn 11 tin ở Đà Nẵng.")
        turn_two_input = model.seen[1]
        self.assertEqual(
            [type(message).__name__ for message in turn_two_input],
            ["HumanMessage", "AIMessage", "ToolMessage", "HumanMessage"],
        )
        synthetic = turn_two_input[2]
        self.assertEqual(synthetic.tool_call_id, "call_1")
        self.assertEqual(synthetic.status, "error")
        self.assertEqual(synthetic.content, INTERRUPTED_TOOL_CALL_CONTENT)
        self.assertEqual(turn_two_input[3].content, "Còn ở Đà Nẵng thì sao?")

        # The repair is stored directly after the call, and the model retried
        # the tool for the new question, so the thread holds a valid sequence.
        stored = (await agent.aget_state(config)).values["messages"]
        self.assertEqual(_dangling_tool_call_ids(stored), set())
        self.assertIsInstance(stored[2], ToolMessage)
        self.assertEqual(stored[2].tool_call_id, "call_1")
        self.assertEqual(
            [
                message.tool_call_id
                for message in stored
                if isinstance(message, ToolMessage)
            ],
            ["call_1", "call_2"],
        )


if __name__ == "__main__":
    unittest.main()
