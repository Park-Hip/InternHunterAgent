from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.runtime.factory import agent_factory
from src.agents.tools.query_clean_jobs import query_clean_jobs
from src.agents.tools.get_job_details import get_job_details


class AgentFactoryTests(unittest.TestCase):
    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.AgentProvider")
    def test_agent_factory_registers_job_search_tools(
        self, mock_agent_provider, mock_load_system_prompt, mock_create_agent
    ) -> None:
        agent_factory()

        _, kwargs = mock_create_agent.call_args
        self.assertEqual(kwargs["tools"], [query_clean_jobs, get_job_details])

    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.AgentProvider")
    def test_agent_factory_accepts_optional_checkpointer(
        self, mock_agent_provider, mock_load_system_prompt, mock_create_agent
    ) -> None:
        fake_checkpointer = object()

        agent_factory(checkpointer=fake_checkpointer)

        mock_create_agent.assert_called_once()

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
    def test_agent_factory_compacts_persisted_history_with_the_serving_model(
        self,
        mock_agent_provider,
        mock_load_system_prompt,
        mock_create_agent,
        mock_load_compaction_message_limits,
        mock_build_compaction_middleware,
        mock_load_max_turns,
        mock_build_trim_middleware,
    ) -> None:
        model = mock_agent_provider.return_value.build_model.return_value

        agent_factory()

        mock_build_compaction_middleware.assert_called_once_with(model, 24, 12)
        mock_load_max_turns.assert_called_once()
        mock_build_trim_middleware.assert_called_once_with(6)
        _, kwargs = mock_create_agent.call_args
        self.assertEqual(
            kwargs["middleware"],
            [
                mock_build_compaction_middleware.return_value,
                mock_build_trim_middleware.return_value,
            ],
        )


if __name__ == "__main__":
    unittest.main()
