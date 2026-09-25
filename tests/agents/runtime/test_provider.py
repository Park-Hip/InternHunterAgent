from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.runtime.provider import AgentProvider
from src.core.config import ConfigLoadError, validate_agent_config


def _agent_config(
    *,
    react_deployment: str = "deepseek_flash",
    react_options: dict | None = None,
    sql_options: dict | None = None,
) -> dict:
    return {
        "agent": {
            "providers": {
                "deepseek_flash": {
                    "provider": "deepseek",
                    "model": "deepseek/deepseek-v4-flash",
                    "api_key_env": "DEEPSEEK_API_KEY",
                },
                "groq_qwen": {
                    "provider": "groq",
                    "model": "groq/qwen/qwen3.6-27b",
                    "api_key_env": "GROQ_API_KEY",
                },
            },
            "react": {
                "deployment": react_deployment,
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout": 30,
                "max_retries": 2,
                "streaming": True,
                "provider_options": react_options or {"thinking": "disabled"},
            },
            "sql_generation": {
                "deployment": "groq_qwen",
                "temperature": 0.0,
                "max_tokens": 1024,
                "timeout": 15,
                "max_retries": 1,
                "streaming": False,
                "provider_options": sql_options
                or {"reasoning_format": "hidden", "reasoning_effort": "none"},
            },
        }
    }


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_build_model_resolves_a_deepseek_profile(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    AgentProvider().build_model("react")

    mock_chat_litellm.assert_called_once_with(
        model="deepseek/deepseek-v4-flash",
        api_key="deepseek-test-key",
        temperature=0.2,
        max_tokens=2048,
        request_timeout=30,
        max_retries=2,
        streaming=True,
        model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}},
    )


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_profiles_resolve_independent_deployments(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

    provider = AgentProvider()
    provider.build_model("react")
    provider.build_model("sql_generation")

    deepseek_kwargs = mock_chat_litellm.call_args_list[0].kwargs
    groq_kwargs = mock_chat_litellm.call_args_list[1].kwargs
    assert deepseek_kwargs["model"] == "deepseek/deepseek-v4-flash"
    assert deepseek_kwargs["model_kwargs"] == {
        "extra_body": {"thinking": {"type": "disabled"}}
    }
    assert groq_kwargs["model"] == "groq/qwen/qwen3.6-27b"
    assert groq_kwargs["temperature"] == 0.0
    assert groq_kwargs["streaming"] is False
    assert groq_kwargs["model_kwargs"] == {
        "reasoning_format": "hidden",
        "reasoning_effort": "none",
    }
    assert provider.provider_for("react") == "deepseek"
    assert provider.provider_for("sql_generation") == "groq"


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_missing_deepseek_thinking_option_defaults_to_disabled(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config()
    mock_settings.config_yaml["agent"]["react"]["provider_options"] = {}
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    AgentProvider().build_model("react")

    assert mock_chat_litellm.call_args.kwargs["model_kwargs"] == {
        "extra_body": {"thinking": {"type": "disabled"}}
    }


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_thinking_enabled_omits_the_deepseek_override(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config(react_options={"thinking": "enabled"})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    AgentProvider().build_model("react")

    assert mock_chat_litellm.call_args.kwargs["model_kwargs"] == {}


@patch("src.agents.runtime.provider.settings")
def test_missing_selected_credential_names_the_profile(
    mock_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="agent.react.deployment.*DEEPSEEK_API_KEY"):
        AgentProvider().build_model("react")


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_eval_driver_disables_provider_retries(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    monkeypatch.setenv("EVAL_DRIVER_DISABLE_PROVIDER_RETRIES", "1")

    AgentProvider().build_model("react")

    assert mock_chat_litellm.call_args.kwargs["max_retries"] == 0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda config: config["agent"]["react"].update(
                {"deployment": "missing"}
            ),
            "unknown deployment",
        ),
        (
            lambda config: config["agent"]["providers"]["deepseek_flash"].update(
                {"model": "deepseek-v4-flash"}
            ),
            "must start with 'deepseek/'",
        ),
        (
            lambda config: config["agent"]["react"].update(
                {"provider_options": {"reasoning_effort": "low"}}
            ),
            "unsupported DeepSeek options",
        ),
        (
            lambda config: config["agent"]["sql_generation"].update(
                {"provider_options": {"thinking": "disabled"}}
            ),
            "unsupported Groq options",
        ),
    ],
)
def test_invalid_configuration_is_rejected_before_model_construction(
    mutation, message: str
) -> None:
    config = _agent_config()
    mutation(config)

    with pytest.raises(ConfigLoadError, match=message):
        validate_agent_config(config)
