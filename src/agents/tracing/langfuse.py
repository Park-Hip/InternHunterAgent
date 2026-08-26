from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, cast

from langfuse import Langfuse, LangfuseSpan, propagate_attributes
from langfuse.api import NotFoundError
from langfuse.langchain import CallbackHandler
from langfuse.model import PromptClient

from src.agents.runtime.prompts import load_prompt_versions
from src.agents.tracing.prompt_registry import SQL_GENERATION_PROMPT_NAME
from src.core.config import settings
from src.core.logger import logger

# The handle handed to callers is still a Langfuse object at runtime. Exporting the
# alias from this layer lets the agent runtime annotate it without importing
# `langfuse` itself.
SqlGenerationObservation = LangfuseSpan

_langfuse_handler: CallbackHandler | None = None
_langfuse: Langfuse | None = None
# One-shot negative guard: set only when Langfuse confirms the SQL prompt is not
# registered (NotFoundError), never on a transient failure. Registering the prompt
# after this process has started will not be picked up until the process restarts;
# that is acceptable because deploys restart the process.
_sql_generation_prompt_missing = False


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
        *(f"prompt:{surface}:{version}" for surface, version in load_prompt_versions().items()),
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
    """Attach Session 3's tags and named prompt lineage without exposing Langfuse to routes."""
    tags = build_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    attributes: dict[str, Any] = {
        "tags": tags,
        "metadata": {"prompt_versions": load_prompt_versions()},
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
) -> AsyncIterator[str | None]:
    """Scope one root Langfuse observation to an asynchronous agent request."""
    if _langfuse_handler is None:
        yield None
        return

    with langfuse_trace_attributes(
        entry_point=entry_point,
        trace_name=trace_name,
        scenario_id=scenario_id,
        repeat=repeat,
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


async def get_sql_generation_prompt_reference() -> PromptClient | None:
    """Fetch only the Langfuse reference used to link the direct SQL generation.

    The agent always reads prompt text from config/prompts.yaml.  This best-effort
    lookup supplies only the server-assigned numeric version the Langfuse SDK needs
    to attach prompt lineage to a generation observation.
    """
    global _sql_generation_prompt_missing

    client = get_langfuse_client()
    if client is None:
        return None

    if _sql_generation_prompt_missing:
        return None

    try:
        return await asyncio.to_thread(
            client.get_prompt,
            SQL_GENERATION_PROMPT_NAME,
            label="production",
            type="text",
            cache_ttl_seconds=60,
            max_retries=0,
            # Unit is SECONDS (SDK docstring wrongly says "milliseconds"); keep this
            # low since it blocks the user-facing streaming chat path on every call.
            fetch_timeout_seconds=3,
        )
    except NotFoundError as exc:
        # Structural: the prompt genuinely is not registered. It will not fix
        # itself while this process is running, so stop paying the blocking
        # lookup on every request until the process restarts.
        _sql_generation_prompt_missing = True
        logger.warning(
            "Langfuse SQL prompt reference unavailable: prompt not registered, "
            "disabling lookup for this process until it is registered and the "
            "process restarts",
            error=str(exc),
        )
        return None
    except Exception as exc:
        # Transient: a timeout, connection error, or 5xx should not permanently
        # disable prompt linkage for the life of the process.
        logger.warning("Langfuse SQL prompt reference unavailable", error=str(exc))
        return None


@asynccontextmanager
async def sql_generation_observation(
    question: str,
) -> AsyncIterator[SqlGenerationObservation | None]:
    """Scope one prompt-attributed Langfuse observation to the direct SQL generation.

    Yields ``None`` whenever tracing is disabled or the prompt is not registered, so
    the caller keeps a single code path.  The observation is a span, not a
    generation: the LangChain callback handler already emits the real generation for
    the same call with model, token and cost detail, and a second generation wrapped
    around it would double-count every SQL generation in the Langfuse generation,
    usage and cost aggregates.

    The SDK attaches native prompt linkage only to generation-like observations and
    silently drops ``prompt`` on a span, so the fetched reference is recorded as span
    metadata instead.
    """
    reference = await get_sql_generation_prompt_reference()
    client = get_langfuse_client()
    if reference is None or client is None:
        yield None
        return

    with client.start_as_current_observation(
        as_type="span",
        name="sql_generation",
        input={"question": question},
        metadata={
            "langfuse_prompt_name": reference.name,
            "langfuse_prompt_version": reference.version,
        },
    ) as observation:
        yield cast(SqlGenerationObservation, observation)


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
