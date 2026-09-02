import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from langchain.messages import HumanMessage

from src.agents.runtime.factory import agent_factory
from src.agents.tracing.langfuse import (
    build_langfuse_config,
    get_langfuse_client,
    langfuse_request_trace,
    record_agent_response_failure,
    StreamLatency,
)
from src.core.logger import logger


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
            answer, failure_category = self._extract_answer_with_failure_category(response)
            if failure_category is not None:
                logger.warning(
                    "agent_runtime.response_extraction_failed",
                    failure_category=failure_category,
                )
                record_agent_response_failure(category=failure_category)

        client = get_langfuse_client()
        if client is not None:
            await asyncio.to_thread(client.flush)

        trace_url = None
        if trace_id is not None and client is not None:
            trace_url = client.get_trace_url(trace_id=trace_id)

        result: dict[str, str | None] = {
            "answer": answer,
            "trace_id": trace_id,
            "trace_url": trace_url,
        }
        if failure_category is not None:
            result["failure_category"] = failure_category
        return result

    async def astream(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        latency: StreamLatency | None = None,
        completion_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[dict[str, object], None]:
        config = build_langfuse_config(
            entry_point="api:chat-stream",
        )
        if session_id:
            config = {**config, "configurable": {"thread_id": session_id}}
        messages = self._build_messages(query)

        events: asyncio.Queue[dict[str, str | None] | Exception] = asyncio.Queue(
            maxsize=1
        )

        async def _produce_stream() -> None:
            try:
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
                    await events.put({"type": "token", "text": content})
                await events.put({"type": "complete"})
            except Exception as exc:
                await events.put(exc)

        client = get_langfuse_client()
        async with langfuse_request_trace(
            entry_point="api:chat-stream",
            trace_name="agent-chat-stream",
            session_id=session_id,
            user_id=user_id,
            on_span_started=latency.attach_span if latency is not None else None,
        ) as trace_id:
            producer = asyncio.create_task(_produce_stream())
            stream_completed = False
            provider_failed = False
            try:
                while True:
                    event = await events.get()
                    if isinstance(event, Exception):
                        if completion_event is None:
                            if latency is not None:
                                latency.complete("error")
                            stream_completed = True
                            raise event
                        provider_failed = True
                        yield {"type": "runtime_error", "exception": event}
                        await completion_event.wait()
                        stream_completed = True
                        break
                    if event["type"] == "complete":
                        if completion_event is None:
                            if latency is not None:
                                latency.complete("success")
                            stream_completed = True
                        break
                    yield event

                if completion_event is not None and not provider_failed:
                    trace_url = None
                    if trace_id is not None and client is not None:
                        trace_url = client.get_trace_url(trace_id=trace_id)
                    yield {
                        "type": "metadata",
                        "trace_id": trace_id,
                        "trace_url": trace_url,
                    }
                    await completion_event.wait()
                    stream_completed = True
            finally:
                if not producer.done():
                    producer.cancel()
                if not stream_completed and latency is not None:
                    latency.complete("cancelled")
                await asyncio.gather(producer, return_exceptions=True)
                if client is not None:
                    await asyncio.to_thread(client.flush)

        if completion_event is None:
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
        answer, _ = self._extract_answer_with_failure_category(response)
        return answer

    def _extract_answer_with_failure_category(
        self, response: Any
    ) -> tuple[str, str | None]:
        if not isinstance(response, dict):
            return "", "response_not_dict"

        if "messages" not in response:
            return "", "messages_missing"

        messages = response["messages"]
        if not isinstance(messages, list):
            return "", "messages_not_list"
        if not messages:
            return "", "messages_empty"

        last_message = messages[-1]
        content = getattr(last_message, "content", None)

        if not isinstance(content, str):
            return "", "message_content_not_text"
        if not content.strip():
            return "", "message_content_empty"

        return content.strip(), None
