from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.runtime.provider import AgentProvider


class AgentProviderTests(unittest.TestCase):
    @patch("src.agents.runtime.provider.ChatGroq")
    @patch("src.agents.runtime.provider.settings")
    def test_build_model_forwards_configured_reasoning_format(
        self, mock_settings, mock_chat_groq
    ) -> None:
        mock_settings.config_yaml = {
            "agent": {
                "provider": "groq",
                "groq": {
                    "model": "qwen/qwen3.6-27b",
                    "reasoning_format": "hidden",
                },
            }
        }
        mock_settings.GROQ_API_KEY = "fake-key"

        AgentProvider().build_model()

        _, kwargs = mock_chat_groq.call_args
        self.assertEqual(kwargs["reasoning_format"], "hidden")

    @patch("src.agents.runtime.provider.ChatGroq")
    @patch("src.agents.runtime.provider.settings")
    def test_build_model_defaults_reasoning_format_to_none_when_unset(
        self, mock_settings, mock_chat_groq
    ) -> None:
        mock_settings.config_yaml = {
            "agent": {
                "provider": "groq",
                "groq": {
                    "model": "qwen/qwen3.6-27b",
                },
            }
        }
        mock_settings.GROQ_API_KEY = "fake-key"

        AgentProvider().build_model()

        _, kwargs = mock_chat_groq.call_args
        self.assertIsNone(kwargs["reasoning_format"])


if __name__ == "__main__":
    unittest.main()
