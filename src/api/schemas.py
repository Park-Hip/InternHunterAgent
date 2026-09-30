from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

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


class StreamSessionEvent(BaseModel):
    type: Literal["session"]
    session_id: str


class StreamTokenEvent(BaseModel):
    type: Literal["token"]
    text: str


class StreamMetadataEvent(BaseModel):
    type: Literal["metadata"]
    trace_id: str | None
    trace_url: str | None


class StreamErrorEvent(StreamErrorResponse):
    type: Literal["error"]


class StreamToolEvent(BaseModel):
    """Public payload for an in-band SSE ``tool`` event.

    Tool arguments reach the browser. They are restricted here to short strings,
    because the tools receive reader-derived filters and this event is shown to
    the reader. Anything longer or structured belongs in a future, separate
    contract rather than in this one.
    """

    type: Literal["tool"]
    name: str
    status: Literal["running", "ok", "error"]
    call_id: str | None = None
    arguments: dict[str, str] = Field(default_factory=dict)
    duration_ms: int | None = None
    error: str | None = None
    #: How many rows the tool actually matched. Present when the tool can say, and
    #: None when it cannot - which is different from zero.
    row_count: int | None = None
    #: True when the returned rows were capped. A count without this would imply
    #: the answer shows every match, which is exactly the impression to avoid.
    truncated: bool = False


class StreamDoneEvent(BaseModel):
    type: Literal["done"]


StreamEvent = Annotated[
    StreamSessionEvent
    | StreamTokenEvent
    | StreamMetadataEvent
    | StreamErrorEvent
    | StreamToolEvent
    | StreamDoneEvent,
    Field(discriminator="type"),
]
STREAM_EVENT_SCHEMA = TypeAdapter(StreamEvent).json_schema()
