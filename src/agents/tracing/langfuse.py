from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Callable, cast

from langfuse import Langfuse, LangfuseSpan, propagate_attributes
from langfuse.langchain import CallbackHandler

from src.agents.runtime.prompts import (
    load_resolved_prompt_versions,
    load_resolved_prompt_versions_async,
)
from src.agents.tracing.prompt_registry import ResolvedPrompt, get_prompt_registry
from src.agents.tracing.stream import StreamLatency, StreamObservation, StreamOutcome
from src.core.config import settings
from src.core.logger import logger

_langfuse_handler: CallbackHandler | None = None
_langfuse: Langfuse | None = None
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
    agent = settings.config_yaml.get("agent")
    if not isinstance(agent, dict) or not isinstance(agent.get("react"), dict):
        return "unknown"
    model = agent["react"].get("model")
    return model if isinstance(model, str) else "unknown"


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
            "D-029; the SDK's own default would export somewhere nobody reads."
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

    agent = settings.config_yaml.get("agent")
    if not isinstance(agent, dict) or not isinstance(agent.get("react"), dict):
        raise ValueError("Missing 'agent.react' configuration")
    react = agent["react"]
    provider = react.get("provider", agent.get("provider"))
    model = react.get("model")
    if not isinstance(provider, str) or not isinstance(model, str):
        raise ValueError("Invalid 'agent.react' provider/model configuration")

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
) -> list[str]:
    tags = _base_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    tags[1:1] = [
        f"prompt:{surface}:{version}"
        for surface, version in (await load_resolved_prompt_versions_async()).items()
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
        "metadata": {"prompt_versions": load_resolved_prompt_versions()},
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
) -> AsyncIterator[str | None]:
    """Scope one root Langfuse observation to an asynchronous agent request."""
    if _langfuse_handler is None:
        yield None
        return

    tags = await _build_langfuse_tags_async(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    attributes: dict[str, Any] = {
        "tags": tags,
        "metadata": {"prompt_versions": await load_resolved_prompt_versions_async()},
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
        _langfuse = create_langfuse_client()
        _langfuse_handler = CallbackHandler()
    elif tracing_disabled:
        logger.info("Langfuse tracing disabled for this process")
    else:
        logger.warning("Langfuse tracing disabled: missing Langfuse credentials")
except Exception as exc:
    logger.warning("Langfuse tracing disabled: failed to initialize", error=str(exc))


def get_langfuse_handler() -> CallbackHandler | None:
    """Return the callback handler for eval writeback compatibility."""
    return _langfuse_handler


def get_langfuse_client() -> Langfuse | None:
    """Return the process client only when tracing initialized successfully."""
    return _langfuse


def record_agent_response_failure(*, category: str) -> None:
    """Attach a safe extraction-failure category to the active request span."""
    client = get_langfuse_client()
    if client is None:
        return

    try:
        client.update_current_span(
            metadata={"agent_response_failure_category": category},
            level="WARNING",
        )
    except Exception:
        logger.warning(
            "langfuse.agent_response_failure_diagnostic_failed",
            failure_category=category,
        )


@contextmanager
def langfuse_prompt_attributes(prompt: ResolvedPrompt) -> Iterator[None]:
    """Attach a native PromptClient to generations made by the LangChain callback."""
    if prompt.prompt_client is None:
        yield
        return
    with propagate_attributes(prompt=prompt.prompt_client):
        yield


async def prepare_native_prompts_startup() -> None:
    """Warm every prompt before requests can use the managed prompt deployment."""
    resolved = await get_prompt_registry().prefetch_async()
    logger.info(
        "langfuse.prompts_prefetched",
        prompts={surface: prompt.version for surface, prompt in resolved.items()},
    )


async def diagnose_langfuse_startup() -> None:
    """Log non-fatal credential diagnostics after the application starts."""
    client = get_langfuse_client()
    if client is None:
        logger.info("Langfuse startup authentication skipped: tracing disabled")
        return

    try:
        authenticated = await asyncio.to_thread(client.auth_check)
    except Exception as exc:
        logger.warning("Langfuse startup authentication failed", error=str(exc))
        return

    if authenticated:
        logger.info("Langfuse startup authentication succeeded")
    else:
        logger.warning("Langfuse startup authentication failed")


async def shutdown_langfuse() -> None:
    """Drain tracing events during app shutdown without blocking teardown."""
    client = get_langfuse_client()
    if client is None:
        return

    try:
        await asyncio.to_thread(client.shutdown)
    except Exception as exc:
        logger.warning("Langfuse shutdown failed", error=str(exc))


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
