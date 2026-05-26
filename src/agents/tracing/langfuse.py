from __future__ import annotations

from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

from src.core.config import settings

_langfuse = Langfuse(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_BASE_URL,
)

_langfuse_handler = CallbackHandler()


def get_langfuse_handler() -> CallbackHandler:
    return _langfuse_handler


def get_langfuse_client():
    return get_client()


def build_langfuse_config(
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {}

    if session_id:
        metadata["langfuse_session_id"] = session_id
    if user_id:
        metadata["langfuse_user_id"] = user_id

    return {
        "callbacks": [_langfuse_handler],
        "metadata": metadata,
    }