from __future__ import annotations

import unittest
import uuid
from unittest.mock import AsyncMock

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from src.agents.runtime.middleware import build_trim_middleware
from src.agents.service import generate_agent_response


class RecordingChatModel(BaseChatModel):
    """A fake chat model that records the exact messages it is asked to
    generate from, so tests can assert what the model saw on each turn."""

    _seen: list = PrivateAttr(default_factory=list)
    _reply: str = PrivateAttr(default="ok")

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._seen.append(list(messages))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self._reply))]
        )

    @property
    def _llm_type(self) -> str:
        return "recording"

    @property
    def seen(self) -> list:
        return self._seen


def _build_agent(model: BaseChatModel, checkpointer, middleware=None):
    return create_agent(
        model=model,
        tools=[],
        system_prompt="sys",
        checkpointer=checkpointer,
        middleware=middleware or [],
    )


def _contents(messages) -> list:
    return [getattr(m, "content", None) for m in messages]


class MultiTurnRefinementTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_turn_sees_first_turn_context(self) -> None:
        model = RecordingChatModel()
        agent = _build_agent(model, InMemorySaver())
        config = {"configurable": {"thread_id": "session-a"}}

        await agent.ainvoke(
            {"messages": [HumanMessage(content="What companies use Python?")]},
            config=config,
        )
        await agent.ainvoke(
            {"messages": [HumanMessage(content="Which of those also use SQL?")]},
            config=config,
        )

        # The model's input on turn 2 must carry turn 1's exchange, which is
        # what lets the model resolve "those" against the prior question.
        turn_two_input = _contents(model.seen[-1])
        self.assertIn("What companies use Python?", turn_two_input)
        self.assertIn("Which of those also use SQL?", turn_two_input)


class SessionIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_sessions_do_not_see_each_others_history(self) -> None:
        model = RecordingChatModel()
        checkpointer = InMemorySaver()
        agent = _build_agent(model, checkpointer)

        await agent.ainvoke(
            {"messages": [HumanMessage(content="secret-from-session-one")]},
            config={"configurable": {"thread_id": "session-one"}},
        )
        await agent.ainvoke(
            {"messages": [HumanMessage(content="hello-from-session-two")]},
            config={"configurable": {"thread_id": "session-two"}},
        )

        session_two_input = _contents(model.seen[-1])
        self.assertIn("hello-from-session-two", session_two_input)
        self.assertNotIn("secret-from-session-one", session_two_input)


class GeneratedSessionIdTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_session_id_returned_when_client_omits_it(self) -> None:
        runtime = AsyncMock()
        runtime.ainvoke.return_value = {"answer": "ok", "trace_id": None}

        result = await generate_agent_response(query="hi", runtime=runtime)

        # A real UUID is generated and returned so the client can continue
        # the thread; it is also the id handed to the runtime as the thread key.
        returned_id = result["session_id"]
        self.assertIsNotNone(returned_id)
        uuid.UUID(returned_id)  # raises if not a valid UUID
        runtime.ainvoke.assert_awaited_once_with(
            query="hi", session_id=returned_id, user_id=None
        )


class PersistenceAcrossRestartTests(unittest.IsolatedAsyncioTestCase):
    async def test_conversation_resumes_after_runtime_rebuild(self) -> None:
        # The checkpointer (the persistent store) outlives the agent/runtime.
        # Rebuilding the agent against the same store simulates a process
        # restart: a fresh in-memory runtime, same backing DB + thread_id.
        checkpointer = InMemorySaver()
        config = {"configurable": {"thread_id": "durable-session"}}

        agent_before = _build_agent(RecordingChatModel(), checkpointer)
        await agent_before.ainvoke(
            {"messages": [HumanMessage(content="remember-me")]},
            config=config,
        )

        # Fresh agent + fresh model, no shared in-process state.
        model_after = RecordingChatModel()
        agent_after = _build_agent(model_after, checkpointer)
        await agent_after.ainvoke(
            {"messages": [HumanMessage(content="are you still there?")]},
            config=config,
        )

        # The rebuilt runtime replays the prior turn purely from the store.
        resumed_input = _contents(model_after.seen[-1])
        self.assertIn("remember-me", resumed_input)

        state = await agent_after.aget_state(config)
        self.assertIn("remember-me", _contents(state.values["messages"]))


class TrimmingCapHoldsTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_recent_messages_reach_model_while_store_keeps_all(self) -> None:
        max_messages = 4
        model = RecordingChatModel()
        checkpointer = InMemorySaver()
        agent = _build_agent(
            model, checkpointer, middleware=[build_trim_middleware(max_messages)]
        )
        config = {"configurable": {"thread_id": "long-session"}}

        for i in range(6):
            await agent.ainvoke(
                {"messages": [HumanMessage(content=f"turn-{i}")]},
                config=config,
            )

        # The model never sees more than the cap on any turn.
        self.assertTrue(all(len(seen) <= max_messages for seen in model.seen))
        self.assertEqual(len(model.seen[-1]), max_messages)

        # The store still holds the full conversation (well beyond the cap).
        state = await agent.aget_state(config)
        self.assertGreater(len(state.values["messages"]), max_messages)
        self.assertIn("turn-0", _contents(state.values["messages"]))


if __name__ == "__main__":
    unittest.main()
