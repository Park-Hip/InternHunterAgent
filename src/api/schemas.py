from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_MAX_QUERY_CHARS = 2000

# Streaming chat emits SSE events in this order: session {session_id}, token
# {text} zero or more times, metadata {trace_id, trace_url}, then done {}.
# On mid-run failure, error {message, code, retryable} replaces further
# token/metadata events before done. QueryResponse remains the one-shot route
# schema.

class QueryRequest(BaseModel):
    query: str = Field(..., max_length=DEFAULT_MAX_QUERY_CHARS)
    user_id: str | None = None
    # Omit session_id on the first demo turn: the server mints an unguessable uuid4,
    # returns it, and the UI reuses it so visitors do not share one conversation.
    session_id: str | None = None

class QueryResponse(BaseModel):
    answer: str
    session_id: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None


class StreamErrorResponse(BaseModel):
    """Public payload for an in-band SSE ``error`` event."""

    message: str
    code: Literal["provider_busy", "internal_error"]
    retryable: bool
