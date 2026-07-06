import uuid
from typing import TypedDict

from src.agents.runtime.react_agent import AgentRuntime

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

    response = await runtime.ainvoke(
        query=query,
        session_id=session_id,
        user_id=user_id,
    )

    answer = response["answer"]
    if answer is None or not answer.strip():
        answer = FALLBACK_ANSWER

    return {
        "answer": answer,
        "session_id": session_id,
        "trace_id": response["trace_id"],
        "trace_url": response["trace_url"],
    }
