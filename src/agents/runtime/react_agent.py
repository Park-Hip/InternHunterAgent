import asyncio
from collections.abc import AsyncGenerator
from typing import Any, cast

from langchain.messages import HumanMessage, SystemMessage

from src.agents.runtime.factory import agent_factory as default_agent_factory
from src.agents.runtime.prompts import (
    ResolvedPrompt,
    ResolvedPromptBundle,
    prompt_bundle_context,
    resolve_prompt_bundle_async,
)
from src.agents.tracing.langfuse import (
    build_langfuse_config,
    langfuse_prompt_attributes,
    langfuse_request_trace,
    langfuse_trace_url,
)
from src.agents.tracing.stream import StreamObservation
from src.agents.runtime.tool_events import (
    bind_tool_event_emitter,
    reset_tool_event_emitter,
)


class AgentRuntime:
    def __init__(self, agent_factory=None, checkpointer=None, tools=None):
        self._checkpointer = checkpointer
        self._tools = tools
        self._agent_factory = agent_factory or default_agent_factory
        self._managed_agents: dict[tuple[str, str], Any] = {}

    async def _active_agent(
        self, prompts: ResolvedPromptBundle
    ) -> tuple[Any, ResolvedPrompt]:
        """Return the agent compiled for this request's immutable system prompt."""
        prompt = prompts.system
        key = (prompt.version, prompt.content)
        agent = self._managed_agents.get(key)
        if agent is None:
            agent = await self._agent_factory(
                checkpointer=self._checkpointer,
                system_prompt=SystemMessage(content=prompt.content),
                tools=self._tools,
            )
            self._managed_agents[key] = agent
        return agent, prompt

    async def astream(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        observation: StreamObservation | None = None,
        *,
        completion_event: asyncio.Event,
    ) -> AsyncGenerator[dict[str, object], None]:
        """Stream the answer, keeping the trace span open until the service is done.

        The service owns the turn's end: it completes the observation, sends
        `done`, and only then sets `completion_event`, which is what keeps the
        span covering the whole stream.
        """
        config = build_langfuse_config(
            entry_point="api:chat-stream",
        )
        if session_id:
            config = {**config, "configurable": {"thread_id": session_id}}
        prompts = await resolve_prompt_bundle_async()
        agent, system_prompt = await self._active_agent(prompts)

        events: asyncio.Queue[dict[str, object] | Exception] = asyncio.Queue(
            maxsize=1
        )

        # Tool events are published straight into this turn's queue by the
        # observation middleware, so they interleave with tokens in real time
        # rather than arriving after the answer. The binding is per turn: the
        # context is copied into the producer task, so a concurrent turn cannot
        # receive this turn's tool events.
        emitter_token = bind_tool_event_emitter(events.put)

        async def _produce_stream() -> None:
            try:
                async for chunk, metadata in agent.astream(
                    {"messages": [HumanMessage(content=query)]},
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

        async with langfuse_request_trace(
            entry_point="api:chat-stream",
            trace_name="agent-chat-stream",
            session_id=session_id,
            user_id=user_id,
            on_span_started=observation.attach_trace
            if observation is not None
            else None,
            prompts=prompts,
        ) as trace_id:
            with prompt_bundle_context(prompts):
                with langfuse_prompt_attributes(system_prompt):
                    producer = asyncio.create_task(_produce_stream())
            stream_completed = False
            provider_failed = False
            try:
                while True:
                    event = await events.get()
                    if isinstance(event, Exception):
                        # A provider failure is reported as an event, not
                        # raised: the service classifies it and owns the error
                        # payload, and the span stays open until it has sent
                        # `done`.
                        provider_failed = True
                        yield {"type": "runtime_error", "exception": event}
                        await completion_event.wait()
                        stream_completed = True
                        break
                    if event["type"] == "complete":
                        break
                    yield cast(dict[str, object], event)

                if not provider_failed:
                    yield {
                        "type": "metadata",
                        "trace_id": trace_id,
                        "trace_url": langfuse_trace_url(trace_id=trace_id),
                    }
                    await completion_event.wait()
                    stream_completed = True
            finally:
                reset_tool_event_emitter(emitter_token)
                if not producer.done():
                    producer.cancel()
                await asyncio.gather(producer, return_exceptions=True)
                if not stream_completed:
                    await completion_event.wait()

