from __future__ import annotations

import unittest
from unittest.mock import patch

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.runtime.middleware import (
    build_trim_middleware,
    load_compaction_message_limits,
    load_max_turns,
)


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


class LoadMaxTurnsTests(unittest.TestCase):
    def test_reads_positive_int_from_config(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {"agent": {"memory": {"max_turns": 6}}}
            self.assertEqual(load_max_turns(), 6)

    def test_rejects_missing_memory_section(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {"agent": {}}
            with self.assertRaises(ValueError):
                load_max_turns()

    def test_rejects_non_positive_value(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {"agent": {"memory": {"max_turns": 0}}}
            with self.assertRaises(ValueError):
                load_max_turns()

    def test_rejects_boolean_value(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {"agent": {"memory": {"max_turns": True}}}
            with self.assertRaises(ValueError):
                load_max_turns()


class LoadCompactionMessageLimitsTests(unittest.TestCase):
    def test_reads_trigger_and_retention_from_config(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {
                "agent": {
                    "memory": {
                        "compaction": {
                            "trigger_messages": 24,
                            "keep_messages": 12,
                        }
                    }
                }
            }

            self.assertEqual(load_compaction_message_limits(), (24, 12))

    def test_rejects_retention_that_cannot_compact(self) -> None:
        with patch("src.agents.runtime.middleware.settings") as mock_settings:
            mock_settings.config_yaml = {
                "agent": {
                    "memory": {
                        "compaction": {
                            "trigger_messages": 12,
                            "keep_messages": 12,
                        }
                    }
                }
            }

            with self.assertRaises(ValueError):
                load_compaction_message_limits()


class TrimTurnsMiddlewareTests(unittest.TestCase):
    def test_trims_to_recent_complete_turns(self) -> None:
        history: list = []
        for index in range(5):
            history.append(HumanMessage(content=f"q{index}"))
            history.append(AIMessage(content=f"a{index}"))

        seen: dict = {}

        def handler(request: ModelRequest):
            seen["messages"] = request.messages
            return AIMessage(content="final")

        middleware = build_trim_middleware(2)
        middleware.wrap_model_call(_make_request(history), handler)

        self.assertEqual(
            [message.content for message in seen["messages"]],
            ["q3", "a3", "q4", "a4"],
        )

    def test_short_conversation_under_turn_cap_is_unchanged(self) -> None:
        history = [HumanMessage(content="hi"), AIMessage(content="hello")]
        seen: dict = {}

        def handler(request: ModelRequest):
            seen["messages"] = request.messages
            return AIMessage(content="final")

        middleware = build_trim_middleware(2)
        middleware.wrap_model_call(_make_request(history), handler)

        self.assertEqual([message.content for message in seen["messages"]], ["hi", "hello"])

    def test_retains_a_compaction_summary_alongside_recent_complete_turns(self) -> None:
        history = [
            HumanMessage(
                content="summary",
                additional_kwargs={"lc_source": "summarization"},
            )
        ]
        for index in range(3):
            history.append(HumanMessage(content=f"q{index}"))
            history.append(AIMessage(content=f"a{index}"))
        seen: dict = {}

        def handler(request: ModelRequest):
            seen["messages"] = request.messages
            return AIMessage(content="final")

        middleware = build_trim_middleware(2)
        middleware.wrap_model_call(_make_request(history), handler)

        self.assertEqual(
            [message.content for message in seen["messages"]],
            ["summary", "q1", "a1", "q2", "a2"],
        )


class TrimTurnsMiddlewareAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_atrims_to_recent_complete_turns(self) -> None:
        history: list = []
        for index in range(5):
            history.append(HumanMessage(content=f"q{index}"))
            history.append(AIMessage(content=f"a{index}"))

        seen: dict = {}

        async def handler(request: ModelRequest):
            seen["messages"] = request.messages
            return AIMessage(content="final")

        middleware = build_trim_middleware(2)
        await middleware.awrap_model_call(_make_request(history), handler)

        self.assertEqual(
            [message.content for message in seen["messages"]],
            ["q3", "a3", "q4", "a4"],
        )


class TrimTurnsMiddlewareLeavesStateIntactTests(unittest.IsolatedAsyncioTestCase):
    async def test_stored_state_retains_full_history_while_model_sees_recent_turns(self) -> None:
        model = GenericFakeChatModel(messages=iter([AIMessage(content="final answer")]))
        agent = create_agent(
            model=model,
            tools=[],
            system_prompt="sys",
            middleware=[build_trim_middleware(2)],
        )

        history: list = []
        for index in range(5):
            history.append(HumanMessage(content=f"q{index}"))
            history.append(AIMessage(content=f"a{index}"))

        result = await agent.ainvoke({"messages": history})

        self.assertEqual(len(result["messages"]), 11)
        self.assertEqual(result["messages"][0].content, "q0")
        self.assertEqual(result["messages"][-1].content, "final answer")


if __name__ == "__main__":
    unittest.main()
