from __future__ import annotations

import time

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    SummarizationMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from src.agents.runtime.tool_events import (
    elapsed_ms,
    emit_tool_event,
    format_arguments,
    new_result_facts,
    published_facts,
    reset_result_holder,
    set_result_holder,
)
from src.core.config import settings


def _load_positive_memory_value(value: object, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(
            f"agent.memory.compaction.{key} must be a positive integer "
            "in config/settings.yaml"
        )

    return value


def load_max_turns() -> int:
    agent_cfg = settings.config_yaml.get("agent")
    if not isinstance(agent_cfg, dict):
        raise ValueError("Missing 'agent' section in config/settings.yaml")

    memory_cfg = agent_cfg.get("memory")
    if not isinstance(memory_cfg, dict):
        raise ValueError("Missing 'agent.memory' section in config/settings.yaml")

    max_turns = memory_cfg.get("max_turns")
    if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns <= 0:
        raise ValueError(
            "agent.memory.max_turns must be a positive integer in config/settings.yaml"
        )

    return max_turns


def load_compaction_message_limits() -> tuple[int, int]:
    agent_cfg = settings.config_yaml.get("agent")
    if not isinstance(agent_cfg, dict):
        raise ValueError("Missing 'agent' section in config/settings.yaml")

    memory_cfg = agent_cfg.get("memory")
    if not isinstance(memory_cfg, dict):
        raise ValueError("Missing 'agent.memory' section in config/settings.yaml")

    compaction_cfg = memory_cfg.get("compaction")
    if not isinstance(compaction_cfg, dict):
        raise ValueError(
            "Missing 'agent.memory.compaction' section in config/settings.yaml"
        )

    trigger_messages = _load_positive_memory_value(
        compaction_cfg.get("trigger_messages"), "trigger_messages"
    )
    keep_messages = _load_positive_memory_value(
        compaction_cfg.get("keep_messages"), "keep_messages"
    )

    if keep_messages >= trigger_messages:
        raise ValueError(
            "agent.memory.compaction.keep_messages must be smaller than "
            "agent.memory.compaction.trigger_messages in config/settings.yaml"
        )

    return trigger_messages, keep_messages


class TrimTurnsMiddleware(AgentMiddleware):
    """Trim the per-turn model input to the most recent complete user turns.

    A turn begins with a human message and includes every later message up to the next
    human message. Only the inbound model request is trimmed, leaving stored checkpoint
    history untouched. Both sync and async hooks are implemented because the runtime
    drives the agent through ``ainvoke``.
    """

    def __init__(self, max_turns: int) -> None:
        super().__init__()
        self._max_turns = max_turns

    def _trim(self, request: ModelRequest) -> ModelRequest:
        turn_starts = [
            index
            for index, message in enumerate(request.messages)
            if isinstance(message, HumanMessage)
            and message.additional_kwargs.get("lc_source") != "summarization"
        ]
        if len(turn_starts) <= self._max_turns:
            return request

        retained_start = turn_starts[-self._max_turns]
        summaries = [
            message
            for message in request.messages[:retained_start]
            if isinstance(message, HumanMessage)
            and message.additional_kwargs.get("lc_source") == "summarization"
        ]
        return request.override(
            messages=[*summaries, *request.messages[retained_start:]]
        )

    def wrap_model_call(self, request, handler):
        return handler(self._trim(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._trim(request))


def build_trim_middleware(max_turns: int) -> AgentMiddleware:
    return TrimTurnsMiddleware(max_turns)


def build_compaction_middleware(
    model: BaseChatModel, trigger_messages: int, keep_messages: int
) -> AgentMiddleware:
    """Compact persisted state before it grows beyond the configured message limit."""
    return SummarizationMiddleware(
        model=model,
        trigger=("messages", trigger_messages),
        keep=("messages", keep_messages),
    )


class ToolObservationMiddleware(AgentMiddleware):
    """Announce tool calls so the interface can show what the agent did.

    This observes and reports. It never alters the call, the arguments, the
    result, or the control flow: a failure here degrades to no telemetry rather
    than to a failed turn, because an interface that reports on the agent must
    not be able to break it.
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
        # Fold in whatever the tool published about its own result, so one event
        # carries both the call and the count.
        facts = published_facts()
        await emit_tool_event(
            name=name,
            status="ok",
            call_id=call_id,
            arguments=arguments,
            duration_ms=elapsed_ms(started),
            facts=facts,
        )
        reset_result_holder(holder_token)
        return result


def build_tool_observation_middleware() -> AgentMiddleware:
    return ToolObservationMiddleware()
