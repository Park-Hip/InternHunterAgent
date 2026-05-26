from src.agents.runtime.react_agent import runtime

async def generate_agent_response(
        query: str,
        session_id: str = None,
        user_id: str = None
    ):
    response = await runtime.ainvoke(
        query=query,
        session_id=session_id,
        user_id=user_id
    )

    return {
        "answer": response["answer"],
        "trace_id": response["trace_id"],
        "trace_url": None
    }