from src.agents.runtime.react_agent import AgentRuntime

_runtime = AgentRuntime()

async def generate_agent_response(
        query: str,
        session_id: str = None,
        user_id: str = None
    ):
    answer = await _runtime.ainvoke(query)

    return {
        "answer": answer,
        "trace_id": None,
        "trace_url": None
    }