from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.agents.runtime.factory import agent_factory


class AgentFactoryTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.build_model")
    async def test_agent_factory_registers_discovered_tools(
        self, mock_build_model, mock_load_system_prompt, mock_create_agent
    ) -> None:
        tools = [MagicMock(name="query_clean_jobs"), MagicMock(name="get_job_details")]

        await agent_factory(tools=tools)

        _, kwargs = mock_create_agent.call_args
        self.assertEqual(kwargs["tools"], tools)

    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.build_model")
    async def test_agent_factory_accepts_optional_checkpointer(
        self, mock_build_model, mock_load_system_prompt, mock_create_agent
    ) -> None:
        fake_checkpointer = object()

        await agent_factory(checkpointer=fake_checkpointer)

        _, kwargs = mock_create_agent.call_args
        self.assertIs(kwargs["checkpointer"], fake_checkpointer)
        self.assertEqual(kwargs["tools"], [])

    @patch("src.agents.runtime.factory.settings")
    @patch("src.agents.runtime.factory.build_tool_observation_middleware")
    @patch("src.agents.runtime.factory.build_trim_middleware")
    @patch("src.agents.runtime.factory.build_interrupted_tool_call_repair_middleware")
    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.build_model")
    async def test_agent_factory_registers_middlewares_in_order(
        self,
        mock_build_model,
        mock_load_system_prompt,
        mock_create_agent,
        mock_build_repair_middleware,
        mock_build_trim_middleware,
        mock_build_tool_observation_middleware,
        mock_settings,
    ) -> None:
        mock_settings.agent.max_turns = 6

        await agent_factory(tools=[])

        mock_build_trim_middleware.assert_called_once_with(6)
        _, kwargs = mock_create_agent.call_args
        self.assertEqual(
            kwargs["middleware"],
            [
                mock_build_repair_middleware.return_value,
                mock_build_trim_middleware.return_value,
                mock_build_tool_observation_middleware.return_value,
            ],
        )

    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.build_model")
    async def test_agent_factory_uses_release_system_prompt_when_none_given(
        self, mock_build_model, mock_load_system_prompt, mock_create_agent
    ) -> None:
        mock_load_system_prompt.return_value = "release-system-prompt"

        await agent_factory(tools=[])

        _, kwargs = mock_create_agent.call_args
        self.assertEqual(kwargs["system_prompt"], "release-system-prompt")


if __name__ == "__main__":
    unittest.main()
