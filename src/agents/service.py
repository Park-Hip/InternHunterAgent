import uuid
from collections.abc import AsyncIterator
from typing import TypedDict

from src.agents.runtime.react_agent import AgentRuntime
from src.core.errors import BUSY_MESSAGE, GENERIC_ERROR_MESSAGE, classify_provider_busy_error
from src.core.logger import logger

FALLBACK_ANSWER = "I couldn't produce an answer for that — please try rephrasing."


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
) -> AsyncIterator[dict[str, str | None]]:
    session_id = session_id or str(uuid.uuid4())
    yield {"type": "session", "session_id": session_id}

    saw_token = False
    metadata_event = {"type": "metadata", "trace_id": None, "trace_url": None}
    metadata_emitted = False

    try:
        async for event in runtime.astream(
            query=query,
            session_id=session_id,
            user_id=user_id,
        ):
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

        if not saw_token:
            logger.warning(
                "stream_agent_response.empty_answer_fallback",
                session_id=session_id,
            )
            yield {"type": "token", "text": FALLBACK_ANSWER}

        if not metadata_emitted:
            yield metadata_event
    except Exception as exc:
        provider_busy = classify_provider_busy_error(exc)
        logger.error(
            "stream_agent_response.failed",
            session_id=session_id,
            error=str(exc),
            reclassified_busy=provider_busy is not None,
        )
        message = BUSY_MESSAGE if provider_busy is not None else GENERIC_ERROR_MESSAGE
        yield {"type": "error", "message": message}

    yield {"type": "done"}
