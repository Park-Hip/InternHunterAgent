"""Release-pinned prompt text with a native Langfuse link when the texts agree.

A request never calls Langfuse. The registry resolves every surface once at
boot, keeps the result in memory, and a background task refreshes the link on
its own cadence (#698), so an unreachable Langfuse costs boot a bounded wait and
a turn nothing at all. Under the decision on #669 a refresh moves the link and
never the text.
"""

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
# A refresh is the only Langfuse call left in the process, so it is never retried:
# boot waits at most one fetch timeout, and the refresh an interval later is the
# retry. A retried fetch would put the SDK's own 5 s x 3 back on the boot path,
# which is the 16 s every turn paid while resolution ran per request (#698).
PROMPT_FETCH_MAX_RETRIES: Final = 0


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
    """Serve the release text from memory and link Langfuse off the request path.

    Two entry points, and they never overlap. `resolve` is what a turn calls: it
    reads memory and cannot wait on Langfuse (#698). `refresh` is the only
    caller of the SDK, run once at boot and then from a background task, and it
    publishes a whole new snapshot so a reader never sees a partial one.
    """

    def __init__(self, client_provider: Callable[[], Any | None]) -> None:
        self._client_provider = client_provider
        # The last (state, managed version) reported per surface, so a drift or
        # a link is logged once per transition instead of once per refresh.
        self._reported: dict[PromptSurface, tuple[str, str]] = {}
        # What a request reads. A refresh rebinds this to a new mapping instead
        # of mutating the published one, so a concurrent reader keeps a whole
        # snapshot and never a half-updated one.
        self._resolved: dict[PromptSurface, ResolvedPrompt] = {}

    def resolve(self, surface: PromptSurface) -> ResolvedPrompt:
        """Return the prompt as it serves right now, without any Langfuse call."""
        prompt = self._resolved.get(surface)
        if prompt is None:
            # Nothing has resolved this surface yet, so it serves the release
            # text unlinked until the boot refresh, or a refresh after one,
            # publishes what Langfuse holds.
            prompt = self._release(PROMPT_DEFINITIONS_BY_SURFACE[surface])
            self._resolved.setdefault(surface, prompt)
        return prompt

    async def resolve_async(self, surface: PromptSurface) -> ResolvedPrompt:
        """Read the in-memory prompt from an asynchronous request loop.

        The await survives so the request path keeps one shape, but nothing is
        dispatched: a turn cannot be delayed by Langfuse (#698).
        """
        return self.resolve(surface)

    def resolved(self) -> dict[PromptSurface, ResolvedPrompt]:
        """Every surface as it serves right now, without any Langfuse call."""
        return {surface: self.resolve(surface) for surface in PROMPT_SURFACES}

    def clear(self) -> None:
        """Drop the in-memory snapshot so the next resolve serves the release text.

        The snapshot belongs to one client's lifetime; a process that replaces
        its client (or a test that patches one) starts from the release text and
        repopulates through a refresh.
        """
        self._resolved = {}
        self._reported = {}

    def refresh(self) -> dict[PromptSurface, ResolvedPrompt]:
        """Resolve every surface once and publish the result to memory."""
        return self._publish(
            {surface: self._refresh_surface(surface) for surface in PROMPT_SURFACES}
        )

    async def refresh_async(self) -> dict[PromptSurface, ResolvedPrompt]:
        """Refresh every surface without blocking the caller's event loop."""
        refreshed = await asyncio.gather(
            *(
                asyncio.to_thread(self._refresh_surface, surface)
                for surface in PROMPT_SURFACES
            )
        )
        return self._publish(dict(zip(PROMPT_SURFACES, refreshed, strict=True)))

    def _publish(
        self, refreshed: dict[PromptSurface, ResolvedPrompt]
    ) -> dict[PromptSurface, ResolvedPrompt]:
        """Swap in a new snapshot and return it."""
        published = {**self._resolved, **refreshed}
        self._resolved = published
        return published

    def _refresh_surface(self, surface: PromptSurface) -> ResolvedPrompt:
        """One bounded, un-retried lookup that updates the link, never the text."""
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
                max_retries=PROMPT_FETCH_MAX_RETRIES,
                fetch_timeout_seconds=config["fetch_timeout_seconds"],
            )
        except Exception as exc:
            # One line per refresh, per surface, so an unreachable Langfuse is
            # visible in the log without a failing refresh flooding it.
            logger.warning(
                "langfuse.prompt_resolution_failed",
                prompt_name=definition.name,
                label=config["deployment_label"],
                error=str(exc),
            )
            # The text did not move, so the last link Langfuse confirmed is
            # still true; keeping it is what lets a transient outage leave the
            # trace lineage intact.
            return self._resolved.get(surface, release)

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
        return {
            "deployment_label": label,
            "cache_ttl_seconds": cache_ttl_seconds,
            "fetch_timeout_seconds": _positive_seconds(
                prompts, "fetch_timeout_seconds"
            ),
            "refresh_interval_seconds": _positive_seconds(
                prompts, "refresh_interval_seconds"
            ),
        }

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


def _positive_seconds(prompts: dict[str, Any], key: str) -> int:
    """Read one bounded, positive second count, refusing anything else."""
    value = prompts.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise ValueError(f"agent.prompts.{key} must be a positive integer")
    return value


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


def prompt_refresh_interval_seconds() -> int:
    """How often the background task refreshes the in-memory prompt links."""
    return int(PromptRegistry._configuration()["refresh_interval_seconds"])
