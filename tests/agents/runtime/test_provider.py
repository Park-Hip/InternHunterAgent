from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.agents.runtime.provider import AgentProvider


def _agent_config(
    *,
    react_reasoning_effort: str | None = None,
    sql_reasoning_effort: str | None = "none",
    react_provider: str | None = None,
    react_thinking: str | None = None,
) -> dict:
    config = {
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
    if react_provider is not None:
        config["agent"]["react"]["provider"] = react_provider
    if react_thinking is not None:
        config["agent"]["react"]["thinking"] = react_thinking
    return config


class AgentProviderTests(unittest.TestCase):
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

    @patch("src.agents.runtime.provider.settings")
    def test_missing_groq_key_names_the_profile(self, mock_settings) -> None:
        """GROQ_API_KEY is optional at boot, so the branch that needs it validates it."""
        mock_settings.config_yaml = _agent_config()
        mock_settings.GROQ_API_KEY = None

        with self.assertRaises(ValueError) as caught:
            AgentProvider().build_model("react")

        self.assertIn("agent.react.provider", str(caught.exception))
        self.assertIn("GROQ_API_KEY", str(caught.exception))


class DeepSeekProviderTests(unittest.TestCase):
    """The DeepSeek branch imports lazily, so it is patched at its import site."""

    @patch("langchain_deepseek.ChatDeepSeek")
    @patch("src.agents.runtime.provider.settings")
    def test_profile_provider_overrides_the_agent_default(
        self, mock_settings, mock_chat_deepseek
    ) -> None:
        mock_settings.config_yaml = _agent_config(react_provider="deepseek")
        mock_settings.DEEPSEEK_API_KEY = "fake-deepseek-key"

        AgentProvider().build_model("react")

        _, kwargs = mock_chat_deepseek.call_args
        self.assertEqual(kwargs["model"], "react-model")
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertEqual(kwargs["max_tokens"], 2048)
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(kwargs["max_retries"], 2)
        self.assertIs(kwargs["streaming"], True)
        self.assertEqual(kwargs["api_key"], "fake-deepseek-key")
        self.assertNotIn("reasoning_format", kwargs)
        self.assertNotIn("groq_api_key", kwargs)

    @patch("src.agents.runtime.provider.ChatGroq")
    @patch("langchain_deepseek.ChatDeepSeek")
    @patch("src.agents.runtime.provider.settings")
    def test_one_profile_moves_while_the_other_stays(
        self, mock_settings, mock_chat_deepseek, mock_chat_groq
    ) -> None:
        mock_settings.config_yaml = _agent_config(react_provider="deepseek")
        mock_settings.GROQ_API_KEY = "fake-key"
        mock_settings.DEEPSEEK_API_KEY = "fake-deepseek-key"

        provider = AgentProvider()
        provider.build_model("react")
        provider.build_model("sql_generation")

        self.assertEqual(mock_chat_deepseek.call_count, 1)
        self.assertEqual(mock_chat_groq.call_count, 1)
        self.assertEqual(provider.provider_for("react"), "deepseek")
        self.assertEqual(provider.provider_for("sql_generation"), "groq")

    @patch("langchain_deepseek.ChatDeepSeek")
    @patch("src.agents.runtime.provider.settings")
    def test_thinking_disabled_is_sent_as_extra_body(
        self, mock_settings, mock_chat_deepseek
    ) -> None:
        mock_settings.config_yaml = _agent_config(
            react_provider="deepseek", react_thinking="disabled"
        )
        mock_settings.DEEPSEEK_API_KEY = "fake-deepseek-key"

        AgentProvider().build_model("react")

        _, kwargs = mock_chat_deepseek.call_args
        self.assertEqual(kwargs["extra_body"], {"thinking": {"type": "disabled"}})

    @patch("langchain_deepseek.ChatDeepSeek")
    @patch("src.agents.runtime.provider.settings")
    def test_thinking_defaults_to_disabled_when_unset(
        self, mock_settings, mock_chat_deepseek
    ) -> None:
        """Thinking on is the provider default, and it ignores temperature (T0027.1)."""
        mock_settings.config_yaml = _agent_config(react_provider="deepseek")
        mock_settings.DEEPSEEK_API_KEY = "fake-deepseek-key"

        AgentProvider().build_model("react")

        _, kwargs = mock_chat_deepseek.call_args
        self.assertEqual(kwargs["extra_body"], {"thinking": {"type": "disabled"}})

    @patch("langchain_deepseek.ChatDeepSeek")
    @patch("src.agents.runtime.provider.settings")
    def test_thinking_enabled_sends_no_extra_body(
        self, mock_settings, mock_chat_deepseek
    ) -> None:
        mock_settings.config_yaml = _agent_config(
            react_provider="deepseek", react_thinking="enabled"
        )
        mock_settings.DEEPSEEK_API_KEY = "fake-deepseek-key"

        AgentProvider().build_model("react")

        _, kwargs = mock_chat_deepseek.call_args
        self.assertNotIn("extra_body", kwargs)

    @patch("src.agents.runtime.provider.settings")
    def test_unknown_thinking_value_is_rejected(self, mock_settings) -> None:
        mock_settings.config_yaml = _agent_config(
            react_provider="deepseek", react_thinking="hidden"
        )
        mock_settings.DEEPSEEK_API_KEY = "fake-deepseek-key"

        with self.assertRaises(ValueError) as caught:
            AgentProvider().build_model("react")

        self.assertIn("agent.react.thinking", str(caught.exception))

    @patch("src.agents.runtime.provider.settings")
    def test_missing_key_names_the_profile(self, mock_settings) -> None:
        mock_settings.config_yaml = _agent_config(react_provider="deepseek")
        mock_settings.DEEPSEEK_API_KEY = None

        with self.assertRaises(ValueError) as caught:
            AgentProvider().build_model("react")

        self.assertIn("agent.react.provider", str(caught.exception))
        self.assertIn("DEEPSEEK_API_KEY", str(caught.exception))

    @patch("langchain_deepseek.ChatDeepSeek")
    @patch("src.agents.runtime.provider.settings")
    def test_driver_retry_suppression_reaches_the_deepseek_branch(
        self, mock_settings, mock_chat_deepseek
    ) -> None:
        """A branch that retries underneath the driver corrupts its retry ledger."""
        mock_settings.config_yaml = _agent_config(react_provider="deepseek")
        mock_settings.DEEPSEEK_API_KEY = "fake-deepseek-key"

        with patch.dict(os.environ, {"EVAL_DRIVER_DISABLE_PROVIDER_RETRIES": "1"}):
            AgentProvider().build_model("react")

        _, kwargs = mock_chat_deepseek.call_args
        self.assertEqual(kwargs["max_retries"], 0)

    @patch("src.agents.runtime.provider.settings")
    def test_unsupported_provider_is_rejected(self, mock_settings) -> None:
        mock_settings.config_yaml = _agent_config(react_provider="mistral")

        with self.assertRaises(ValueError) as caught:
            AgentProvider().build_model("react")

        self.assertIn("mistral", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
