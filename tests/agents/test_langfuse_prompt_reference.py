from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agents.runtime.prompts import resolve_prompt_bundle_async
from src.agents.tracing.prompt_registry import (
    PROMPT_DEFINITIONS,
    PromptDefinition,
    PromptRegistry,
    ResolvedPrompt,
    prompt_refresh_interval_seconds,
)
from src.core.config import settings

CONFIGURATION = {
    "deployment_label": "production",
    "cache_ttl_seconds": 60,
    "fetch_timeout_seconds": 2,
    "refresh_interval_seconds": 300,
}
SURFACES_BY_NAME = {
    definition.name: definition.surface for definition in PROMPT_DEFINITIONS
}


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


def _matching_prompts(version: int = 4) -> dict[str, SimpleNamespace]:
    """One managed prompt per surface whose text equals that surface's release."""
    return {
        name: SimpleNamespace(
            prompt=f"release:{surface}", version=version, is_fallback=False
        )
        for name, surface in SURFACES_BY_NAME.items()
    }


def _configuration() -> patch:
    return patch.object(PromptRegistry, "_configuration", return_value=CONFIGURATION)


def _release() -> patch:
    return patch.object(PromptRegistry, "_release", side_effect=_controlled_release)


def test_registry_links_the_managed_prompt_when_its_text_matches_the_release() -> None:
    client = MagicMock()
    client.get_prompt.side_effect = lambda name, **_kwargs: _matching_prompts()[name]

    with (
        _configuration(),
        _release(),
        patch("src.agents.tracing.prompt_registry.logger") as log,
    ):
        registry = _registry(client)
        refreshed = registry.refresh()
        # The served read is a memory read: the refresh was the only SDK caller.
        resolved = registry.resolve("sql_generation")

    assert resolved is refreshed["sql_generation"]
    assert resolved.content == "release:sql_generation"
    assert resolved.version == "v-sql_generation"
    assert resolved.prompt_client is not None
    assert resolved.is_fallback is False
    assert client.get_prompt.call_count == 3
    args, kwargs = next(
        fetched
        for fetched in client.get_prompt.call_args_list
        if fetched.args == ("resumi-sql-generation",)
    )
    assert kwargs == {
        "label": "production",
        "type": "text",
        "fallback": "release:sql_generation",
        "cache_ttl_seconds": 60,
        "max_retries": 0,
        "fetch_timeout_seconds": 2,
    }
    log.info.assert_any_call(
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
        _configuration(),
        _release(),
        patch("src.agents.tracing.prompt_registry.logger") as log,
    ):
        registry = _registry(client)
        registry.refresh()
        registry.refresh()
        first = registry.resolve("system")
        second = registry.resolve("system")

    for resolved in (first, second):
        assert resolved.content == "release:system"
        assert resolved.version == "v-system"
        assert resolved.prompt_client is None
        assert resolved.is_fallback is True
    log.warning.assert_any_call(
        "prompt.drift",
        surface="system",
        prompt_name="resumi-system",
        label="production",
        release_version="v-system",
        managed_version="2",
        release_hash=_text_hash("release:system"),
        managed_hash=_text_hash("stale managed text"),
    )
    # One drift line per surface in total, however many refreshes happen.
    drift_surfaces = [
        logged.kwargs["surface"]
        for logged in log.warning.call_args_list
        if logged.args == ("prompt.drift",)
    ]
    assert drift_surfaces == ["system", "schema_context", "sql_generation"]


def test_registry_uses_the_release_text_when_the_client_is_unavailable() -> None:
    with _release():
        registry = _registry(None)
        before_any_refresh = registry.resolve("system")
        refreshed = registry.refresh()

    assert before_any_refresh.is_fallback is True
    assert before_any_refresh.prompt_client is None
    assert before_any_refresh.version == "v-system"
    assert before_any_refresh.content == "release:system"
    assert refreshed["system"].is_fallback is True
    assert refreshed["system"].prompt_client is None


def test_registry_uses_the_release_text_when_langfuse_returns_a_fallback() -> None:
    client = MagicMock()
    client.get_prompt.return_value = SimpleNamespace(
        prompt="stale fallback", version=None, is_fallback=True
    )

    with _configuration(), _release():
        resolved = _registry(client).refresh()["sql_generation"]

    assert resolved.is_fallback is True
    assert resolved.prompt_client is None
    assert resolved.content == "release:sql_generation"
    assert resolved.version == "v-sql_generation"


def test_configured_release_versions_are_content_hashes_of_the_configured_texts() -> (
    None
):
    """#700: the version is derived from the text that serves, not a YAML label."""
    prompts = settings.prompts_yaml["prompts"]

    for definition in PROMPT_DEFINITIONS:
        resolved = PromptRegistry._release(definition)
        text = prompts[definition.yaml_key].strip()

        assert resolved.content == text
        assert resolved.version == hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def test_release_version_hashes_the_stripped_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "prompts_yaml",
        {
            "prompts": {
                "system_prompt": "  System text.  ",
                "schema_context": "Schema text.",
                "sql_generation": "SQL text.",
            }
        },
    )

    versions = {
        definition.surface: PromptRegistry._release(definition).version
        for definition in PROMPT_DEFINITIONS
    }

    assert versions == {
        "system": hashlib.sha256(b"System text.").hexdigest()[:12],
        "schema_context": hashlib.sha256(b"Schema text.").hexdigest()[:12],
        "sql_generation": hashlib.sha256(b"SQL text.").hexdigest()[:12],
    }


def test_editing_one_surface_changes_only_its_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = {
        "system_prompt": "System text.",
        "schema_context": "Schema text.",
        "sql_generation": "SQL text.",
    }
    monkeypatch.setattr(settings, "prompts_yaml", {"prompts": prompts})
    before = {
        definition.surface: PromptRegistry._release(definition).version
        for definition in PROMPT_DEFINITIONS
    }

    monkeypatch.setattr(
        settings,
        "prompts_yaml",
        {"prompts": {**prompts, "sql_generation": "SQL text with one more rule."}},
    )
    after = {
        definition.surface: PromptRegistry._release(definition).version
        for definition in PROMPT_DEFINITIONS
    }

    assert after["sql_generation"] != before["sql_generation"]
    assert after["system"] == before["system"]
    assert after["schema_context"] == before["schema_context"]


def test_release_refuses_a_missing_surface_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "prompts_yaml", {"prompts": {}})

    with pytest.raises(ValueError, match="prompts.system_prompt"):
        PromptRegistry._release(PROMPT_DEFINITIONS[0])


def test_registry_refreshes_every_required_surface_and_turns_read_memory() -> None:
    client = MagicMock()
    client.get_prompt.side_effect = (
        lambda name, **_kwargs: _matching_prompts(version=7)[name]
    )

    with _configuration(), _release():
        registry = _registry(client)
        refreshed = registry.refresh()
        served = registry.resolved()
        single = registry.resolve("system")

    assert tuple(refreshed) == ("system", "schema_context", "sql_generation")
    assert all(prompt.prompt_client is not None for prompt in refreshed.values())
    assert {
        surface: prompt.version for surface, prompt in refreshed.items()
    } == {
        "system": "v-system",
        "schema_context": "v-schema_context",
        "sql_generation": "v-sql_generation",
    }
    assert served == refreshed
    assert single is refreshed["system"]
    assert client.get_prompt.call_count == 3


def test_failed_refresh_keeps_the_last_confirmed_prompt_link() -> None:
    client = MagicMock()
    client.get_prompt.side_effect = lambda name, **_kwargs: _matching_prompts()[name]

    with (
        _configuration(),
        _release(),
        patch("src.agents.tracing.prompt_registry.logger") as log,
    ):
        registry = _registry(client)
        linked = registry.refresh()
        client.get_prompt.side_effect = RuntimeError("langfuse down")
        after_failure = registry.refresh()

    assert after_failure["system"] is linked["system"]
    assert after_failure["system"].prompt_client is not None
    assert after_failure["system"].content == "release:system"
    assert after_failure["system"].is_fallback is False
    resolution_failures = [
        logged
        for logged in log.warning.call_args_list
        if logged.args == ("langfuse.prompt_resolution_failed",)
    ]
    assert len(resolution_failures) == 3


def test_refresh_interval_comes_from_the_configured_lifecycle() -> None:
    with _configuration():
        assert prompt_refresh_interval_seconds() == 300


@pytest.mark.asyncio
async def test_a_turn_never_waits_on_a_hanging_langfuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#698: the request path is a memory read even while a fetch never returns."""
    started = threading.Event()
    released = threading.Event()
    client = MagicMock()

    def get_prompt(*_args: object, **_kwargs: object) -> SimpleNamespace:
        started.set()
        released.wait(5)
        return SimpleNamespace(prompt="release:system", version=2, is_fallback=False)

    client.get_prompt.side_effect = get_prompt
    registry = _registry(client)
    monkeypatch.setattr(
        "src.agents.runtime.prompts.get_prompt_registry", lambda: registry
    )

    with _configuration(), _release():
        refresh = asyncio.create_task(registry.refresh_async())
        try:
            await asyncio.to_thread(started.wait, 5)
            began = time.monotonic()
            bundle = await asyncio.wait_for(resolve_prompt_bundle_async(), 1)
            elapsed = time.monotonic() - began
        finally:
            released.set()
            await refresh

    assert elapsed < 0.5
    assert bundle.system.content == "release:system"
    assert bundle.system.is_fallback is True


@pytest.mark.asyncio
async def test_registry_refresh_does_not_block_the_event_loop() -> None:
    started = threading.Event()
    released = threading.Event()
    loop_progressed = threading.Event()
    observed: dict[str, bool] = {}
    loop = asyncio.get_running_loop()
    client = MagicMock()

    def get_prompt(*_args: object, **_kwargs: object) -> SimpleNamespace:
        started.set()
        released.wait(5)
        observed["loop_progressed"] = loop_progressed.is_set()
        return SimpleNamespace(prompt="release:system", version=2, is_fallback=False)

    client.get_prompt.side_effect = get_prompt
    registry = _registry(client)

    with _configuration(), _release():
        refresh = asyncio.create_task(registry.refresh_async())
        try:
            await asyncio.to_thread(started.wait, 5)
            loop.call_soon(loop_progressed.set)
            await asyncio.sleep(0)
        finally:
            released.set()
        refreshed = await refresh

    assert observed["loop_progressed"] is True
    assert refreshed["system"].prompt_client is not None
