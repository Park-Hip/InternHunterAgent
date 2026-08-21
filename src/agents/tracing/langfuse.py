from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langfuse import Langfuse, get_client, propagate_attributes
from langfuse.langchain import CallbackHandler

from src.agents.runtime.prompts import load_prompt_version
from src.core.config import settings
from src.core.logger import logger

_langfuse_handler: CallbackHandler | None = None


def _string_list(value: Any, *, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Invalid '{name}' configuration")
    return value


def _langfuse_taxonomy() -> dict[str, Any]:
    observability = settings.config_yaml.get("observability")
    if not isinstance(observability, dict):
        raise ValueError("Missing 'observability' section in config/settings.yaml")
    langfuse = observability.get("langfuse")
    if not isinstance(langfuse, dict):
        raise ValueError("Missing 'observability.langfuse' section in config/settings.yaml")
    return langfuse


def get_langfuse_environment() -> str:
    taxonomy = _langfuse_taxonomy()
    environments = taxonomy.get("environments")
    if not isinstance(environments, dict):
        raise ValueError("Missing 'observability.langfuse.environments' configuration")
    default = environments.get("default")
    if not isinstance(default, str):
        raise ValueError("Invalid 'observability.langfuse.environments' configuration")
    allowed = _string_list(
        environments.get("allowed"),
        name="observability.langfuse.environments",
    )

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

    entry_points = _string_list(
        taxonomy.get("entry_points"),
        name="observability.langfuse.tag_taxonomy.entry_points",
    )
    providers = _string_list(
        taxonomy.get("providers"),
        name="observability.langfuse.tag_taxonomy.providers",
    )
    models = _string_list(
        taxonomy.get("models"),
        name="observability.langfuse.tag_taxonomy.models",
    )
    if entry_point not in entry_points:
        raise ValueError(f"Unsupported Langfuse entry point: {entry_point}")

    agent = settings.config_yaml.get("agent")
    if not isinstance(agent, dict) or not isinstance(agent.get("react"), dict):
        raise ValueError("Missing 'agent.react' configuration")
    react = agent["react"]
    provider = react.get("provider", agent.get("provider"))
    model = react.get("model")
    if provider not in providers or model not in models:
        raise ValueError("Agent provider/model is outside the Langfuse tag taxonomy")

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


@contextmanager
def langfuse_trace_attributes(
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
) -> Iterator[None]:
    """Attach Session 3's tags and prompt version without exposing Langfuse to routes."""
    tags = build_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )
    with propagate_attributes(tags=tags, version=load_prompt_version()):
        yield

try:
    tracing_disabled = os.getenv("LANGFUSE_ENABLED", "true").lower() in {"0", "false", "no"}
    if not tracing_disabled and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        _langfuse = create_langfuse_client()
        _langfuse_handler = CallbackHandler()
    elif tracing_disabled:
        logger.info("Langfuse tracing disabled for this process")
    else:
        logger.warning("Langfuse tracing disabled: missing Langfuse credentials")
except Exception as exc:
    logger.warning("Langfuse tracing disabled: failed to initialize", error=str(exc))


def get_langfuse_handler() -> CallbackHandler | None:
    return _langfuse_handler


def get_langfuse_client():
    return get_client()


def build_langfuse_config(
    session_id: str | None = None,
    user_id: str | None = None,
    *,
    entry_point: str,
    scenario_id: str | None = None,
    repeat: int | None = None,
) -> dict[str, object]:
    config: dict[str, object] = {}

    if _langfuse_handler is not None:
        config["callbacks"] = [_langfuse_handler]

    metadata: dict[str, object] = {}
    if session_id:
        metadata["langfuse_session_id"] = session_id
    if user_id:
        metadata["langfuse_user_id"] = user_id
    metadata["langfuse_tags"] = build_langfuse_tags(
        entry_point=entry_point,
        scenario_id=scenario_id,
        repeat=repeat,
    )

    if metadata:
        config["metadata"] = metadata

    return config
