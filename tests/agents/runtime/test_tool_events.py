"""Tests for the tool observation seam.

These assert the three things that matter and are easy to get wrong:

1. The middleware emits a running event and an ok event around a real call, and
   returns the handler's result untouched.
2. A failing tool still reports, and still propagates unchanged.
3. A failure that arrives as an error-status tool message reports an error with
   no detail, and no result facts (#702).
4. Arguments are bounded, because they reach the browser.
5. A failed call leaves no result holder bound behind it.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langchain_core.messages import ToolMessage

from src.agents.models import StreamToolEvent
from src.agents.runtime.middleware import ToolObservationMiddleware
from src.agents.runtime.tool_events import (
    MAX_ARGUMENT_LENGTH,
    MAX_ARGUMENTS,
    emit_tool_event,
    format_arguments,
    publish_tool_result,
    published_facts,
)


def _request(name: str, args: dict, call_id: str = "call-1") -> SimpleNamespace:
    return SimpleNamespace(tool_call={"name": name, "args": args, "id": call_id})


class _Collector:
    """Collects emitted events for assertions, simulating a bound emitter."""

    def __init__(self) -> None:
        self.events: list[StreamToolEvent] = []

    async def __call__(self, payload: StreamToolEvent) -> None:
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
            _request("query_clean_jobs", {"request": "AI Engineer in Da Nang"}),
            handler,
        )

        self.assertIs(result, sentinel, "the tool result must pass through unchanged")
        self.assertEqual([e.status for e in self.collector.events], ["running", "ok"])
        self.assertEqual(self.collector.events[0].name, "query_clean_jobs")
        self.assertEqual(self.collector.events[0].type, "tool")
        self.assertIsNone(self.collector.events[0].duration_ms)
        self.assertIsInstance(self.collector.events[1].duration_ms, int)
        self.assertEqual(
            self.collector.events[0].arguments, {"request": "AI Engineer in Da Nang"}
        )

    async def test_a_failing_tool_reports_then_propagates_unchanged(self) -> None:
        boom = RuntimeError("tool exploded")

        async def handler(_request):
            raise boom

        middleware = ToolObservationMiddleware()
        with self.assertRaises(RuntimeError) as raised:
            await middleware.awrap_tool_call(_request("query_clean_jobs", {}), handler)

        self.assertIs(raised.exception, boom, "the original exception must propagate")
        self.assertEqual(
            [e.status for e in self.collector.events], ["running", "error"]
        )
        error = self.collector.events[1].error
        self.assertIsNotNone(error, "the failing call must report why it failed")
        self.assertIn("tool exploded", error)

    async def test_an_error_status_tool_message_reports_an_error_with_no_detail(
        self,
    ) -> None:
        """The MCP boundary delivers a tool failure as an error-status message.

        The model reads the kind and the detail inside the message; the card
        shows the server-owned Vietnamese copy instead, so the event carries no
        error text and folds in no result facts (#702).
        """
        failure_message = ToolMessage(
            content='unknown_column: column "remote" does not exist',
            tool_call_id="call-1",
            name="query_clean_jobs",
            status="error",
        )

        async def handler(_request):
            # A behavior that published before failing must not leak its facts
            # into an error event.
            publish_tool_result(row_count=3)
            return failure_message

        returned = await ToolObservationMiddleware().awrap_tool_call(
            _request("query_clean_jobs", {"request": "what does remote hold?"}), handler
        )

        self.assertIs(returned, failure_message, "the message must pass through")
        self.assertEqual(
            [e.status for e in self.collector.events], ["running", "error"]
        )
        error_event = self.collector.events[1]
        self.assertIsNone(
            error_event.error,
            "the card owns the error copy, so the event carries no detail",
        )
        self.assertIsNone(error_event.row_count)
        self.assertFalse(error_event.truncated)
        self.assertIsNone(error_event.page_offset)
        self.assertIsNone(error_event.rows_returned)

    async def test_result_facts_carry_the_page_bounds(self) -> None:
        """The card needs the page start and the shown-row count to tell an
        empty later page from a search that matched nothing (#726)."""

        async def handler(_request):
            publish_tool_result(
                row_count=161,
                truncated=True,
                page_offset=200,
                rows_returned=0,
            )
            return object()

        await ToolObservationMiddleware().awrap_tool_call(
            _request("query_clean_jobs", {"request": "the page after the end"}),
            handler,
        )

        ok_event = self.collector.events[1]
        self.assertEqual(ok_event.status, "ok")
        self.assertEqual(ok_event.row_count, 161)
        self.assertTrue(ok_event.truncated)
        self.assertEqual(ok_event.page_offset, 200)
        self.assertEqual(ok_event.rows_returned, 0)

    async def test_a_failing_tool_leaves_no_result_holder_bound(self) -> None:
        """A released holder, so nothing later in this context reads stale facts."""

        async def handler(_request):
            raise RuntimeError("tool exploded")

        middleware = ToolObservationMiddleware()
        with self.assertRaises(RuntimeError):
            await middleware.awrap_tool_call(_request("query_clean_jobs", {}), handler)

        # With a leaked binding this publish would land in the failed call's
        # holder and be readable here.
        publish_tool_result(row_count=5)
        self.assertIsNone(
            published_facts(),
            "a failed call must not leave its result holder bound",
        )

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