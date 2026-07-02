from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.runtime.factory import agent_factory
from src.agents.tools.query_clean_jobs import query_clean_jobs
from src.agents.tools.get_job_details import get_job_details
from src.agents.tools.time import get_current_time


class AgentFactoryTests(unittest.TestCase):
    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.AgentProvider")
    def test_agent_factory_registers_clock_and_query_clean_jobs_tools(
        self, mock_agent_provider, mock_load_system_prompt, mock_create_agent
    ) -> None:
        agent_factory()

        _, kwargs = mock_create_agent.call_args
        self.assertIn(get_current_time, kwargs["tools"])
        self.assertIn(query_clean_jobs, kwargs["tools"])
        self.assertIn(get_job_details, kwargs["tools"])

    @patch("src.agents.runtime.factory.create_agent")
    @patch("src.agents.runtime.factory.load_system_prompt")
    @patch("src.agents.runtime.factory.AgentProvider")
    def test_agent_factory_accepts_optional_checkpointer(
        self, mock_agent_provider, mock_load_system_prompt, mock_create_agent
    ) -> None:
        fake_checkpointer = object()

        agent_factory(checkpointer=fake_checkpointer)

        mock_create_agent.assert_called_once()


if __name__ == "__main__":
    unittest.main()
