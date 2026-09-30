from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.agents.runtime.factory import agent_factory


class AgentFactoryTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.AgentProvider")
    async def test_agent_factory_registers_discovered_tools(
        self, mock_agent_provider, mock_load_system_prompt, mock_create_agent
    ) -> None:
        tools = [MagicMock(name="query_clean_jobs"), MagicMock(name="get_job_details")]

        await agent_factory(tools=tools)

        _, kwargs = mock_create_agent.call_args
        self.assertEqual(kwargs["tools"], tools)

    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.AgentProvider")
    async def test_agent_factory_accepts_optional_checkpointer(
        self, mock_agent_provider, mock_load_system_prompt, mock_create_agent
    ) -> None:
        fake_checkpointer = object()

        await agent_factory(checkpointer=fake_checkpointer)

        _, kwargs = mock_create_agent.call_args
        self.assertIs(kwargs["checkpointer"], fake_checkpointer)
        self.assertEqual(kwargs["tools"], [])

    @patch("src.agents.runtime.factory.build_tool_observation_middleware")
    @patch("src.agents.runtime.factory.build_trim_middleware")
    @patch("src.agents.runtime.factory.load_max_turns", return_value=6)
    @patch("src.agents.runtime.factory.build_compaction_middleware")
    @patch(
        "src.agents.runtime.factory.load_compaction_message_limits",
        return_value=(24, 12),
    )
    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.AgentProvider")
    async def test_agent_factory_compacts_persisted_history_with_the_serving_model(
        self,
        mock_agent_provider,
        mock_load_system_prompt,
        mock_create_agent,
        mock_load_compaction_message_limits,
        mock_build_compaction_middleware,
        mock_load_max_turns,
        mock_build_trim_middleware,
        mock_build_tool_observation_middleware,
    ) -> None:
        model = mock_agent_provider.return_value.build_model.return_value

        await agent_factory(tools=[])

        mock_build_compaction_middleware.assert_called_once_with(model, 24, 12)
        mock_load_max_turns.assert_called_once()
        mock_build_trim_middleware.assert_called_once_with(6)
        _, kwargs = mock_create_agent.call_args
        self.assertEqual(
            kwargs["middleware"],
            [
                mock_build_compaction_middleware.return_value,
                mock_build_trim_middleware.return_value,
                mock_build_tool_observation_middleware.return_value,
            ],
        )

    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.AgentProvider")
    async def test_agent_factory_uses_release_system_prompt_when_none_given(
        self, mock_agent_provider, mock_load_system_prompt, mock_create_agent
    ) -> None:
        mock_load_system_prompt.return_value = "release-system-prompt"

        await agent_factory(tools=[])

        _, kwargs = mock_create_agent.call_args
        self.assertEqual(kwargs["system_prompt"], "release-system-prompt")


if __name__ == "__main__":
    unittest.main()