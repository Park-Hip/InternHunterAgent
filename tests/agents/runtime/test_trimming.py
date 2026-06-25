from __future__ import annotations

import unittest
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest

from src.agents.runtime.middleware import build_trim_middleware, load_max_messages


def _make_request(messages: list) -> ModelRequest:
    return ModelRequest(
        model=GenericFakeChatModel(messages=iter([AIMessage(content="x")])),
        messages=messages,
        system_message=None,
        tool_choice=None,
        tools=[],
        response_format=None,
        state={"messages": messages},
        runtime=None,
        model_settings={},
    )


class LoadMaxMessagesTests(unittest.TestCase):
    def test_reads_positive_int_from_config(self) -> None:
        with patch(
            "src.agents.runtime.middleware.settings"
        ) as mock_settings:
            mock_settings.config_yaml = {"agent": {"memory": {"max_messages": 8}}}
            self.assertEqual(load_max_messages(), 8)

    def test_rejects_missing_memory_section(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {"agent": {}}
            with self.assertRaises(ValueError):
                load_max_messages()

    def test_rejects_non_positive_value(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {"agent": {"memory": {"max_messages": 0}}}
            with self.assertRaises(ValueError):
                load_max_messages()

    def test_rejects_boolean_value(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {"agent": {"memory": {"max_messages": True}}}
            with self.assertRaises(ValueError):
                load_max_messages()


class TrimMiddlewareTests(unittest.TestCase):
    def test_trims_inbound_model_messages_to_most_recent_cap(self) -> None:
        history: list = []
        for i in range(5):
            history.append(HumanMessage(content=f"q{i}"))
            history.append(AIMessage(content=f"a{i}"))

        seen: dict = {}

        def handler(request: ModelRequest):
            seen["messages"] = request.messages
            return AIMessage(content="final")

        middleware = build_trim_middleware(4)
        middleware.wrap_model_call(_make_request(history), handler)

        self.assertEqual(len(seen["messages"]), 4)
        self.assertEqual(
            [m.content for m in seen["messages"]],
            ["q3", "a3", "q4", "a4"],
        )

    def test_short_conversation_under_cap_is_unchanged(self) -> None:
        history = [HumanMessage(content="hi"), AIMessage(content="hello")]

        seen: dict = {}

        def handler(request: ModelRequest):
            seen["messages"] = request.messages
            return AIMessage(content="final")

        middleware = build_trim_middleware(20)
        middleware.wrap_model_call(_make_request(history), handler)

        self.assertEqual([m.content for m in seen["messages"]], ["hi", "hello"])


class TrimMiddlewareAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_atrims_inbound_model_messages_to_most_recent_cap(self) -> None:
        history: list = []
        for i in range(5):
            history.append(HumanMessage(content=f"q{i}"))
            history.append(AIMessage(content=f"a{i}"))

        seen: dict = {}

        async def handler(request: ModelRequest):
            seen["messages"] = request.messages
            return AIMessage(content="final")

        middleware = build_trim_middleware(4)
        await middleware.awrap_model_call(_make_request(history), handler)

        self.assertEqual([m.content for m in seen["messages"]], ["q3", "a3", "q4", "a4"])


class TrimMiddlewareLeavesStateIntactTests(unittest.IsolatedAsyncioTestCase):
    async def test_stored_state_retains_full_history_while_model_sees_trimmed(self) -> None:
        model = GenericFakeChatModel(messages=iter([AIMessage(content="final answer")]))
        agent = create_agent(
            model=model,
            tools=[],
            system_prompt="sys",
            middleware=[build_trim_middleware(4)],
        )

        history: list = []
        for i in range(5):
            history.append(HumanMessage(content=f"q{i}"))
            history.append(AIMessage(content=f"a{i}"))

        # Driven through ainvoke, matching how the runtime invokes the agent.
        result = await agent.ainvoke({"messages": history})

        # The full 10-message history plus the new answer survive in state
        # (what the checkpointer would persist) — trimming touched only the
        # per-turn model input, not stored history.
        self.assertEqual(len(result["messages"]), 11)
        self.assertEqual(result["messages"][0].content, "q0")
        self.assertEqual(result["messages"][-1].content, "final answer")


if __name__ == "__main__":
    unittest.main()
