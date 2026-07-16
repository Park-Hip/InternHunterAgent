import asyncio
from collections.abc import AsyncIterator
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
            await asyncio.to_thread(client.flush)

        trace_url = None
        if trace_id is not None and client is not None:
            trace_url = client.get_trace_url(trace_id=trace_id)

        return {
            "answer": answer,
            "trace_id": trace_id,
            "trace_url": trace_url,
        }

    async def astream(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[dict[str, str | None]]:
        config = build_langfuse_config(session_id=session_id, user_id=user_id)
        if session_id:
            config = {**config, "configurable": {"thread_id": session_id}}
        messages = self._build_messages(query)

        async for chunk, metadata in self.agent.astream(
            messages,
            config=config or None,
            stream_mode="messages",
        ):
            if metadata.get("langgraph_node") != "model":
                continue
            content = getattr(chunk, "content", None)
            tool_call_chunks = getattr(chunk, "tool_call_chunks", None)
            if not isinstance(content, str) or not content or tool_call_chunks:
                continue
            yield {"type": "token", "text": content}

        trace_id = None
        handler = get_langfuse_handler()
        if handler is not None:
            trace_id = handler.last_trace_id

        client = get_langfuse_client()
        if client is not None:
            await asyncio.to_thread(client.flush)

        trace_url = None
        if trace_id is not None and client is not None:
            trace_url = client.get_trace_url(trace_id=trace_id)

        yield {
            "type": "metadata",
            "trace_id": trace_id,
            "trace_url": trace_url,
        }

    def _build_messages(self, query: str) -> dict[str, list[HumanMessage]]:
        return {"messages": [HumanMessage(content=query)]}

    def _extract_answer(self, response: Any) -> str:
        if not isinstance(response, dict):
            return ""

        messages = response.get("messages")
        if not isinstance(messages, list) or not messages:
            return ""

        last_message = messages[-1]
        content = getattr(last_message, "content", None)

        if not isinstance(content, str) or not content.strip():
            return ""

        return content.strip()
