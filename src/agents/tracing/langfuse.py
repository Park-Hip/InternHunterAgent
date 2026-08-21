from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler

from src.agents.runtime.prompts import load_prompt_version
from src.core.config import settings
from src.core.logger import logger

_langfuse_handler: CallbackHandler | None = None
_langfuse: Langfuse | None = None


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

    tags = [
        entry_point,
        f"prompt:{load_prompt_version()}",
        f"provider:{provider}",
        f"model:{model}",
    ]
    if scenario_id is not None:
        if not scenario_id.strip():
            raise ValueError("Langfuse evaluation scenario_id must not be empty")
        tags.extend((f"scenario:{scenario_id}", f"repeat:{repeat}"))
    return tags


def validate_langfuse_trace_context(
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
) -> None:
    """Validate the configured Langfuse vocabulary before invoking LangChain."""
    build_langfuse_tags(
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
    """Attach Session 3's tags and prompt version without exposing Langfuse to routes."""
    tags = build_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    attributes: dict[str, Any] = {
        "tags": tags,
        "version": load_prompt_version(),
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
    session_id: str | None = None,
    user_id: str | None = None,
) -> AsyncIterator[str | None]:
    """Scope one root Langfuse observation to an asynchronous agent request."""
    if _langfuse_handler is None:
        yield None
        return

    with langfuse_trace_attributes(
        entry_point=entry_point,
        trace_name=trace_name,
        session_id=session_id,
        user_id=user_id,
    ):
        client = get_langfuse_client()
        if client is None:
            yield None
            return
        with client.start_as_current_observation(as_type="span", name=trace_name):
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
