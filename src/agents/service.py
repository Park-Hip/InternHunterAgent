import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Literal, Mapping, TypeVar, TypedDict, cast

from src.agents.runtime.react_agent import AgentRuntime
from src.agents.tracing.stream import (
    StreamObservationFactory,
    create_noop_stream_observation,
)
from src.core.config import settings
from src.core.errors import (
    BUSY_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    INTERNAL_ERROR_CODE,
    PROVIDER_BUSY_ERROR_CODE,
    AgentTurnDeadlineExceededError,
    ProviderBusyError,
    classify_provider_busy_error,
)
from src.core.logger import logger

# The sentence a turn whose model wrote nothing shows the reader. It is sent as
# a `token`, not an `error`, so there is no `code` for a client to map from: the
# server owns the copy, and it is Vietnamese like every other user-facing string
# (ADR-0061). The web client mirrors it only to recognise the empty-answer turn.
FALLBACK_ANSWER = "Chưa thể trả lời câu hỏi này - vui lòng thử diễn đạt lại."


_T = TypeVar("_T")

# One stream event as it travels inside the process. The payload is still an
# untyped dict (#679); the union covers what the service and the runtime
# actually put on it: text, flags, counts, and internal-only extras.
StreamEventPayload = Mapping[str, str | bool | int | None]


def _consume_background_task_result(task: asyncio.Future[_T]) -> None:
    """Retrieve a cancelled runtime task's result after detached cleanup."""

    if not task.cancelled():
        task.exception()


def _cancel_and_detach_task(task: asyncio.Future[_T]) -> None:
    """Cancel a runtime task and consume its result without awaiting cleanup."""

    task.cancel()
    task.add_done_callback(_consume_background_task_result)


class AgentResponse(TypedDict):
    answer: str
    session_id: str
    trace_id: str | None
    trace_url: str | None


async def collect_agent_response(
    query: str,
    runtime: AgentRuntime,
    session_id: str | None = None,
    user_id: str | None = None,
    stream_observation_factory: StreamObservationFactory = create_noop_stream_observation,
) -> AgentResponse:
    """Collect one streamed turn into the finished body the JSON route returns.

    `/agent/chat` is no longer a second implementation beside the stream: it
    drives `stream_agent_response` and folds its events back into the response
    body, so the deadline, the empty-answer fallback, the error mapping, and the
    tracing are written once. An in-band `error` event is re-raised as the same
    failure the streamed path reports: a `ProviderBusyError` carrying the status
    the service computed (429 for a rate limit, 503 otherwise), anything else
    as a failure the route maps to its generic 500.
    """
    answer_parts: list[str] = []
    resolved_session_id: str | None = session_id
    trace_id: str | None = None
    trace_url: str | None = None
    error_event: StreamEventPayload | None = None

    events = stream_agent_response(
        query=query,
        runtime=runtime,
        session_id=session_id,
        user_id=user_id,
        stream_observation_factory=stream_observation_factory,
    )
    async for event in events:
        event_type = event["type"]
        if event_type == "session":
            resolved_session_id = cast(str, event["session_id"])
        elif event_type == "token":
            answer_parts.append(cast(str, event["text"]))
        elif event_type == "metadata":
            trace_id = cast(str | None, event["trace_id"])
            trace_url = cast(str | None, event["trace_url"])
        elif event_type == "error":
            # Keep reading to the terminal `done` before raising, so the
            # generator's observation and cleanup finish as a completed turn.
            error_event = event

    if error_event is not None:
        if error_event["code"] == PROVIDER_BUSY_ERROR_CODE:
            raise ProviderBusyError(
                status_code=cast(int, error_event.get("status_code", 503))
            )
        raise RuntimeError(GENERIC_ERROR_MESSAGE)

    if resolved_session_id is None:
        raise RuntimeError("Streamed turn completed without a session id")

    return {
        "answer": "".join(answer_parts),
        "session_id": resolved_session_id,
        "trace_id": trace_id,
        "trace_url": trace_url,
    }


async def stream_agent_response(
    query: str,
    runtime: AgentRuntime,
    session_id: str | None = None,
    user_id: str | None = None,
    stream_observation_factory: StreamObservationFactory = create_noop_stream_observation,
) -> AsyncGenerator[StreamEventPayload, None]:
    session_id = session_id or str(uuid.uuid4())
    observation = stream_observation_factory()
    yield {"type": "session", "session_id": session_id}

    saw_token = False
    metadata_event: StreamEventPayload = {
        "type": "metadata",
        "trace_id": None,
        "trace_url": None,
    }
    metadata_emitted = False

    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.agent.stream_turn_timeout_seconds
    completion_event = asyncio.Event()
    runtime_stream = runtime.astream(
        query=query,
        session_id=session_id,
        user_id=user_id,
        observation=observation,
        completion_event=completion_event,
    )
    runtime_events: asyncio.Queue[dict[str, object] | Exception | None] = asyncio.Queue(
        maxsize=1
    )

    async def consume_runtime_stream() -> None:
        try:
            async for event in runtime_stream:
                await runtime_events.put(event)
        except Exception as exc:
            await runtime_events.put(exc)
        finally:
            try:
                runtime_events.put_nowait(None)
            except asyncio.QueueFull:
                pass

    detach_runtime_task = False
    done_emitted = False
    stream_outcome: Literal["success", "error"] | None = None
    runtime_task = asyncio.create_task(consume_runtime_stream())
    try:
        while True:
            if runtime_task.done() and runtime_events.empty():
                break

            remaining = deadline - loop.time()
            if remaining <= 0:
                _cancel_and_detach_task(runtime_task)
                detach_runtime_task = True
                raise AgentTurnDeadlineExceededError(
                    "Streamed agent turn exceeded its serving deadline."
                )

            try:
                event = await asyncio.wait_for(runtime_events.get(), timeout=remaining)
            except TimeoutError as exc:
                _cancel_and_detach_task(runtime_task)
                detach_runtime_task = True
                raise AgentTurnDeadlineExceededError(
                    "Streamed agent turn exceeded its serving deadline."
                ) from exc

            if event is None:
                break
            if isinstance(event, Exception):
                raise event
            if event["type"] == "runtime_error":
                exception = event["exception"]
                if not isinstance(exception, Exception):
                    raise RuntimeError("Runtime failed without an exception")
                raise exception
            if event["type"] == "metadata":
                metadata_event = cast(StreamEventPayload, event)
                if not saw_token:
                    logger.warning(
                        "stream_agent_response.empty_answer_fallback",
                        session_id=session_id,
                    )
                    observation.mark_user_visible()
                    yield {"type": "token", "text": FALLBACK_ANSWER}
                    saw_token = True
                yield metadata_event
                metadata_emitted = True
                break

            if event["type"] == "token":
                observation.mark_user_visible()
                saw_token = True

            yield cast(StreamEventPayload, event)
        if not saw_token:
            logger.warning(
                "stream_agent_response.empty_answer_fallback",
                session_id=session_id,
            )
            observation.mark_user_visible()
            yield {"type": "token", "text": FALLBACK_ANSWER}

        if not metadata_emitted:
            yield metadata_event
        stream_outcome = "success"
        done_emitted = True
        yield {"type": "done"}
    except AgentTurnDeadlineExceededError as exc:
        stream_outcome = "error"
        logger.error(
            "stream_agent_response.failed",
            session_id=session_id,
            error=str(exc),
            reclassified_busy=False,
            deadline_exceeded=True,
        )
        yield {
            "type": "error",
            "message": BUSY_MESSAGE,
            "code": PROVIDER_BUSY_ERROR_CODE,
            "retryable": True,
            # Internal-only: the HTTP status the collected JSON route returns,
            # read by `collect_agent_response` and stripped by the SSE route
            # (#689). This is not part of the published event contract.
            "status_code": 503,
        }
        done_emitted = True
        yield {"type": "done"}
    except Exception as exc:
        stream_outcome = "error"
        provider_busy = classify_provider_busy_error(exc)
        logger.error(
            "stream_agent_response.failed",
            session_id=session_id,
            error=str(exc),
            reclassified_busy=provider_busy is not None,
            deadline_exceeded=False,
        )
        if provider_busy is not None:
            yield {
                "type": "error",
                "message": BUSY_MESSAGE,
                "code": provider_busy.code,
                "retryable": provider_busy.retryable,
                # Internal-only (#689); see the deadline branch above.
                "status_code": provider_busy.status_code,
            }
        else:
            yield {
                "type": "error",
                "message": GENERIC_ERROR_MESSAGE,
                "code": INTERNAL_ERROR_CODE,
                "retryable": False,
            }
        done_emitted = True
        yield {"type": "done"}
    finally:
        if stream_outcome is not None and done_emitted:
            observation.complete(stream_outcome)
            completion_event.set()
            if not detach_runtime_task:
                await asyncio.gather(runtime_task, return_exceptions=True)
        else:
            observation.complete("cancelled")
            completion_event.set()
            if not detach_runtime_task:
                if not runtime_task.done():
                    runtime_task.cancel()
                await asyncio.gather(runtime_task, return_exceptions=True)
