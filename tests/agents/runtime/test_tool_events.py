"""Tests for the tool observation seam.

These assert the three things that matter and are easy to get wrong:

1. The middleware emits a running event and an ok event around a real call, and
   returns the handler's result untouched.
2. A failing tool still reports, and still propagates unchanged.
3. Arguments are bounded, because they reach the browser.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.agents.runtime.middleware import ToolObservationMiddleware
from src.agents.runtime.tool_events import (
    MAX_ARGUMENT_LENGTH,
    MAX_ARGUMENTS,
    emit_tool_event,
    format_arguments,
)


def _request(name: str, args: dict, call_id: str = "call-1") -> SimpleNamespace:
    return SimpleNamespace(tool_call={"name": name, "args": args, "id": call_id})


class _Collector:
    """Collects emitted events for assertions, simulating a bound emitter."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def __call__(self, payload: dict) -> None:
        self.events.append(payload)


class ToolObservationMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from src.agents.runtime.tool_events import bind_tool_event_emitter

        self.collector = _Collector()
        self.token = bind_tool_event_emitter(self.collector)
        self.addCleanup(
            __import__(
                "src.agents.runtime.tool_events", fromlist=["reset_tool_event_emitter"]
            ).reset_tool_event_emitter,
            self.token,
        )

    async def test_reports_running_then_ok_and_returns_the_result_untouched(self) -> None:
        sentinel = object()
        handler = AsyncMock(return_value=sentinel)
        middleware = ToolObservationMiddleware()

        result = await middleware.awrap_tool_call(
            _request("query_clean_jobs", {"question": "AI Engineer in Da Nang"}),
            handler,
        )

        self.assertIs(result, sentinel, "the tool result must pass through unchanged")
        self.assertEqual([e["status"] for e in self.collector.events], ["running", "ok"])
        self.assertEqual(self.collector.events[0]["name"], "query_clean_jobs")
        self.assertEqual(self.collector.events[0]["type"], "tool")
        self.assertIsNone(self.collector.events[0]["duration_ms"])
        self.assertIsInstance(self.collector.events[1]["duration_ms"], int)
        self.assertEqual(
            self.collector.events[0]["arguments"], {"question": "AI Engineer in Da Nang"}
        )

    async def test_a_failing_tool_reports_then_propagates_unchanged(self) -> None:
        boom = RuntimeError("tool exploded")

        async def handler(_request):
            raise boom

        middleware = ToolObservationMiddleware()
        with self.assertRaises(RuntimeError) as raised:
            await middleware.awrap_tool_call(_request("query_clean_jobs", {}), handler)

        self.assertIs(raised.exception, boom, "the original exception must propagate")
        self.assertEqual([e["status"] for e in self.collector.events], ["running", "error"])
        self.assertIn("tool exploded", self.collector.events[1]["error"])

    async def test_no_emitter_bound_is_a_no_op_not_an_error(self) -> None:
        """Telemetry must never be able to break a turn."""
        from src.agents.runtime.tool_events import (
            bind_tool_event_emitter,
            reset_tool_event_emitter,
        )

        token = bind_tool_event_emitter(None)
        try:
            await emit_tool_event(name="x", status="running")  # must not raise
        finally:
            reset_tool_event_emitter(token)


class FormatArgumentsTests(unittest.TestCase):
    def test_bounds_length_and_count(self) -> None:
        args = {f"k{i}": "x" * 500 for i in range(MAX_ARGUMENTS + 5)}
        formatted = format_arguments(args)
        self.assertEqual(len(formatted), MAX_ARGUMENTS)
        self.assertTrue(
            all(len(v) <= MAX_ARGUMENT_LENGTH for v in formatted.values()),
            "argument values must be truncated before they reach the browser",
        )

    def test_structures_are_collapsed_rather_than_serialised(self) -> None:
        formatted = format_arguments({"filters": {"a": 1}, "ids": [1, 2, 3]})
        self.assertEqual(formatted["filters"], "…")
        self.assertEqual(formatted["ids"], "…")

    def test_non_dict_args_yield_nothing(self) -> None:
        self.assertEqual(format_arguments("not a dict"), {})
        self.assertEqual(format_arguments(None), {})


if __name__ == "__main__":
    unittest.main()