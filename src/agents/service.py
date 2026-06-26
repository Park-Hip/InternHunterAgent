import uuid

from src.agents.runtime.react_agent import AgentRuntime


async def generate_agent_response(
    query: str,
    runtime: AgentRuntime,
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, str | None]:
    session_id = session_id or str(uuid.uuid4())

    response = await runtime.ainvoke(
        query=query,
        session_id=session_id,
        user_id=user_id,
    )

    return {
        "answer": response["answer"],
        "session_id": session_id,
        "trace_id": response["trace_id"],
        "trace_url": None,
    }