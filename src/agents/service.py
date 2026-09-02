import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Literal, Mapping, TypeVar, TypedDict

from src.agents.runtime.react_agent import AgentRuntime
from src.agents.tracing.langfuse import StreamLatency
from src.core.config import get_stream_turn_timeout_seconds, settings
from src.core.errors import (
    BUSY_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    INTERNAL_ERROR_CODE,
    PROVIDER_BUSY_ERROR_CODE,
    AgentTurnDeadlineExceededError,
    classify_provider_busy_error,
)
from src.core.logger import logger

FALLBACK_ANSWER = "I couldn't produce an answer for that — please try rephrasing."


_T = TypeVar("_T")


def _consume_background_task_result(task: asyncio.Future[_T]) -> None:
    """Retrieve a cancelled runtime task's result after detached cleanup."""

    if not task.cancelled():
        task.exception()


class AgentResponse(TypedDict):
    answer: str
    session_id: str
    trace_id: str | None
    trace_url: str | None


async def generate_agent_response(
    query: str,
    runtime: AgentRuntime,
    session_id: str | None = None,
    user_id: str | None = None,
) -> AgentResponse:
    session_id = session_id or str(uuid.uuid4())

    try:
        response = await runtime.ainvoke(
            query=query,
            session_id=session_id,
            user_id=user_id,
        )
    except Exception as exc:
        provider_busy = classify_provider_busy_error(exc)
        if provider_busy is not None:
            raise provider_busy from exc
        raise

    answer = response["answer"]
    if answer is None or not answer.strip():
        logger.warning(
            "generate_agent_response.empty_answer_fallback",
            session_id=session_id,
            failure_category=response.get("failure_category"),
        )
        answer = FALLBACK_ANSWER

    return {
        "answer": answer,
        "session_id": session_id,
        "trace_id": response["trace_id"],
        "trace_url": response["trace_url"],
    }


async def stream_agent_response(
    query: str,
    runtime: AgentRuntime,
    session_id: str | None = None,
    user_id: str | None = None,
) -> AsyncGenerator[Mapping[str, str | bool | None], None]:
    session_id = session_id or str(uuid.uuid4())
    latency = StreamLatency()
    yield {"type": "session", "session_id": session_id}

    saw_token = False
    metadata_event = {"type": "metadata", "trace_id": None, "trace_url": None}
    metadata_emitted = False

    loop = asyncio.get_running_loop()
    deadline = loop.time() + get_stream_turn_timeout_seconds(settings.config_yaml)
    completion_event = asyncio.Event()
    runtime_stream = runtime.astream(
        query=query,
        session_id=session_id,
        user_id=user_id,
        latency=latency,
        completion_event=completion_event,
    )
    runtime_events: asyncio.Queue[dict[str, object] | Exception | None] = (
        asyncio.Queue(maxsize=1)
    )

    async def consume_runtime_stream() -> None:
        try:
            async for event in runtime_stream:
                await runtime_events.put(event)
        except Exception as exc:
            await runtime_events.put(exc)
        finally:
            await runtime_events.put(None)

    detach_runtime_task = False
    deferred_runtime_cleanup = False
    done_emitted = False
    stream_outcome: Literal["success", "error"] | None = None
    runtime_task = asyncio.create_task(consume_runtime_stream())
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise AgentTurnDeadlineExceededError(
                    "Streamed agent turn exceeded its serving deadline."
                )

            try:
                event = await asyncio.wait_for(runtime_events.get(), timeout=remaining)
            except TimeoutError as exc:
                runtime_task.cancel()
                runtime_task.add_done_callback(_consume_background_task_result)
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
                deferred_runtime_cleanup = True
                raise exception
            if event["type"] == "metadata":
                metadata_event = event
                if not saw_token:
                    logger.warning(
                        "stream_agent_response.empty_answer_fallback",
                        session_id=session_id,
                    )
                    latency.mark_user_visible()
                    yield {"type": "token", "text": FALLBACK_ANSWER}
                    saw_token = True
                yield metadata_event
                metadata_emitted = True
                break

            if event["type"] == "token":
                latency.mark_user_visible()
                saw_token = True

            yield event
        if not saw_token:
            logger.warning(
                "stream_agent_response.empty_answer_fallback",
                session_id=session_id,
            )
            latency.mark_user_visible()
            yield {"type": "token", "text": FALLBACK_ANSWER}

        if not metadata_emitted:
            yield metadata_event
        stream_outcome = "success"
        done_emitted = True
        yield {"type": "done"}
    except AgentTurnDeadlineExceededError as exc:
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
            latency.complete(stream_outcome)
            if stream_outcome == "success" or deferred_runtime_cleanup:
                completion_event.set()
                await asyncio.gather(runtime_task, return_exceptions=True)
        elif not detach_runtime_task:
            if not runtime_task.done():
                runtime_task.cancel()
            await asyncio.gather(runtime_task, return_exceptions=True)
