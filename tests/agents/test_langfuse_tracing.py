from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.agents.tracing import langfuse


def test_build_langfuse_config_uses_closed_api_tag_taxonomy() -> None:
    config = langfuse.build_langfuse_config(
        session_id="session-1",
        user_id="user-1",
        entry_point="api:chat",
    )

    assert config["metadata"] == {
        "langfuse_session_id": "session-1",
        "langfuse_user_id": "user-1",
        "langfuse_tags": [
            "api:chat",
            "prompt:v4",
            "provider:deepseek",
            "model:deepseek-v4-flash",
        ],
    }


def test_build_langfuse_config_labels_evaluation_scenario_and_repeat() -> None:
    config = langfuse.build_langfuse_config(
        entry_point="eval:driver",
        scenario_id="HLP-COUNT-1",
        repeat=2,
    )

    assert config["metadata"]["langfuse_tags"][-2:] == [
        "scenario:HLP-COUNT-1",
        "repeat:2",
    ]


def test_trace_attributes_propagate_prompt_version_and_closed_tags() -> None:
    with patch.object(langfuse, "propagate_attributes") as propagate:
        propagate.return_value.__enter__.return_value = None
        propagate.return_value.__exit__.return_value = None

        with langfuse.langfuse_trace_attributes(entry_point="api:chat-stream"):
            pass

    propagate.assert_called_once_with(
        tags=[
            "api:chat-stream",
            "prompt:v4",
            "provider:deepseek",
            "model:deepseek-v4-flash",
        ],
        version="v4",
    )


def test_build_langfuse_config_rejects_unknown_entry_points() -> None:
    with pytest.raises(ValueError, match="Unsupported Langfuse entry point"):
        langfuse.build_langfuse_config(entry_point="api:debug")


def test_langfuse_environment_is_closed_and_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_TRACING_ENVIRONMENT", raising=False)
    assert langfuse.get_langfuse_environment() == "local"

    monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "staging")
    with pytest.raises(ValueError, match="must be one of"):
        langfuse.get_langfuse_environment()


def test_langfuse_client_receives_environment_and_render_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "production")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    monkeypatch.setattr(
        langfuse,
        "settings",
        SimpleNamespace(
            LANGFUSE_PUBLIC_KEY="public",
            LANGFUSE_SECRET_KEY="secret",
            LANGFUSE_BASE_URL="https://example.test",
            config_yaml={
                "observability": {
                    "langfuse": {
                        "environments": {
                            "default": "local",
                            "allowed": ["local", "production", "evaluation"],
                        }
                    }
                }
            },
        ),
    )

    with patch.object(langfuse, "Langfuse") as client:
        langfuse.create_langfuse_client()

    client.assert_called_once_with(
        public_key="public",
        secret_key="secret",
        host="https://example.test",
        environment="production",
        release="abc123",
    )
