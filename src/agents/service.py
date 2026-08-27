import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Mapping, TypeVar, TypedDict

from src.agents.runtime.react_agent import AgentRuntime
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
    yield {"type": "session", "session_id": session_id}

    saw_token = False
    metadata_event = {"type": "metadata", "trace_id": None, "trace_url": None}
    metadata_emitted = False

    loop = asyncio.get_running_loop()
    deadline = loop.time() + get_stream_turn_timeout_seconds(settings.config_yaml)
    runtime_stream = runtime.astream(
        query=query,
        session_id=session_id,
        user_id=user_id,
    )
    detach_runtime_task = False
    next_event: asyncio.Task[dict[str, str | None]] | None = None
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise AgentTurnDeadlineExceededError(
                    "Streamed agent turn exceeded its serving deadline."
                )

            next_event = asyncio.create_task(anext(runtime_stream))
            done, _ = await asyncio.wait({next_event}, timeout=remaining)
            if not done:
                next_event.cancel()
                next_event.add_done_callback(_consume_background_task_result)
                detach_runtime_task = True
                raise AgentTurnDeadlineExceededError(
                    "Streamed agent turn exceeded its serving deadline."
                )

            event = next_event.result()
            if event["type"] == "metadata":
                metadata_event = event
                if not saw_token:
                    logger.warning(
                        "stream_agent_response.empty_answer_fallback",
                        session_id=session_id,
                    )
                    yield {"type": "token", "text": FALLBACK_ANSWER}
                    saw_token = True
                yield metadata_event
                metadata_emitted = True
                continue

            if event["type"] == "token":
                saw_token = True

            yield event
    except StopAsyncIteration:
        if not saw_token:
            logger.warning(
                "stream_agent_response.empty_answer_fallback",
                session_id=session_id,
            )
            yield {"type": "token", "text": FALLBACK_ANSWER}

        if not metadata_emitted:
            yield metadata_event
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
    except Exception as exc:
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
    finally:
        if not detach_runtime_task:
            if next_event is not None and not next_event.done():
                next_event.cancel()
                await asyncio.gather(next_event, return_exceptions=True)
            await runtime_stream.aclose()

    yield {"type": "done"}
