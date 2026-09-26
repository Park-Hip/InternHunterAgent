"""Prompt accessors backed by managed Langfuse versions or release fallbacks."""

from contextvars import ContextVar
from dataclasses import dataclass
from contextlib import contextmanager
from collections.abc import Iterator
from typing import cast

from langchain.messages import SystemMessage

from src.agents.tracing.prompt_registry import (
    PROMPT_SURFACES,
    PromptSurface,
    SCHEMA_CONTEXT_PROMPT_SURFACE,
    SQL_GENERATION_PROMPT_SURFACE,
    SYSTEM_PROMPT_SURFACE,
    ResolvedPrompt,
    get_prompt_registry,
)
from src.core.config import settings


@dataclass(frozen=True)
class ResolvedPromptBundle:
    """One request's immutable view of every managed prompt surface."""

    system: ResolvedPrompt
    schema_context: ResolvedPrompt
    sql_generation: ResolvedPrompt

    def for_surface(self, surface: str) -> ResolvedPrompt:
        return getattr(self, surface)

    def versions(self) -> dict[str, str]:
        return {
            surface: self.for_surface(surface).version for surface in PROMPT_SURFACES
        }


_active_prompt_bundle: ContextVar[ResolvedPromptBundle | None] = ContextVar(
    "active_prompt_bundle", default=None
)


@contextmanager
def prompt_bundle_context(bundle: ResolvedPromptBundle) -> Iterator[None]:
    """Keep all nested model calls on the request's resolved prompt versions."""
    token = _active_prompt_bundle.set(bundle)
    try:
        yield
    finally:
        _active_prompt_bundle.reset(token)


def active_prompt_bundle() -> ResolvedPromptBundle | None:
    return _active_prompt_bundle.get()


def resolve_prompt(surface: str) -> ResolvedPrompt:
    """Return the configured managed version, or the checked-in release fallback."""
    if surface not in PROMPT_SURFACES:
        raise ValueError(f"Unsupported prompt surface: {surface}")
    return get_prompt_registry().resolve(surface)


async def resolve_prompt_async(surface: str) -> ResolvedPrompt:
    """Resolve a managed prompt without blocking the request event loop."""
    if surface not in PROMPT_SURFACES:
        raise ValueError(f"Unsupported prompt surface: {surface}")
    return await get_prompt_registry().resolve_async(cast(PromptSurface, surface))


async def resolve_prompt_bundle_async() -> ResolvedPromptBundle:
    """Resolve every prompt once for a request or evaluation capture."""
    prompts = await get_prompt_registry().prefetch_async()
    return ResolvedPromptBundle(
        system=prompts[SYSTEM_PROMPT_SURFACE],
        schema_context=prompts[SCHEMA_CONTEXT_PROMPT_SURFACE],
        sql_generation=prompts[SQL_GENERATION_PROMPT_SURFACE],
    )


def load_system_prompt_resolution() -> ResolvedPrompt:
    return resolve_prompt(SYSTEM_PROMPT_SURFACE)


async def load_system_prompt_resolution_async() -> ResolvedPrompt:
    bundle = active_prompt_bundle()
    return (
        bundle.system
        if bundle is not None
        else await resolve_prompt_async(SYSTEM_PROMPT_SURFACE)
    )


def _load_release_fallback(yaml_key: str) -> str:
    prompts_root = settings.prompts_yaml.get("prompts")
    if not isinstance(prompts_root, dict):
        raise ValueError("Missing 'prompts' section in config/prompts.yaml")
    content = prompts_root.get(yaml_key)
    if not isinstance(content, str) or not content.strip():
        raise ValueError(
            f"Missing or empty 'prompts.{yaml_key}' in config/prompts.yaml"
        )
    return content.strip()


def load_system_prompt() -> SystemMessage:
    """Return the reviewed release fallback for offline callers and tests."""
    return SystemMessage(content=_load_release_fallback("system_prompt"))


def load_schema_context_resolution() -> ResolvedPrompt:
    return resolve_prompt(SCHEMA_CONTEXT_PROMPT_SURFACE)


async def load_schema_context_resolution_async() -> ResolvedPrompt:
    bundle = active_prompt_bundle()
    return (
        bundle.schema_context
        if bundle is not None
        else await resolve_prompt_async(SCHEMA_CONTEXT_PROMPT_SURFACE)
    )


def load_schema_context() -> str:
    """Return the reviewed release fallback for offline callers and tests."""
    return _load_release_fallback("schema_context")


def load_sql_generation_prompt_resolution() -> ResolvedPrompt:
    return resolve_prompt(SQL_GENERATION_PROMPT_SURFACE)


async def load_sql_generation_prompt_resolution_async() -> ResolvedPrompt:
    bundle = active_prompt_bundle()
    return (
        bundle.sql_generation
        if bundle is not None
        else await resolve_prompt_async(SQL_GENERATION_PROMPT_SURFACE)
    )


def load_sql_generation_prompt() -> str:
    """Return the reviewed release fallback for offline callers and tests."""
    return _load_release_fallback("sql_generation")


def load_prompt_versions() -> dict[str, str]:
    """Return release-pinned lineage for offline artifacts and fallback operation."""
    prompt_versions = settings.prompts_yaml.get("prompt_versions")
    if not isinstance(prompt_versions, dict) or set(prompt_versions) != set(
        PROMPT_SURFACES
    ):
        raise ValueError(
            "config/prompts.yaml must declare exactly these prompt_versions: "
            + ", ".join(PROMPT_SURFACES)
        )
    if not all(
        isinstance(prompt_versions[surface], str) and prompt_versions[surface].strip()
        for surface in PROMPT_SURFACES
    ):
        raise ValueError("Every prompt_versions value must be a non-empty string")
    return {surface: prompt_versions[surface].strip() for surface in PROMPT_SURFACES}


def load_resolved_prompt_versions() -> dict[str, str]:
    """Return exact remote versions when native prompts are available."""
    return {surface: resolve_prompt(surface).version for surface in PROMPT_SURFACES}


async def load_resolved_prompt_versions_async() -> dict[str, str]:
    """Return managed prompt lineage without blocking an asynchronous request loop."""
    bundle = active_prompt_bundle() or await resolve_prompt_bundle_async()
    return bundle.versions()


def load_behavior_glossary() -> dict[str, str]:
    """Canonical hedge and refusal phrasings, keyed by token."""
    glossary = settings.prompts_yaml.get("behavior_glossary")
    if not isinstance(glossary, dict) or not glossary:
        raise ValueError("Missing or empty 'behavior_glossary' in config/prompts.yaml")

    for token, phrasing in glossary.items():
        if not isinstance(token, str) or not token.strip():
            raise ValueError(
                "Every 'behavior_glossary' token must be a non-empty string"
            )
        if not isinstance(phrasing, str) or not phrasing.strip():
            raise ValueError(f"Empty 'behavior_glossary' phrasing for token: {token}")

    return {token: phrasing.strip() for token, phrasing in glossary.items()}
