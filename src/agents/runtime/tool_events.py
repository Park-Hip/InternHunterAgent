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
from contextvars import ContextVar
from typing import Any

#: Arguments reach the browser. Keep them short, flat, and stringly typed.
MAX_ARGUMENT_LENGTH = 120
MAX_ARGUMENTS = 6

ToolEventEmitter = Callable[[dict[str, Any]], Awaitable[None]]

_current_emitter: ContextVar[ToolEventEmitter | None] = ContextVar(
    "current_tool_event_emitter", default=None
)


def bind_tool_event_emitter(
    emitter: ToolEventEmitter,
) -> "Token[None]":  # noqa: F821 - Token is only used for readability
    """Bind an emitter for the current context. Returns a reset token."""
    return _current_emitter.set(emitter)


def reset_tool_event_emitter(token: Any) -> None:
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


async def emit_tool_event(
    *,
    name: str,
    status: str,
    call_id: str | None = None,
    arguments: dict[str, str] | None = None,
    duration_ms: int | None = None,
    error: str | None = None,
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
        }
    )


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)