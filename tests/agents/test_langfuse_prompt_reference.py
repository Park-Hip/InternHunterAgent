from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.agents.tracing.prompt_registry import PromptRegistry


def _registry(client: MagicMock | None) -> PromptRegistry:
    return PromptRegistry(lambda: client)


def test_registry_fetches_an_explicit_label_and_returns_the_native_prompt() -> None:
    client = MagicMock()
    native = SimpleNamespace(prompt="REMOTE", version=4, is_fallback=False)
    client.get_prompt.return_value = native

    with patch.object(PromptRegistry, "_configuration", return_value={"deployment_label": "production", "cache_ttl_seconds": 60}):
        resolved = _registry(client).resolve("sql_generation")

    assert resolved.content == "REMOTE"
    assert resolved.version == "4"
    assert resolved.prompt_client is native
    args, kwargs = client.get_prompt.call_args
    assert args == ("resumi-sql-generation",)
    assert kwargs["label"] == "production"
    assert kwargs["type"] == "text"
    assert kwargs["cache_ttl_seconds"] == 60
    assert "You generate SQL" in kwargs["fallback"]


def test_registry_uses_release_fallback_when_the_client_is_unavailable() -> None:
    resolved = _registry(None).resolve("system")

    assert resolved.is_fallback is True
    assert resolved.prompt_client is None
    assert resolved.version == "v13"
    assert "You are Resumi" in resolved.content


def test_registry_uses_release_fallback_when_langfuse_returns_a_fallback() -> None:
    client = MagicMock()
    client.get_prompt.return_value = SimpleNamespace(
        prompt="fallback", version=None, is_fallback=True
    )

    with patch.object(PromptRegistry, "_configuration", return_value={"deployment_label": "production", "cache_ttl_seconds": 60}):
        resolved = _registry(client).resolve("sql_generation")

    assert resolved.is_fallback is True
    assert resolved.prompt_client is None


def test_registry_prefetches_every_required_surface() -> None:
    client = MagicMock()
    client.get_prompt.return_value = SimpleNamespace(prompt="REMOTE", version=2, is_fallback=False)

    with patch.object(PromptRegistry, "_configuration", return_value={"deployment_label": "production", "cache_ttl_seconds": 60}):
        prompts = _registry(client).prefetch()

    assert set(prompts) == {"system", "schema_context", "sql_generation"}
    assert client.get_prompt.call_count == 3
