async def generate_agent_response(query: str, session_id: str | None = None, user_id: str | None = None) -> str:
    return f"Your query is: {query}"