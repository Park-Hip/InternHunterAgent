from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Callable, cast

from langfuse import Langfuse, LangfuseSpan, propagate_attributes
from langfuse.langchain import CallbackHandler

from src.agents.runtime.prompts import (
    ResolvedPromptBundle,
    load_resolved_prompt_versions,
    load_resolved_prompt_versions_async,
)
from src.agents.tracing.prompt_registry import (
    SYSTEM_PROMPT_SURFACE,
    ResolvedPrompt,
    get_prompt_registry,
    prompt_refresh_interval_seconds,
)
from src.agents.tracing.stream import StreamLatency, StreamObservation, StreamOutcome
from src.core.config import settings
from src.core.logger import logger

_langfuse_handler: CallbackHandler | None = None
_langfuse: Langfuse | None = None
_project_id: str | None = None


class LangfuseStreamObservation:
    """Publish neutral stream lifecycle timings to the current Langfuse span."""

    def __init__(self) -> None:
        self._latency = StreamLatency()
        self._span: LangfuseSpan | None = None

    def attach_trace(self, trace: object) -> None:
        self._span = cast(LangfuseSpan, trace)

    def mark_user_visible(self) -> None:
        self._latency.mark_user_visible()
        self._update_span()

    def complete(self, outcome: StreamOutcome) -> None:
        self._latency.complete(outcome)
        self._update_span()

    def _update_span(self) -> None:
        client = get_langfuse_client()
        if client is None:
            return
        metadata = {
            "latency_unit": "ms",
            "server_e2e_ms": self._latency.completion_ms,
            "user_visible_ttft_ms": self._latency.user_visible_ttft_ms,
            "stream_completion_ms": self._latency.completion_ms,
            "outcome": self._latency.outcome,
            "cold_start": self._latency.cold_start,
            "environment": get_langfuse_environment(),
            "model": _react_model_name(),
        }
        try:
            if self._span is not None:
                self._span.update(metadata=metadata)
            else:
                client.update_current_span(metadata=metadata)
        except Exception:
            logger.warning("langfuse.stream_latency_diagnostic_failed")


def create_langfuse_stream_observation() -> StreamObservation:
    """Create a best-effort Langfuse adapter for one streamed response."""
    return LangfuseStreamObservation()


def _react_model_name() -> str:
    return settings.agent.deployment_for("react").model


def _langfuse_taxonomy() -> dict[str, Any]:
    observability = settings.config_yaml.get("observability")
    if not isinstance(observability, dict):
        raise ValueError("Missing 'observability' section in config/settings.yaml")
    langfuse = observability.get("langfuse")
    if not isinstance(langfuse, dict):
        raise ValueError(
            "Missing 'observability.langfuse' section in config/settings.yaml"
        )
    return langfuse


def get_langfuse_environment() -> str:
    taxonomy = _langfuse_taxonomy()
    environments = taxonomy.get("environments")
    if not isinstance(environments, dict):
        raise ValueError("Missing 'observability.langfuse.environments' configuration")
    default = environments.get("default")
    if not isinstance(default, str):
        raise ValueError("Invalid 'observability.langfuse.environments' configuration")
    allowed = environments.get("allowed")
    if not isinstance(allowed, list):
        raise ValueError("Invalid 'observability.langfuse.environments' configuration")

    environment = os.getenv("LANGFUSE_TRACING_ENVIRONMENT", default).strip().lower()
    if environment not in allowed:
        raise ValueError(
            "LANGFUSE_TRACING_ENVIRONMENT must be one of: " + ", ".join(allowed)
        )
    return environment


def get_langfuse_release() -> str | None:
    release = os.getenv("RENDER_GIT_COMMIT") or os.getenv("LANGFUSE_RELEASE")
    return release.strip() if release and release.strip() else None


def create_langfuse_client() -> Langfuse:
    """Build the process client with explicit deployment attribution."""
    if not settings.LANGFUSE_BASE_URL:
        raise ValueError(
            "LANGFUSE_BASE_URL is not set. Set it to the Langfuse Cloud host from "
            "ADR-0029 (docs/decisions/adr-0029-langfuse-cloud-hobby-japan.md); the "
            "SDK's own default would export somewhere nobody reads."
        )
    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL,
        environment=get_langfuse_environment(),
        release=get_langfuse_release(),
    )


def build_langfuse_tags(
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
) -> list[str]:
    """Build the deliberately closed per-trace Langfuse tag vocabulary."""
    tags = _base_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    tags[1:1] = [
        f"prompt:{surface}:{version}"
        for surface, version in load_resolved_prompt_versions().items()
    ]
    return tags


def _base_langfuse_tags(
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
) -> list[str]:
    """Build trace tags that do not require remote prompt resolution."""
    taxonomy = _langfuse_taxonomy().get("tag_taxonomy")
    if not isinstance(taxonomy, dict):
        raise ValueError("Missing 'observability.langfuse.tag_taxonomy' configuration")

    entry_points = taxonomy.get("entry_points")
    if not isinstance(entry_points, list):
        raise ValueError(
            "Invalid 'observability.langfuse.tag_taxonomy.entry_points' configuration"
        )
    if entry_point not in entry_points:
        raise ValueError(f"Unsupported Langfuse entry point: {entry_point}")

    deployment = settings.agent.deployment_for("react")
    provider = deployment.provider
    model = deployment.model

    if (scenario_id is None) != (repeat is None):
        raise ValueError("Langfuse evaluation tags require both scenario_id and repeat")
    if repeat is not None and repeat < 1:
        raise ValueError("Langfuse evaluation repeat must be positive")

    tags = [entry_point, f"provider:{provider}", f"model:{model}"]
    if scenario_id is not None:
        if not scenario_id.strip():
            raise ValueError("Langfuse evaluation scenario_id must not be empty")
        tags.extend((f"scenario:{scenario_id}", f"repeat:{repeat}"))
    return tags


async def _build_langfuse_tags_async(
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
    prompts: ResolvedPromptBundle | None = None,
) -> list[str]:
    tags = _base_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    tags[1:1] = [
        f"prompt:{surface}:{version}"
        for surface, version in (
            prompts.versions()
            if prompts is not None
            else await load_resolved_prompt_versions_async()
        ).items()
    ]
    return tags


def validate_langfuse_trace_context(
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
) -> None:
    """Validate the configured Langfuse vocabulary before invoking LangChain."""
    _base_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )


def _prompt_versions_metadata(versions: dict[str, str]) -> dict[str, str]:
    """Encode per-surface prompt lineage as JSON for Langfuse metadata.

    ``propagate_attributes`` coerces every non-string metadata value with
    ``str()``, which would store a Python repr that the read path cannot parse;
    a compact JSON string parses back into the object.
    """
    return {
        "prompt_versions": json.dumps(versions, sort_keys=True, separators=(",", ":"))
    }


@contextmanager
def langfuse_trace_attributes(
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
    trace_name: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> Iterator[None]:
    """Attach Session 3's tags and named prompt lineage without exposing Langfuse to routes."""
    tags = build_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    attributes: dict[str, Any] = {
        "tags": tags,
        "metadata": _prompt_versions_metadata(load_resolved_prompt_versions()),
    }
    if trace_name is not None:
        attributes["trace_name"] = trace_name
    if session_id is not None:
        attributes["session_id"] = session_id
    if user_id is not None:
        attributes["user_id"] = user_id

    with propagate_attributes(**attributes):
        yield


@asynccontextmanager
async def langfuse_request_trace(
    *,
    entry_point: str,
    trace_name: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    on_span_started: Callable[[LangfuseSpan], None] | None = None,
    prompts: ResolvedPromptBundle | None = None,
) -> AsyncIterator[str | None]:
    """Scope one root Langfuse observation to an asynchronous agent request."""
    if _langfuse_handler is None:
        yield None
        return

    tags = await _build_langfuse_tags_async(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
        prompts=prompts,
    )
    attributes: dict[str, Any] = {
        "tags": tags,
        "metadata": _prompt_versions_metadata(
            prompts.versions()
            if prompts is not None
            else await load_resolved_prompt_versions_async()
        ),
        "trace_name": trace_name,
    }
    if session_id is not None:
        attributes["session_id"] = session_id
    if user_id is not None:
        attributes["user_id"] = user_id

    with propagate_attributes(**attributes):
        client = get_langfuse_client()
        if client is None:
            yield None
            return
        with client.start_as_current_observation(
            as_type="span", name=trace_name
        ) as span:
            if on_span_started is not None:
                on_span_started(span)
            yield client.get_current_trace_id()


def init_langfuse() -> None:
    """Create the process client and callback handler, or leave tracing disabled.

    Ownership is explicit: the serving lifespan and the evaluation driver call
    this for their own process and hand the client to `shutdown_langfuse` the
    same way. Importing this module does nothing, so a broken configuration can
    no longer surface first as a tracing warning, and a client can no longer
    outlive the process that was supposed to end it. A client that already
    exists is left alone, so a second lifespan in one process reuses it instead
    of leaking another. This never raises: tracing must not block boot.
    """
    global _langfuse, _langfuse_handler
    if _langfuse is not None:
        return

    try:
        tracing_disabled = os.getenv("LANGFUSE_ENABLED", "true").lower() in {
            "0",
            "false",
            "no",
        }
        if (
            not tracing_disabled
            and settings.LANGFUSE_PUBLIC_KEY
            and settings.LANGFUSE_SECRET_KEY
        ):
            client = create_langfuse_client()
            handler = CallbackHandler()
            _langfuse = client
            _langfuse_handler = handler
        elif tracing_disabled:
            logger.info("Langfuse tracing disabled for this process")
        else:
            logger.warning("Langfuse tracing disabled: missing Langfuse credentials")
    except Exception as exc:
        _langfuse = None
        _langfuse_handler = None
        logger.warning(
            "Langfuse tracing disabled: failed to initialize", error=str(exc)
        )


def get_langfuse_handler() -> CallbackHandler | None:
    """Return the callback handler for eval writeback compatibility."""
    return _langfuse_handler


def get_langfuse_client() -> Langfuse | None:
    """Return the process client only when tracing initialized successfully."""
    return _langfuse


def langfuse_trace_url(*, trace_id: str | None) -> str | None:
    """Build the trace URL from the boot-resolved project id, without any I/O.

    The URL is pure string composition, so an unreachable Langfuse can never
    block or fail a finished turn (#699). Null when the turn has no trace id,
    when the project id was not resolved at startup, or when the base URL is
    missing. The string matches what the SDK's `get_trace_url` produced for
    the same host and project.
    """
    if not trace_id or _project_id is None or not settings.LANGFUSE_BASE_URL:
        return None
    return f"{settings.LANGFUSE_BASE_URL}/project/{_project_id}/traces/{trace_id}"


@contextmanager
def langfuse_prompt_attributes(prompt: ResolvedPrompt) -> Iterator[None]:
    """Attach a native PromptClient to generations made by the LangChain callback.

    A prompt is only linkable when the installed SDK can propagate it, so the
    locked Langfuse version is a serving requirement, not a preference.
    """
    if prompt.prompt_client is None:
        yield
        return
    with propagate_attributes(prompt=prompt.prompt_client):
        yield


async def prepare_native_prompts_startup() -> None:
    """Resolve every prompt the served bundle runs on, before requests can.

    This is the one resolution the serving process does on the request path's
    behalf: it is bounded by `agent.prompts.fetch_timeout_seconds`, is never
    retried, and the registry keeps what it resolves in memory from here on
    (#698). Every turn after it is a memory read, so an unreachable Langfuse
    delays boot once instead of every question.

    A prompt that was never registered in Langfuse degrades to the checked-in
    text, which is defensible behaviour but an operator still needs to see which
    version is actually live, so the boot line reports the link per surface and
    not only the release version.
    """
    resolved = await get_prompt_registry().refresh_async()
    logger.info(
        "langfuse.prompts_prefetched",
        prompts={surface: prompt.version for surface, prompt in resolved.items()},
        linked={
            surface: prompt.prompt_client is not None
            for surface, prompt in resolved.items()
        },
        served_system_surface=SYSTEM_PROMPT_SURFACE,
        warmed=tuple(resolved),
    )


async def refresh_prompt_links_forever() -> None:
    """Keep the in-memory prompt links fresh for the life of the process (#698).

    The wait comes first because boot has already resolved once, so the first
    refresh lands a full interval later instead of repeating the boot lookup. A
    refresh moves the link and never the text (#669), and a refresh that fails
    is one logged line per surface: the release text keeps serving, the next
    interval is the retry, and a turn is never waiting on any of it.
    """
    interval = prompt_refresh_interval_seconds()
    while True:
        await asyncio.sleep(interval)
        try:
            await get_prompt_registry().refresh_async()
        except Exception:
            logger.exception("langfuse.prompt_refresh_failed")


def _fetch_project_id(client: Langfuse) -> str | None:
    """Return the project id the credentials resolve to, or None.

    The same `api.projects.get` call the SDK's `auth_check` makes, kept here
    so the response is available for caching instead of a bare boolean.
    """
    projects = client.api.projects.get()
    if not projects.data or not projects.data[0].id:
        return None
    return projects.data[0].id


async def diagnose_langfuse_startup() -> None:
    """Log non-fatal credential diagnostics and resolve the project id once.

    The project id is what the request path needs to build a trace URL without
    network I/O (#699). It is fetched here, on a worker thread, once per
    process: boot does not wait on Langfuse, and no request ever resolves it.
    A failure is only a diagnostic; requests keep serving, with a null trace
    URL, until the next process start.
    """
    global _project_id
    client = get_langfuse_client()
    if client is None:
        logger.info("Langfuse startup authentication skipped: tracing disabled")
        return

    try:
        _project_id = await asyncio.to_thread(_fetch_project_id, client)
    except Exception as exc:
        logger.warning("Langfuse startup authentication failed", error=str(exc))
        return

    if _project_id is not None:
        logger.info("Langfuse startup authentication succeeded")
    else:
        logger.warning("Langfuse startup authentication failed")


async def shutdown_langfuse() -> None:
    """Drain tracing events during app shutdown without blocking teardown.

    The module state is cleared even when draining fails, so the getters report
    "tracing disabled" after shutdown and a later `init_langfuse` creates a
    fresh client instead of reusing a drained one. The resolved project id is
    dropped with it, so a new lifespan resolves it again.
    """
    global _langfuse, _langfuse_handler, _project_id
    client = get_langfuse_client()
    _project_id = None
    if client is None:
        return

    try:
        await asyncio.to_thread(client.shutdown)
    except Exception as exc:
        logger.warning("Langfuse shutdown failed", error=str(exc))
    finally:
        _langfuse = None
        _langfuse_handler = None


def build_langfuse_config(
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
) -> dict[str, object]:
    config: dict[str, object] = {}

    if _langfuse_handler is not None:
        config["callbacks"] = [_langfuse_handler]

    validate_langfuse_trace_context(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    return config
