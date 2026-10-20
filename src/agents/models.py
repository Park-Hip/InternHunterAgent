"""The typed stream events, and the internal signals that travel beside them.

The six public events in this module are the SSE contract: their names, their
payload fields including ``type``, and their order. They live in the agents
package rather than in ``src/api/schemas.py`` because the runtime and the service
produce them, and a service must not import from the API layer; the API imports
them from here to publish ``STREAM_EVENT_SCHEMA`` (#679).

Streaming chat emits SSE events in this order: ``session {session_id}``, ``token
{text}`` zero or more times, ``metadata {trace_id, trace_url, answer_source}``,
then ``done {}``. On mid-run failure, ``error {message, code, retryable}``
replaces further token/metadata events before ``done``.

The internal signals are not part of that contract. The runtime publishes them
through the same per-turn queue as its public events, because a turn's frames
must stay in one order, but the service consumes them and decides what the
reader sees: no internal signal ever reaches the wire.
"""

from dataclasses import dataclass
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, Field

from src.core.errors import ErrorCode


class StreamSessionEvent(BaseModel):
    """The first frame of a turn: the id the conversation is pinned to."""

    type: Literal["session"]
    session_id: str


class StreamTokenEvent(BaseModel):
    """Answer text, many per turn."""

    type: Literal["token"]
    text: str


class StreamMetadataEvent(BaseModel):
    """The turn summary, once, after the last token; never on a failed turn.

    The runtime emits it while its Langfuse span is still open, so the recorded
    completion latency covers the whole stream rather than the model call.

    ``answer_source`` is the machine-readable empty-answer signal: ``model``
    when at least one token came from the model, ``fallback`` when the service
    injected ``FALLBACK_ANSWER`` because the model wrote nothing. Clients must
    key the empty-answer outcome on this field rather than on the copy of the
    fallback sentence.
    """

    type: Literal["metadata"]
    trace_id: str | None
    trace_url: str | None
    answer_source: Literal["model", "fallback"] = "model"


class StreamErrorEvent(BaseModel):
    """Public payload for an in-band SSE ``error`` event."""

    type: Literal["error"]
    message: str
    code: ErrorCode
    retryable: bool


class InternalStreamError(StreamErrorEvent):
    """The service's error event: the public frame plus the internal status.

    The collected JSON route maps ``status_code`` to its own response status
    (#689), and the SSE route strips it, so the published frame keeps exactly
    the fields ``StreamErrorEvent`` declares.
    """

    status_code: int

    def as_public_event(self) -> StreamErrorEvent:
        """The frame that crosses the wire, without the internal status."""

        return StreamErrorEvent(
            type=self.type,
            message=self.message,
            code=self.code,
            retryable=self.retryable,
        )


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
    #: Where the returned rows started in the match set, when the tool ran a row
    #: listing. None means the tool did not report a page.
    page_offset: int | None = None
    #: How many rows this call returned. Distinct from ``row_count``, which is
    #: the whole match set: zero here on a later page means the page starts past
    #: the end, not that the search matched nothing.
    rows_returned: int | None = None


class StreamDoneEvent(BaseModel):
    """The terminal frame; always last, on success and failure alike."""

    type: Literal["done"]


#: One public frame, discriminated on ``type``. The order of the union members
#: is the order they are published in, not a required emission order.
StreamEvent: TypeAlias = Annotated[
    StreamSessionEvent
    | StreamTokenEvent
    | StreamMetadataEvent
    | StreamErrorEvent
    | StreamToolEvent
    | StreamDoneEvent,
    Field(discriminator="type"),
]


@dataclass(frozen=True, slots=True)
class RuntimeCompleted:
    """The runtime's producer finished and has no more public events to yield."""


@dataclass(frozen=True, slots=True)
class RuntimeFailed:
    """The runtime's turn failed before it could finish.

    The exception is the original one and stays internal: the service classifies
    it and yields a public ``error`` frame carrying none of its text.
    """

    exception: Exception


#: What travels over the runtime's per-turn queue. A ``metadata`` event is not
#: queued: the runtime yields it after the producer task has finished, while the
#: Langfuse span is still open.
RuntimeStreamItem: TypeAlias = (
    StreamTokenEvent | StreamToolEvent | RuntimeCompleted | RuntimeFailed
)

#: What the runtime yields to the service: the public frames it produces, plus
#: the internal failure signal, which the service consumes and never forwards.
RuntimeOutput: TypeAlias = (
    StreamTokenEvent | StreamToolEvent | StreamMetadataEvent | RuntimeFailed
)
