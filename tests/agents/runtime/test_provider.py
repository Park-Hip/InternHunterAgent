from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.runtime.provider import AgentProvider


def _agent_config(
    *,
    react_reasoning_effort: str | None = None,
    sql_reasoning_effort: str | None = "none",
) -> dict:
    return {
        "agent": {
            "provider": "groq",
            "react": {
                "model": "react-model",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout": 30,
                "max_retries": 2,
                "streaming": True,
                "reasoning_format": "hidden",
                "reasoning_effort": react_reasoning_effort,
            },
            "sql_generation": {
                "model": "sql-model",
                "temperature": 0.0,
                "max_tokens": 1024,
                "timeout": 15,
                "max_retries": 1,
                "streaming": False,
                "reasoning_format": "hidden",
                "reasoning_effort": sql_reasoning_effort,
            },
        }
    }


def _gemini_agent_config() -> dict:
    config = _agent_config()
    config["agent"]["react"].update(
        provider="google", model="gemini-2.5-flash", thinking_budget=0
    )
    return config


class AgentProviderTests(unittest.TestCase):
    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    @patch("src.agents.runtime.provider.settings")
    def test_build_model_constructs_gemini_react_profile(
        self, mock_settings, mock_chat_google
    ) -> None:
        mock_settings.config_yaml = _gemini_agent_config()
        mock_settings.GOOGLE_API_KEY = "google-key"

        AgentProvider().build_model("react")

        _, kwargs = mock_chat_google.call_args
        self.assertEqual(kwargs["model"], "gemini-2.5-flash")
        self.assertEqual(kwargs["google_api_key"], "google-key")
        self.assertEqual(kwargs["thinking_budget"], 0)
        self.assertEqual(kwargs["temperature"], 0.2)

    @patch("src.agents.runtime.provider.settings")
    def test_gemini_requires_google_api_key_without_network_call(self, mock_settings) -> None:
        mock_settings.config_yaml = _gemini_agent_config()
        mock_settings.GOOGLE_API_KEY = None

        with self.assertRaisesRegex(ValueError, "GOOGLE_API_KEY is unset"):
            AgentProvider().build_model("react")
    @patch("src.agents.runtime.provider.ChatGroq")
    @patch("src.agents.runtime.provider.settings")
    def test_build_model_loads_react_profile_fields(
        self, mock_settings, mock_chat_groq
    ) -> None:
        mock_settings.config_yaml = _agent_config()
        mock_settings.GROQ_API_KEY = "fake-key"

        AgentProvider().build_model("react")

        _, kwargs = mock_chat_groq.call_args
        self.assertEqual(kwargs["model_name"], "react-model")
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertEqual(kwargs["max_tokens"], 2048)
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(kwargs["max_retries"], 2)
        self.assertIs(kwargs["streaming"], True)
        self.assertEqual(kwargs["reasoning_format"], "hidden")
        self.assertEqual(kwargs["groq_api_key"], "fake-key")

    @patch("src.agents.runtime.provider.ChatGroq")
    @patch("src.agents.runtime.provider.settings")
    def test_build_model_omits_react_reasoning_effort_when_null(
        self, mock_settings, mock_chat_groq
    ) -> None:
        mock_settings.config_yaml = _agent_config(react_reasoning_effort=None)
        mock_settings.GROQ_API_KEY = "fake-key"

        AgentProvider().build_model("react")

        _, kwargs = mock_chat_groq.call_args
        self.assertNotIn("reasoning_effort", kwargs)

    @patch("src.agents.runtime.provider.ChatGroq")
    @patch("src.agents.runtime.provider.settings")
    def test_build_model_omits_reasoning_effort_when_missing(
        self, mock_settings, mock_chat_groq
    ) -> None:
        config = _agent_config()
        del config["agent"]["react"]["reasoning_effort"]
        mock_settings.config_yaml = config
        mock_settings.GROQ_API_KEY = "fake-key"

        AgentProvider().build_model("react")

        _, kwargs = mock_chat_groq.call_args
        self.assertNotIn("reasoning_effort", kwargs)

    @patch("src.agents.runtime.provider.ChatGroq")
    @patch("src.agents.runtime.provider.settings")
    def test_build_model_loads_sql_generation_profile_fields(
        self, mock_settings, mock_chat_groq
    ) -> None:
        mock_settings.config_yaml = _agent_config()
        mock_settings.GROQ_API_KEY = "fake-key"

        AgentProvider().build_model("sql_generation")

        _, kwargs = mock_chat_groq.call_args
        self.assertEqual(kwargs["model_name"], "sql-model")
        self.assertEqual(kwargs["temperature"], 0.0)
        self.assertEqual(kwargs["max_tokens"], 1024)
        self.assertEqual(kwargs["timeout"], 15)
        self.assertEqual(kwargs["max_retries"], 1)
        self.assertIs(kwargs["streaming"], False)
        self.assertEqual(kwargs["reasoning_format"], "hidden")
        self.assertEqual(kwargs["reasoning_effort"], "none")
        self.assertEqual(kwargs["groq_api_key"], "fake-key")

    @patch("src.agents.runtime.provider.ChatGroq")
    @patch("src.agents.runtime.provider.settings")
    def test_profiles_are_independent(
        self, mock_settings, mock_chat_groq
    ) -> None:
        mock_settings.config_yaml = _agent_config(
            react_reasoning_effort="default",
            sql_reasoning_effort="none",
        )
        mock_settings.GROQ_API_KEY = "fake-key"

        provider = AgentProvider()
        provider.build_model("react")
        provider.build_model("sql_generation")

        react_kwargs = mock_chat_groq.call_args_list[0].kwargs
        sql_kwargs = mock_chat_groq.call_args_list[1].kwargs
        self.assertEqual(react_kwargs["model_name"], "react-model")
        self.assertEqual(react_kwargs["temperature"], 0.2)
        self.assertEqual(react_kwargs["max_tokens"], 2048)
        self.assertIs(react_kwargs["streaming"], True)
        self.assertEqual(react_kwargs["reasoning_effort"], "default")
        self.assertEqual(sql_kwargs["model_name"], "sql-model")
        self.assertEqual(sql_kwargs["temperature"], 0.0)
        self.assertEqual(sql_kwargs["max_tokens"], 1024)
        self.assertIs(sql_kwargs["streaming"], False)
        self.assertEqual(sql_kwargs["reasoning_effort"], "none")


if __name__ == "__main__":
    unittest.main()
