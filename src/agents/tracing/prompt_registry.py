"""Release-pinned prompt text with a native Langfuse link when the texts agree."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Final, Literal

from src.core.config import settings
from src.core.logger import logger

PromptSurface = Literal["system", "schema_context", "sql_generation"]
SYSTEM_PROMPT_SURFACE: Final = "system"
SCHEMA_CONTEXT_PROMPT_SURFACE: Final = "schema_context"
SQL_GENERATION_PROMPT_SURFACE: Final = "sql_generation"
PROMPT_SURFACES: Final[tuple[PromptSurface, ...]] = (
    SYSTEM_PROMPT_SURFACE,
    SCHEMA_CONTEXT_PROMPT_SURFACE,
    SQL_GENERATION_PROMPT_SURFACE,
)


@dataclass(frozen=True)
class PromptDefinition:
    surface: PromptSurface
    yaml_key: str
    name: str


PROMPT_DEFINITIONS: Final[tuple[PromptDefinition, ...]] = (
    PromptDefinition(SYSTEM_PROMPT_SURFACE, "system_prompt", "resumi-system"),
    PromptDefinition(
        SCHEMA_CONTEXT_PROMPT_SURFACE, "schema_context", "resumi-schema-context"
    ),
    PromptDefinition(
        SQL_GENERATION_PROMPT_SURFACE, "sql_generation", "resumi-sql-generation"
    ),
)
PROMPT_DEFINITIONS_BY_SURFACE: Final = {
    definition.surface: definition for definition in PROMPT_DEFINITIONS
}
LANGFUSE_PROMPT_NAMES: Final = {
    definition.yaml_key: definition.name for definition in PROMPT_DEFINITIONS
}
SQL_GENERATION_PROMPT_NAME: Final = LANGFUSE_PROMPT_NAMES["sql_generation"]
ALLOWED_PROMPT_DEPLOYMENT_LABELS: Final = frozenset({"candidate", "production"})


@dataclass(frozen=True)
class ResolvedPrompt:
    """The release text that serves and the optional Langfuse trace link.

    `content` and `version` always come from the release pin in
    `config/prompts.yaml`; a managed Langfuse text never reaches the model.
    `prompt_client` carries the managed prompt only while its text equals the
    release text, so a linked generation can never claim a version the model
    did not read. `is_fallback` is True whenever no managed prompt is linked:
    missing credentials, a failed fetch, or drift.
    """

    surface: PromptSurface
    name: str
    content: str
    version: str
    prompt_client: Any | None
    is_fallback: bool


class PromptRegistry:
    """Serve the release text and link Langfuse only while the texts agree."""

    def __init__(self, client_provider: Callable[[], Any | None]) -> None:
        self._client_provider = client_provider
        # The last (state, managed version) reported per surface, so a drift or
        # a link is logged once per transition instead of once per request.
        self._reported: dict[PromptSurface, tuple[str, str]] = {}

    def resolve(self, surface: PromptSurface) -> ResolvedPrompt:
        definition = PROMPT_DEFINITIONS_BY_SURFACE[surface]
        release = self._release(definition)
        client = self._client_provider()
        if client is None:
            return release

        config = self._configuration()
        try:
            prompt = client.get_prompt(
                definition.name,
                label=config["deployment_label"],
                type="text",
                fallback=release.content,
                cache_ttl_seconds=config["cache_ttl_seconds"],
            )
        except Exception as exc:
            logger.warning(
                "langfuse.prompt_resolution_failed",
                prompt_name=definition.name,
                label=config["deployment_label"],
                error=str(exc),
            )
            return release

        content = getattr(prompt, "prompt", None)
        version = getattr(prompt, "version", None)
        if (
            bool(getattr(prompt, "is_fallback", False))
            or not isinstance(content, str)
            or not content.strip()
            or not isinstance(version, int)
        ):
            return release

        managed_content = content.strip()
        if managed_content != release.content:
            if self._record("drift", definition.surface, version):
                logger.warning(
                    "prompt.drift",
                    surface=definition.surface,
                    prompt_name=definition.name,
                    label=config["deployment_label"],
                    release_version=release.version,
                    managed_version=str(version),
                    release_hash=_text_hash(release.content),
                    managed_hash=_text_hash(managed_content),
                )
            return release

        if self._record("linked", definition.surface, version):
            logger.info(
                "prompt.linked",
                surface=definition.surface,
                prompt_name=definition.name,
                label=config["deployment_label"],
                release_version=release.version,
                managed_version=str(version),
            )
        return ResolvedPrompt(
            surface=surface,
            name=definition.name,
            content=release.content,
            version=release.version,
            prompt_client=prompt,
            is_fallback=False,
        )

    def prefetch(self) -> dict[PromptSurface, ResolvedPrompt]:
        """Resolve every prompt surface before serving.

        Each surface resolves once, so startup records the release versions
        and, with credentials, either a link or `prompt.drift` per surface
        before the first request.
        """
        return {surface: self.resolve(surface) for surface in PROMPT_SURFACES}

    async def resolve_async(self, surface: PromptSurface) -> ResolvedPrompt:
        """Resolve a prompt without blocking an asynchronous request loop."""
        return await asyncio.to_thread(self.resolve, surface)

    async def prefetch_async(self) -> dict[PromptSurface, ResolvedPrompt]:
        """Warm every prompt without blocking application startup's event loop."""
        resolved = await asyncio.gather(
            *(self.resolve_async(surface) for surface in PROMPT_SURFACES)
        )
        return dict(zip(PROMPT_SURFACES, resolved, strict=True))

    def _record(self, state: str, surface: PromptSurface, version: int) -> bool:
        """Report a link state once per transition and managed version."""
        key = (state, str(version))
        if self._reported.get(surface) == key:
            return False
        self._reported[surface] = key
        return True

    @staticmethod
    def _configuration() -> dict[str, str | int]:
        agent = settings.config_yaml.get("agent")
        prompts = agent.get("prompts") if isinstance(agent, dict) else None
        if not isinstance(prompts, dict):
            raise ValueError("Missing 'agent.prompts' configuration")

        label = prompts.get("deployment_label")
        if label not in ALLOWED_PROMPT_DEPLOYMENT_LABELS:
            raise ValueError(
                "agent.prompts.deployment_label must be one of: "
                + ", ".join(sorted(ALLOWED_PROMPT_DEPLOYMENT_LABELS))
            )
        cache_ttl_seconds = prompts.get("cache_ttl_seconds")
        if (
            isinstance(cache_ttl_seconds, bool)
            or not isinstance(cache_ttl_seconds, int)
            or cache_ttl_seconds < 0
        ):
            raise ValueError(
                "agent.prompts.cache_ttl_seconds must be a non-negative integer"
            )
        return {"deployment_label": label, "cache_ttl_seconds": cache_ttl_seconds}

    @staticmethod
    def _release(definition: PromptDefinition) -> ResolvedPrompt:
        """Read the release-pinned text and version from config/prompts.yaml."""
        prompts_root = settings.prompts_yaml.get("prompts")
        if not isinstance(prompts_root, dict):
            raise ValueError("Missing 'prompts' section in config/prompts.yaml")
        content = prompts_root.get(definition.yaml_key)
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"Missing or empty 'prompts.{definition.yaml_key}' in config/prompts.yaml"
            )

        versions = settings.prompts_yaml.get("prompt_versions")
        version = (
            versions.get(definition.surface) if isinstance(versions, dict) else None
        )
        if not isinstance(version, str) or not version.strip():
            raise ValueError(
                f"Missing release-pinned prompt_versions.{definition.surface} in config/prompts.yaml"
            )
        return ResolvedPrompt(
            surface=definition.surface,
            name=definition.name,
            content=content.strip(),
            version=version.strip(),
            prompt_client=None,
            is_fallback=True,
        )


def _text_hash(text: str) -> str:
    """The hash both sides of a drift comparison are reported with."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _langfuse_client() -> Any | None:
    """Avoid a module cycle while keeping Langfuse confined to the tracing layer."""
    from src.agents.tracing.langfuse import get_langfuse_client

    return get_langfuse_client()


_registry = PromptRegistry(_langfuse_client)


def get_prompt_registry() -> PromptRegistry:
    return _registry
