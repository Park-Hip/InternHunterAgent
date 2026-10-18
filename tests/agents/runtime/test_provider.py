from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.runtime.provider import (
    ProviderCredentialError,
    assert_profile_credential,
    build_model,
)
from src.core import config as config_module


def _agent_config(
    *,
    react_options: dict | None = None,
) -> dict:
    return {
        "agent": {
            "providers": {
                "deepseek_flash": {
                    "model": "deepseek/deepseek-flash",
                    "api_key_env": "DEEPSEEK_API_KEY",
                },
            },
            "stream_turn_timeout_seconds": 120,
            "react": {
                "deployment": "deepseek_flash",
                "temperature": 0.2,
                "max_tokens": 2048,
                "timeout": 30,
                "max_attempts": 2,
                "streaming": True,
                "provider_options": react_options or {"thinking": "disabled"},
            },
            "sql_generation": {
                "deployment": "deepseek_flash",
                "temperature": 0.0,
                "max_tokens": 1024,
                "timeout": 15,
                "max_attempts": 1,
                "streaming": False,
                "provider_options": {"thinking": "disabled"},
            },
            "memory": {"max_turns": 6, "retention_days": 30},
        }
    }


def _install(mock_settings, config: dict) -> None:
    """Point the patched settings object at the typed agent section."""
    mock_settings.agent = config_module._build_agent_settings(config)


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_build_model_resolves_a_deepseek_profile(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(mock_settings, _agent_config())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    build_model("react")

    mock_chat_litellm.assert_called_once_with(
        model="deepseek/deepseek-flash",
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
def test_each_profile_builds_with_its_own_generation_settings(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(mock_settings, _agent_config())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    build_model("react")
    build_model("sql_generation")

    react_kwargs = mock_chat_litellm.call_args_list[0].kwargs
    sql_kwargs = mock_chat_litellm.call_args_list[1].kwargs
    assert react_kwargs["model"] == "deepseek/deepseek-flash"
    assert react_kwargs["temperature"] == 0.2
    assert react_kwargs["max_tokens"] == 2048
    assert react_kwargs["request_timeout"] == 30
    assert react_kwargs["max_retries"] == 2
    assert react_kwargs["streaming"] is True
    assert sql_kwargs["temperature"] == 0.0
    assert sql_kwargs["max_tokens"] == 1024
    assert sql_kwargs["request_timeout"] == 15
    assert sql_kwargs["max_retries"] == 1
    assert sql_kwargs["streaming"] is False
    assert mock_settings.agent.deployment_for("react").provider == "deepseek"
    assert mock_settings.agent.deployment_for("sql_generation").provider == "deepseek"


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_missing_deepseek_thinking_option_defaults_to_disabled(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(mock_settings, _agent_config(react_options={}))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    build_model("react")

    assert mock_chat_litellm.call_args.kwargs["model_kwargs"] == {
        "extra_body": {"thinking": {"type": "disabled"}}
    }


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_thinking_enabled_omits_the_deepseek_override(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(mock_settings, _agent_config(react_options={"thinking": "enabled"}))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    build_model("react")

    assert mock_chat_litellm.call_args.kwargs["model_kwargs"] == {}


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_build_model_builds_each_profile_once(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(mock_settings, _agent_config())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    build_model("react")
    build_model("react")

    mock_chat_litellm.assert_called_once()


@patch("src.agents.runtime.provider.settings")
def test_unknown_profile_is_refused(mock_settings) -> None:
    _install(mock_settings, _agent_config())

    with pytest.raises(ValueError, match="Unsupported agent model profile: chatbot"):
        build_model("chatbot")


def test_provider_credential_error_is_a_value_error() -> None:
    """Callers that catch ValueError keep working; only the type name is new."""
    assert issubclass(ProviderCredentialError, ValueError)


@patch("src.agents.runtime.provider.settings")
def test_missing_selected_credential_names_the_profile(
    mock_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(mock_settings, _agent_config())
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(
        ProviderCredentialError,
        match=r"agent\.react\.deployment.*DEEPSEEK_API_KEY is unset or empty",
    ):
        build_model("react")


@patch("src.agents.runtime.provider.settings")
def test_whitespace_selected_credential_is_refused(
    mock_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(mock_settings, _agent_config())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "   ")

    with pytest.raises(
        ProviderCredentialError, match="DEEPSEEK_API_KEY is unset or empty"
    ):
        build_model("react")


@patch("src.agents.runtime.provider.settings")
def test_assert_profile_credential_matches_build_model(
    mock_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The boot guard and first-use construction share one refusal."""
    _install(mock_settings, _agent_config())

    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    assert_profile_credential("react")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "   ")
    with pytest.raises(ProviderCredentialError) as guard_error:
        assert_profile_credential("react")
    with pytest.raises(ProviderCredentialError) as model_error:
        build_model("react")

    assert str(guard_error.value) == str(model_error.value)
