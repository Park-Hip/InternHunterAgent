from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.runtime.provider import AgentProvider, ProviderCredentialError
from src.core.config import ConfigLoadError, validate_agent_config


def _agent_config(
    *,
    react_options: dict | None = None,
) -> dict:
    return {
        "agent": {
            "providers": {
                "deepseek_flash": {
                    "provider": "deepseek",
                    "model": "deepseek/deepseek-flash",
                    "api_key_env": "DEEPSEEK_API_KEY",
                },
            },
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
    mock_settings.config_yaml = _agent_config()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    provider = AgentProvider()
    provider.build_model("react")
    provider.build_model("sql_generation")

    react_kwargs = mock_chat_litellm.call_args_list[0].kwargs
    sql_kwargs = mock_chat_litellm.call_args_list[1].kwargs
    assert react_kwargs["model"] == "deepseek/deepseek-flash"
    assert react_kwargs["temperature"] == 0.2
    assert react_kwargs["max_tokens"] == 2048
    assert react_kwargs["streaming"] is True
    assert sql_kwargs["model"] == "deepseek/deepseek-flash"
    assert sql_kwargs["temperature"] == 0.0
    assert sql_kwargs["max_tokens"] == 1024
    assert sql_kwargs["streaming"] is False
    assert provider.provider_for("react") == "deepseek"
    assert provider.provider_for("sql_generation") == "deepseek"


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


def test_provider_credential_error_is_a_value_error() -> None:
    """Callers that catch ValueError keep working; only the type name is new."""
    assert issubclass(ProviderCredentialError, ValueError)


@patch("src.agents.runtime.provider.settings")
def test_missing_selected_credential_names_the_profile(
    mock_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(
        ProviderCredentialError,
        match=r"agent\.react\.deployment.*DEEPSEEK_API_KEY is unset or empty",
    ):
        AgentProvider().build_model("react")


@patch("src.agents.runtime.provider.settings")
def test_whitespace_selected_credential_is_refused(
    mock_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "   ")

    with pytest.raises(
        ProviderCredentialError, match="DEEPSEEK_API_KEY is unset or empty"
    ):
        AgentProvider().build_model("react")


@patch("src.agents.runtime.provider.settings")
def test_assert_profile_credential_matches_build_model(
    mock_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The boot guard and first-use construction share one refusal."""
    mock_settings.config_yaml = _agent_config()
    provider = AgentProvider()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    provider.assert_profile_credential("react")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "   ")
    with pytest.raises(ProviderCredentialError) as guard_error:
        provider.assert_profile_credential("react")
    with pytest.raises(ProviderCredentialError) as model_error:
        provider.build_model("react")

    assert str(guard_error.value) == str(model_error.value)


@patch("src.agents.runtime.provider.ChatLiteLLM")
@patch("src.agents.runtime.provider.settings")
def test_eval_driver_disables_provider_retries(
    mock_settings, mock_chat_litellm, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_settings.config_yaml = _agent_config()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    monkeypatch.setenv("EVAL_DRIVER_DISABLE_PROVIDER_RETRIES", "1")

    AgentProvider().build_model("react")

    # One attempt: the switch disables retries without disabling the call.
    assert mock_chat_litellm.call_args.kwargs["max_retries"] == 1


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
                {"model": "deepseek-flash"}
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
                {"provider_options": {"thinking": "auto"}}
            ),
            "must be 'disabled' or 'enabled'",
        ),
        (
            lambda config: config["agent"]["react"].pop("max_attempts"),
            "agent.react.max_attempts",
        ),
        (
            lambda config: config["agent"]["react"].update({"max_attempts": 0}),
            "must be a positive integer",
        ),
        (
            lambda config: config["agent"]["react"].update({"max_attempts": -1}),
            "must be a positive integer",
        ),
        (
            lambda config: config["agent"]["react"].update({"max_attempts": True}),
            "must be a positive integer",
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


def test_options_for_a_provider_without_a_serving_contract_are_rejected() -> None:
    config = _agent_config()
    config["agent"]["providers"]["unreviewed"] = {
        "provider": "custom",
        "model": "custom/model-a",
        "api_key_env": "CUSTOM_API_KEY",
    }
    config["agent"]["react"].update(
        {"deployment": "unreviewed", "provider_options": {"temperature": 1}}
    )

    with pytest.raises(ConfigLoadError, match="not supported for provider 'custom'"):
        validate_agent_config(config)
