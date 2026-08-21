import asyncio
from collections.abc import AsyncIterator
from typing import Any

from langchain.messages import HumanMessage

from src.agents.runtime.factory import agent_factory
from src.agents.tracing.langfuse import (
    build_langfuse_config,
    get_langfuse_client,
    langfuse_request_trace,
)


class AgentRuntime:
    def __init__(self, agent=None):
        self.agent = agent or agent_factory()

    async def ainvoke(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, str | None]:
        config = build_langfuse_config(
            entry_point="api:chat",
        )
        if session_id:
            config = {**config, "configurable": {"thread_id": session_id}}
        messages = self._build_messages(query)

        async with langfuse_request_trace(
            entry_point="api:chat",
            trace_name="agent-chat",
            session_id=session_id,
            user_id=user_id,
        ) as trace_id:
            response = await self.agent.ainvoke(messages, config=config or None)
        answer = self._extract_answer(response)

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
        config = build_langfuse_config(
            entry_point="api:chat-stream",
        )
        if session_id:
            config = {**config, "configurable": {"thread_id": session_id}}
        messages = self._build_messages(query)

        trace_id: str | None = None
        events: asyncio.Queue[dict[str, str | None] | Exception] = asyncio.Queue(
            maxsize=1
        )

        async def _produce_stream() -> None:
            try:
                async with langfuse_request_trace(
                    entry_point="api:chat-stream",
                    trace_name="agent-chat-stream",
                    session_id=session_id,
                    user_id=user_id,
                ) as trace_id:
                    async for chunk, metadata in self.agent.astream(
                        messages,
                        config=config or None,
                        stream_mode="messages",
                    ):
                        if metadata.get("langgraph_node") != "model":
                            continue
                        content = getattr(chunk, "content", None)
                        tool_call_chunks = getattr(chunk, "tool_call_chunks", None)
                        if (
                            not isinstance(content, str)
                            or not content
                            or tool_call_chunks
                        ):
                            continue
                        await events.put({"type": "token", "text": content})
                await events.put({"type": "complete", "trace_id": trace_id})
            except Exception as exc:
                await events.put(exc)

        producer = asyncio.create_task(_produce_stream())
        try:
            while True:
                event = await events.get()
                if isinstance(event, Exception):
                    raise event
                if event["type"] == "complete":
                    trace_id = event["trace_id"]
                    break
                yield event
        finally:
            if not producer.done():
                producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)

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
