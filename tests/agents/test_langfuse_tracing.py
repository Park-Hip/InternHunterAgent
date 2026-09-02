from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agents.tracing import langfuse


def test_build_langfuse_config_validates_the_closed_api_tag_taxonomy() -> None:
    with patch.object(langfuse, "validate_langfuse_trace_context") as validate:
        config = langfuse.build_langfuse_config(entry_point="api:chat")

    assert "metadata" not in config
    validate.assert_called_once_with(
        entry_point="api:chat",
        scenario_id=None,
        repeat=None,
    )


def test_build_langfuse_tags_labels_evaluation_scenario_and_repeat() -> None:
    tags = langfuse.build_langfuse_tags(
        entry_point="eval:driver",
        scenario_id="HLP-COUNT-1",
        repeat=2,
    )

    assert tags[-2:] == ["scenario:HLP-COUNT-1", "repeat:2"]


def test_trace_attributes_propagate_request_metadata_and_closed_tags() -> None:
    with patch.object(langfuse, "propagate_attributes") as propagate:
        propagate.return_value.__enter__.return_value = None
        propagate.return_value.__exit__.return_value = None

        with langfuse.langfuse_trace_attributes(
            entry_point="api:chat-stream",
            trace_name="agent-chat-stream",
            session_id="session-1",
            user_id="user-1",
        ):
            pass

    propagate.assert_called_once_with(
        trace_name="agent-chat-stream",
        session_id="session-1",
        user_id="user-1",
        tags=[
            "api:chat-stream",
            "prompt:system:v11",
            "prompt:schema_context:v11",
            "prompt:sql_generation:v11",
            "provider:deepseek",
            "model:deepseek-v4-flash",
        ],
        metadata={
            "prompt_versions": {
                "system": "v11",
                "schema_context": "v11",
                "sql_generation": "v11",
            }
        },
    )


@pytest.mark.asyncio
async def test_request_trace_creates_a_root_observation_in_the_request_context() -> (
    None
):
    client = MagicMock()
    client.get_current_trace_id.return_value = "trace-123"
    client.start_as_current_observation.return_value.__enter__.return_value = None
    client.start_as_current_observation.return_value.__exit__.return_value = None

    with (
        patch.object(langfuse, "_langfuse_handler", object()),
        patch.object(langfuse, "get_langfuse_client", return_value=client),
        patch.object(langfuse, "propagate_attributes") as propagate,
    ):
        propagate.return_value.__enter__.return_value = None
        propagate.return_value.__exit__.return_value = None

        async with langfuse.langfuse_request_trace(
            entry_point="api:chat",
            trace_name="agent-chat",
            session_id="session-1",
            user_id="user-1",
        ) as trace_id:
            assert trace_id == "trace-123"

    propagate.assert_called_once_with(
        trace_name="agent-chat",
        session_id="session-1",
        user_id="user-1",
        tags=[
            "api:chat",
            "prompt:system:v11",
            "prompt:schema_context:v11",
            "prompt:sql_generation:v11",
            "provider:deepseek",
            "model:deepseek-v4-flash",
        ],
        metadata={
            "prompt_versions": {
                "system": "v11",
                "schema_context": "v11",
                "sql_generation": "v11",
            }
        },
    )
    client.start_as_current_observation.assert_called_once_with(
        as_type="span", name="agent-chat"
    )
    client.get_current_trace_id.assert_called_once_with()


@pytest.mark.asyncio
async def test_stream_latency_updates_the_bound_request_span_across_tasks() -> None:
    client = MagicMock()
    span = MagicMock()
    latency = langfuse.StreamLatency()
    latency.attach_span(span)

    async def mark_visible() -> None:
        latency.mark_user_visible()

    async def mark_complete() -> None:
        latency.complete("success")

    with patch.object(langfuse, "get_langfuse_client", return_value=client):
        await asyncio.create_task(mark_visible())
        await asyncio.create_task(mark_complete())

    assert span.update.call_count == 2
    client.update_current_span.assert_not_called()
    metadata = span.update.call_args.kwargs["metadata"]
    assert metadata["user_visible_ttft_ms"] is not None
    assert metadata["stream_completion_ms"] is not None
    assert metadata["outcome"] == "success"


@pytest.mark.asyncio
async def test_request_trace_tags_an_evaluation_scenario_and_repeat() -> None:
    """`evals/harness.py` names `scenario_id` and `repeat` at this call site.

    Every test that drives the harness replaces this function with a `**kwargs`
    stub, so the real signature was never bound and a capture failed with a
    `TypeError` before reaching the model. Exercise the real function.
    """
    client = MagicMock()
    client.get_current_trace_id.return_value = "trace-eval"
    client.start_as_current_observation.return_value.__enter__.return_value = None
    client.start_as_current_observation.return_value.__exit__.return_value = None

    with (
        patch.object(langfuse, "_langfuse_handler", object()),
        patch.object(langfuse, "get_langfuse_client", return_value=client),
        patch.object(langfuse, "propagate_attributes") as propagate,
    ):
        propagate.return_value.__enter__.return_value = None
        propagate.return_value.__exit__.return_value = None

        async with langfuse.langfuse_request_trace(
            entry_point="eval:driver",
            scenario_id="HLP-COUNT-1",
            repeat=2,
            trace_name="eval-HLP-COUNT-1",
        ) as trace_id:
            assert trace_id == "trace-eval"

    tags = propagate.call_args.kwargs["tags"]
    assert tags[-2:] == ["scenario:HLP-COUNT-1", "repeat:2"]


@pytest.mark.asyncio
async def test_request_trace_is_a_no_op_when_tracing_is_disabled() -> None:
    with (
        patch.object(langfuse, "_langfuse_handler", None),
        patch.object(langfuse, "get_langfuse_client") as get_client,
    ):
        async with langfuse.langfuse_request_trace(
            entry_point="api:chat",
            trace_name="agent-chat",
        ) as trace_id:
            assert trace_id is None

    get_client.assert_not_called()


def test_build_langfuse_config_rejects_unknown_entry_points() -> None:
    with pytest.raises(ValueError, match="Unsupported Langfuse entry point"):
        langfuse.build_langfuse_config(entry_point="api:debug")


def test_stream_latency_records_error_without_visible_ttft() -> None:
    client = MagicMock()
    latency = langfuse.StreamLatency()

    with patch.object(langfuse, "get_langfuse_client", return_value=client):
        latency.complete("error")

    metadata = client.update_current_span.call_args.kwargs["metadata"]
    assert metadata["latency_unit"] == "ms"
    assert metadata["server_e2e_ms"] == metadata["stream_completion_ms"]
    assert metadata["server_e2e_ms"] is not None
    assert metadata["user_visible_ttft_ms"] is None
    assert metadata["outcome"] == "error"
    assert metadata["cold_start"] in {"process-first-agent-request", "warm"}
    assert metadata["environment"] in {"local", "production", "evaluation"}
    assert metadata["model"] == "deepseek-v4-flash"


def test_record_agent_response_failure_updates_the_active_span_with_safe_metadata() -> (
    None
):
    client = MagicMock()

    with patch.object(langfuse, "get_langfuse_client", return_value=client):
        langfuse.record_agent_response_failure(category="messages_empty")

    client.update_current_span.assert_called_once_with(
        metadata={"agent_response_failure_category": "messages_empty"},
        level="WARNING",
    )


def test_build_langfuse_tags_use_the_configured_provider_and_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        langfuse.settings.config_yaml["agent"]["react"], "model", "deepseek-v4.1-flash"
    )

    tags = langfuse.build_langfuse_tags(entry_point="api:chat")

    assert tags[-1] == "model:deepseek-v4.1-flash"


def test_langfuse_environment_is_closed_and_defaults_to_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
