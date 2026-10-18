from __future__ import annotations

import time

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Overwrite

from src.agents.runtime.tool_events import (
    elapsed_ms,
    emit_tool_event,
    format_arguments,
    new_result_facts,
    published_facts,
    reset_result_holder,
    set_result_holder,
)


class TrimTurnsMiddleware(AgentMiddleware):
    """Trim the per-turn model input to the most recent complete user turns.

    A turn begins with a human message and includes every later message up to the next
    human message. Only the inbound model request is trimmed, leaving stored checkpoint
    history untouched. Both sync and async hooks are implemented so the trim applies
    however the agent is driven.
    """

    def __init__(self, max_turns: int) -> None:
        super().__init__()
        self._max_turns = max_turns

    def _trim(self, request: ModelRequest) -> ModelRequest:
        turn_starts = [
            index
            for index, message in enumerate(request.messages)
            if isinstance(message, HumanMessage)
        ]
        if len(turn_starts) <= self._max_turns:
            return request

        retained_start = turn_starts[-self._max_turns]
        return request.override(messages=request.messages[retained_start:])

    def wrap_model_call(self, request, handler):
        return handler(self._trim(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._trim(request))


def build_trim_middleware(max_turns: int) -> AgentMiddleware:
    return TrimTurnsMiddleware(max_turns)


INTERRUPTED_TOOL_CALL_CONTENT = (
    "The tool call was interrupted before it returned a result, so no result "
    "is available. Retry the call if its result is still needed."
)


class InterruptedToolCallRepairMiddleware(AgentMiddleware):
    """Answer dangling tool calls before a model call, so a thread stays valid.

    A turn can be cancelled or die between the model asking for a tool and the
    tool answering: the Dừng button, a client disconnect, the turn deadline, or
    a worker crash. LangGraph checkpoints that half-finished step, and a
    provider rejects the replay, because an assistant ``tool_calls`` id with no
    matching tool message is an invalid sequence. This middleware inserts one
    synthetic error ``ToolMessage`` per unanswered id, directly after the call
    that made it, before each model call. The model can then retry the call or
    move on from a valid sequence.

    The repaired list replaces the ``messages`` channel (``Overwrite``) because
    that channel only appends, and a repair must land directly after the call
    it answers. The middleware is stateless, as the compiled agent is shared
    across turns, and a healthy thread produces no update at all.
    """

    def before_model(self, state, runtime):
        return self._repair(state)

    async def abefore_model(self, state, runtime):
        return self._repair(state)

    def _repair(self, state):
        messages = state.get("messages") or []
        answered_ids = {
            message.tool_call_id
            for message in messages
            if isinstance(message, ToolMessage)
        }
        repaired: list = []
        inserted = False
        for message in messages:
            repaired.append(message)
            if not isinstance(message, AIMessage):
                continue
            for call in message.tool_calls:
                call_id = call.get("id")
                if not call_id or call_id in answered_ids:
                    continue
                repaired.append(
                    ToolMessage(
                        content=INTERRUPTED_TOOL_CALL_CONTENT,
                        tool_call_id=call_id,
                        name=call.get("name"),
                        status="error",
                    )
                )
                answered_ids.add(call_id)
                inserted = True
        if not inserted:
            return None
        return {"messages": Overwrite(repaired)}


def build_interrupted_tool_call_repair_middleware() -> AgentMiddleware:
    return InterruptedToolCallRepairMiddleware()


class ToolObservationMiddleware(AgentMiddleware):
    """Announce tool calls so the interface can show what the agent did.

    This observes and reports. It never alters the call, the arguments, the
    result, or the control flow: a failure here degrades to no telemetry rather
    than to a failed turn, because an interface that reports on the agent must
    not be able to break it. The per-call result holder is released in a
    `finally`, so a tool that raises leaves nothing bound behind it.
    """

    async def awrap_tool_call(self, request, handler):
        call = getattr(request, "tool_call", None) or {}
        name = str(call.get("name") or "tool")
        call_id = call.get("id")
        arguments = format_arguments(call.get("args"))

        await emit_tool_event(
            name=name, status="running", call_id=call_id, arguments=arguments
        )
        started = time.perf_counter()
        # A fresh holder per call, shared by reference so the count survives
        # however LangChain chooses to schedule the tool.
        holder = new_result_facts()
        holder_token = set_result_holder(holder)
        try:
            result = await handler(request)
        except Exception as error:
            # Report the failure, then let it propagate unchanged.
            await emit_tool_event(
                name=name,
                status="error",
                call_id=call_id,
                arguments=arguments,
                duration_ms=elapsed_ms(started),
                error=str(error)[:200],
            )
            raise
        else:
            # Fold in whatever the tool published about its own result, so one
            # event carries both the call and the count.
            facts = published_facts()
            await emit_tool_event(
                name=name,
                status="ok",
                call_id=call_id,
                arguments=arguments,
                duration_ms=elapsed_ms(started),
                facts=facts,
            )
            return result
        finally:
            # Success and failure alike: the next call gets its own holder.
            reset_result_holder(holder_token)


def build_tool_observation_middleware() -> AgentMiddleware:
    return ToolObservationMiddleware()
