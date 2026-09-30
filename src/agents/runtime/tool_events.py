"""Publish tool calls as stream events so the interface can show evidence.

A dataset-bounded agent is judged on whether its claims can be checked. The
runtime already receives everything needed to show what the agent did - the
`messages` stream carries the `tools` node and the model's tool-call requests -
but the public stream carried only `token`, `metadata`, `error`, and `done`. A
reader therefore saw an answer with no visible provenance and no way to tell a
retrieval from a guess.

This module provides the seam. The middleware emits through it; the runtime
binds it to the turn's queue for the duration of that turn only.

A `ContextVar` rather than a constructor argument, because agents are compiled
per request and cached by prompt version: `AgentRuntime._managed_agents` reuses
an agent across turns, so a middleware instance cannot own per-turn state. The
context is copied into the producer task at `create_task`, so a turn's events go
to that turn's queue and never leak into a concurrent one.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

#: Arguments reach the browser. Keep them short, flat, and stringly typed.
MAX_ARGUMENT_LENGTH = 120
MAX_ARGUMENTS = 6

ToolEventEmitter = Callable[[dict[str, Any]], Awaitable[None]]
ToolEventToken = Token["ToolEventEmitter | None"]
ResultFactsToken = Token["ToolResultFacts | None"]

_current_emitter: ContextVar[ToolEventEmitter | None] = ContextVar(
    "current_tool_event_emitter", default=None
)


def bind_tool_event_emitter(emitter: ToolEventEmitter) -> ToolEventToken:
    """Bind an emitter for the current context. Returns a reset token."""
    return _current_emitter.set(emitter)


def reset_tool_event_emitter(token: ToolEventToken) -> None:
    _current_emitter.reset(token)


def format_arguments(args: Any) -> dict[str, str]:
    """Flatten tool arguments to short strings.

    Arguments are reader-derived and are about to be rendered in the browser, so
    they are bounded on both length and count rather than trusted to be small.
    """
    if not isinstance(args, dict):
        return {}
    formatted: dict[str, str] = {}
    for key, value in list(args.items())[:MAX_ARGUMENTS]:
        if value is None or isinstance(value, (dict, list, tuple, set)):
            rendered = "…"
        else:
            rendered = str(value)
        if len(rendered) > MAX_ARGUMENT_LENGTH:
            rendered = rendered[: MAX_ARGUMENT_LENGTH - 1] + "…"
        formatted[str(key)[:40]] = rendered
    return formatted


@dataclass
class ToolResultFacts:
    """Mutable facts about the result of the tool call in progress.

    Deliberately mutable and shared by reference rather than published through a
    `ContextVar`. LangChain may run a tool in a copied context, and a rebinding in
    that copy is invisible to the observer that started the call - which silently
    loses the count. Mutating a shared holder survives context copying, and a fresh
    holder per call keeps consecutive calls isolated without an explicit reset.
    """

    row_count: int | None = None
    truncated: bool = False
    published: bool = False


_last_holder: ContextVar[ToolResultFacts | None] = ContextVar(
    "last_tool_result_holder", default=None
)


def new_result_facts() -> ToolResultFacts:
    return ToolResultFacts()


def set_result_holder(holder: ToolResultFacts) -> ResultFactsToken:
    return _last_holder.set(holder)


def reset_result_holder(token: ResultFactsToken) -> None:
    _last_holder.reset(token)


def publish_tool_result(*, row_count: int | None, truncated: bool = False) -> None:
    """Record result facts for the tool call in progress, if one is observed.

    A tool running outside the observed agent simply publishes nothing, which is
    the correct no-op rather than an error.
    """
    holder = _last_holder.get()
    if holder is None:
        return
    holder.row_count = row_count
    holder.truncated = truncated
    holder.published = True


def published_facts() -> ToolResultFacts | None:
    """The facts a tool published for the call in progress, if any."""
    holder = _last_holder.get()
    return holder if holder is not None and holder.published else None


async def emit_tool_event(
    *,
    name: str,
    status: str,
    call_id: str | None = None,
    arguments: dict[str, str] | None = None,
    duration_ms: int | None = None,
    error: str | None = None,
    facts: "ToolResultFacts | None" = None,
) -> None:
    """Emit one tool lifecycle event, if this context has an emitter bound."""
    emitter = _current_emitter.get()
    if emitter is None:
        return
    await emitter(
        {
            "type": "tool",
            "name": name,
            "status": status,
            "call_id": call_id,
            "arguments": arguments or {},
            "duration_ms": duration_ms,
            "error": error,
            "row_count": facts.row_count if facts else None,
            "truncated": bool(facts.truncated) if facts else False,
        }
    )


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)