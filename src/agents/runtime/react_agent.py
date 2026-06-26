from typing import Any

from langchain.messages import HumanMessage

from src.agents.runtime.factory import agent_factory
from src.agents.tracing.langfuse import build_langfuse_config, get_langfuse_client, get_langfuse_handler


class AgentRuntime:
    def __init__(self, agent=None):
        self.agent = agent or agent_factory()

    async def ainvoke(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, str | None]:
        config = build_langfuse_config(session_id=session_id, user_id=user_id)
        if session_id:
            config = {**config, "configurable": {"thread_id": session_id}}
        messages = self._build_messages(query)

        response = await self.agent.ainvoke(messages, config=config or None)
        answer = self._extract_answer(response)

        trace_id = None
        handler = get_langfuse_handler()
        if handler is not None:
            trace_id = handler.last_trace_id

        client = get_langfuse_client()
        if client is not None:
            client.flush()

        return {
            "answer": answer,
            "trace_id": trace_id,
        }

    def _build_messages(self, query: str) -> dict[str, list[HumanMessage]]:
        return {"messages": [HumanMessage(content=query)]}

    def _extract_answer(self, response: Any) -> str:
        if not isinstance(response, dict):
            raise ValueError(f"Unexpected agent response type: {type(response).__name__}")

        messages = response.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("Agent response did not contain any messages")

        last_message = messages[-1]
        content = getattr(last_message, "content", None)

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Agent response did not contain a readable final answer")

        return content.strip()