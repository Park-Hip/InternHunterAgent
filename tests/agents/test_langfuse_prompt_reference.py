from __future__ import annotations

import asyncio
import hashlib
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agents.tracing.prompt_registry import (
    PROMPT_DEFINITIONS,
    PromptDefinition,
    PromptRegistry,
    ResolvedPrompt,
)

CONFIGURATION = {"deployment_label": "production", "cache_ttl_seconds": 60}


def _registry(client: MagicMock | None) -> PromptRegistry:
    return PromptRegistry(lambda: client)


def _controlled_release(definition: PromptDefinition) -> ResolvedPrompt:
    return ResolvedPrompt(
        definition.surface,
        definition.name,
        f"release:{definition.surface}",
        f"v-{definition.surface}",
        None,
        True,
    )


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_registry_links_the_managed_prompt_when_its_text_matches_the_release() -> None:
    client = MagicMock()
    native = SimpleNamespace(
        prompt="release:sql_generation", version=4, is_fallback=False
    )
    client.get_prompt.return_value = native

    with (
        patch.object(PromptRegistry, "_configuration", return_value=CONFIGURATION),
        patch.object(PromptRegistry, "_release", side_effect=_controlled_release),
        patch("src.agents.tracing.prompt_registry.logger") as log,
    ):
        resolved = _registry(client).resolve("sql_generation")

    assert resolved.content == "release:sql_generation"
    assert resolved.version == "v-sql_generation"
    assert resolved.prompt_client is native
    assert resolved.is_fallback is False
    args, kwargs = client.get_prompt.call_args
    assert args == ("resumi-sql-generation",)
    assert kwargs["label"] == "production"
    assert kwargs["type"] == "text"
    assert kwargs["cache_ttl_seconds"] == 60
    assert kwargs["fallback"] == "release:sql_generation"
    log.info.assert_called_once_with(
        "prompt.linked",
        surface="sql_generation",
        prompt_name="resumi-sql-generation",
        label="production",
        release_version="v-sql_generation",
        managed_version="4",
    )


def test_registry_serves_the_release_text_and_reports_drift_once() -> None:
    client = MagicMock()
    client.get_prompt.return_value = SimpleNamespace(
        prompt="  stale managed text  ", version=2, is_fallback=False
    )

    with (
        patch.object(PromptRegistry, "_configuration", return_value=CONFIGURATION),
        patch.object(PromptRegistry, "_release", side_effect=_controlled_release),
        patch("src.agents.tracing.prompt_registry.logger") as log,
    ):
        registry = _registry(client)
        first = registry.resolve("system")
        second = registry.resolve("system")

    for resolved in (first, second):
        assert resolved.content == "release:system"
        assert resolved.version == "v-system"
        assert resolved.prompt_client is None
        assert resolved.is_fallback is True
    log.warning.assert_called_once_with(
        "prompt.drift",
        surface="system",
        prompt_name="resumi-system",
        label="production",
        release_version="v-system",
        managed_version="2",
        release_hash=_text_hash("release:system"),
        managed_hash=_text_hash("stale managed text"),
    )


def test_registry_uses_the_release_text_when_the_client_is_unavailable() -> None:
    with patch.object(PromptRegistry, "_release", side_effect=_controlled_release):
        resolved = _registry(None).resolve("system")

    assert resolved.is_fallback is True
    assert resolved.prompt_client is None
    assert resolved.version == "v-system"
    assert resolved.content == "release:system"


def test_registry_uses_the_release_text_when_langfuse_returns_a_fallback() -> None:
    client = MagicMock()
    client.get_prompt.return_value = SimpleNamespace(
        prompt="stale fallback", version=None, is_fallback=True
    )

    with (
        patch.object(PromptRegistry, "_configuration", return_value=CONFIGURATION),
        patch.object(PromptRegistry, "_release", side_effect=_controlled_release),
    ):
        resolved = _registry(client).resolve("sql_generation")

    assert resolved.is_fallback is True
    assert resolved.prompt_client is None
    assert resolved.content == "release:sql_generation"
    assert resolved.version == "v-sql_generation"


def test_registry_prefetches_every_required_surface() -> None:
    client = MagicMock()
    surfaces_by_name = {
        definition.name: definition.surface for definition in PROMPT_DEFINITIONS
    }

    def get_prompt(name: str, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            prompt=f"release:{surfaces_by_name[name]}", version=2, is_fallback=False
        )

    client.get_prompt.side_effect = get_prompt

    with (
        patch.object(PromptRegistry, "_configuration", return_value=CONFIGURATION),
        patch.object(PromptRegistry, "_release", side_effect=_controlled_release),
    ):
        prompts = _registry(client).prefetch()

    assert set(prompts) == {"system", "schema_context", "sql_generation"}
    assert client.get_prompt.call_count == 3
    assert all(prompt.prompt_client is not None for prompt in prompts.values())
    assert {
        surface: prompt.version for surface, prompt in prompts.items()
    } == {
        "system": "v-system",
        "schema_context": "v-schema_context",
        "sql_generation": "v-sql_generation",
    }


@pytest.mark.asyncio
async def test_registry_resolves_without_blocking_the_event_loop() -> None:
    started = threading.Event()
    release = threading.Event()
    loop_progressed = threading.Event()
    observed: dict[str, bool] = {}
    loop = asyncio.get_running_loop()
    client = MagicMock()

    def get_prompt(*_args: object, **_kwargs: object) -> SimpleNamespace:
        started.set()
        release.wait()
        observed["loop_progressed"] = loop_progressed.is_set()
        return SimpleNamespace(
            prompt="release:system", version=2, is_fallback=False
        )

    client.get_prompt.side_effect = get_prompt
    registry = _registry(client)

    with (
        patch.object(PromptRegistry, "_configuration", return_value=CONFIGURATION),
        patch.object(PromptRegistry, "_release", side_effect=_controlled_release),
    ):
        timer = threading.Timer(0.1, release.set)
        timer.start()
        resolution = asyncio.create_task(registry.resolve_async("system"))
        await asyncio.to_thread(started.wait)
        loop.call_soon(loop_progressed.set)
        await asyncio.sleep(0)
        release.set()
        resolved = await resolution
        timer.cancel()

    assert observed["loop_progressed"] is True
    assert resolved.content == "release:system"
    assert resolved.prompt_client is not None
