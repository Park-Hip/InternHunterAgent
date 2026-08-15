from __future__ import annotations

import os

from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

from src.core.config import settings
from src.core.logger import logger

_langfuse_handler: CallbackHandler | None = None

try:
    tracing_disabled = os.getenv("LANGFUSE_ENABLED", "true").lower() in {"0", "false", "no"}
    if not tracing_disabled and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        _langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_BASE_URL,
        )
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
) -> dict[str, object]:
    config: dict[str, object] = {}

    if _langfuse_handler is not None:
        config["callbacks"] = [_langfuse_handler]

    metadata: dict[str, object] = {}
    if session_id:
        metadata["langfuse_session_id"] = session_id
    if user_id:
        metadata["langfuse_user_id"] = user_id

    if metadata:
        config["metadata"] = metadata

    return config
