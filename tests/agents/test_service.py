from __future__ import annotations

import asyncio
import uuid
import unittest
from unittest.mock import ANY, MagicMock, AsyncMock, patch

from src.agents.service import (
    BUSY_MESSAGE,
    FALLBACK_ANSWER,
    GENERIC_ERROR_MESSAGE,
    generate_agent_response,
    get_stream_turn_timeout_seconds,
    stream_agent_response,
)
from src.core.errors import INTERNAL_ERROR_CODE, PROVIDER_BUSY_ERROR_CODE


class GenerateAgentResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_agent_response_uses_injected_runtime(self) -> None:
        runtime = AsyncMock()
        runtime.ainvoke.return_value = {
            "answer": "The current time is 14:01:52.",
            "trace_id": "trace-123",
            "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-123",
        }

        result = await generate_agent_response(
            query="what time is it?",
            runtime=runtime,
            session_id="session-1",
            user_id="user-1",
        )

        runtime.ainvoke.assert_awaited_once_with(
            query="what time is it?",
            session_id="session-1",
            user_id="user-1",
        )
        self.assertEqual(
            result,
            {
                "answer": "The current time is 14:01:52.",
                "session_id": "session-1",
                "trace_id": "trace-123",
                "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-123",
            },
        )

    async def test_generate_agent_response_generates_session_id_when_omitted(self) -> None:
        runtime = AsyncMock()
        runtime.ainvoke.return_value = {
            "answer": "The current time is 14:01:52.",
            "trace_id": "trace-123",
            "trace_url": None,
        }

        result = await generate_agent_response(
            query="what time is it?",
            runtime=runtime,
        )

        self.assertIsNotNone(result["session_id"])
        self.assertEqual(uuid.UUID(result["session_id"]).version, 4)
        self.assertIsNone(result["trace_url"])
        runtime.ainvoke.assert_awaited_once_with(
            query="what time is it?",
            session_id=result["session_id"],
            user_id=None,
        )

    @patch("src.agents.service.logger")
    async def test_empty_answer_fallback_is_logged(self, mock_logger) -> None:
        runtime = AsyncMock()
        runtime.ainvoke.return_value = {
            "answer": "   ",
            "trace_id": None,
            "trace_url": None,
        }

        result = await generate_agent_response(
            query="what time is it?",
            runtime=runtime,
            session_id="session-empty-sync",
        )

        self.assertEqual(result["answer"], FALLBACK_ANSWER)
        mock_logger.warning.assert_called_once_with(
            "generate_agent_response.empty_answer_fallback",
            session_id="session-empty-sync",
            failure_category=None,
        )


class StreamAgentResponseTests(unittest.IsolatedAsyncioTestCase):
    def test_stream_turn_timeout_uses_deterministic_fallback_for_missing_or_invalid_config(self) -> None:
        self.assertEqual(get_stream_turn_timeout_seconds({}), 120)
        for invalid_value in (0, -1, True, "17"):
            with self.subTest(invalid_value=invalid_value):
                self.assertEqual(
                    get_stream_turn_timeout_seconds(
                        {"agent": {"stream_turn_timeout_seconds": invalid_value}}
                    ),
                    120,
                )
        self.assertEqual(
            get_stream_turn_timeout_seconds({"agent": {"stream_turn_timeout_seconds": 17}}),
            17,
        )

    @patch("src.agents.service.StreamLatency")
    async def test_stream_marks_ttft_only_when_a_visible_token_is_emitted(
        self, mock_latency_class
    ) -> None:
        async def token_stream(**_kwargs):
            yield {"type": "token", "text": "Visible answer"}
            yield {"type": "metadata", "trace_id": None, "trace_url": None}

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=token_stream)
        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-visible-token",
            )
        ]

        self.assertEqual([event["type"] for event in events], ["session", "token", "metadata", "done"])
        mock_latency_class.return_value.mark_user_visible.assert_called_once_with()
        mock_latency_class.return_value.complete.assert_called_once_with("success")
        runtime.astream.assert_called_once_with(
            query="what internships are available?",
            session_id="session-visible-token",
            user_id=None,
            latency=mock_latency_class.return_value,
            completion_event=ANY,
        )

    @patch("src.agents.service.StreamLatency")
    async def test_error_before_a_visible_token_does_not_mark_ttft(
        self, mock_latency_class
    ) -> None:
        async def failing_stream(**_kwargs):
            raise RuntimeError("provider failed")
            yield  # pragma: no cover - keeps this an async generator

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=failing_stream)
        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-no-visible-token",
            )
        ]

        self.assertEqual([event["type"] for event in events], ["session", "error", "done"])
        mock_latency_class.return_value.mark_user_visible.assert_not_called()

    @patch("src.agents.service.StreamLatency")
    async def test_runtime_error_completes_after_the_error_and_done_events(
        self, mock_latency_class
    ) -> None:
        async def failing_stream(*, completion_event, **_kwargs):
            yield {"type": "runtime_error", "exception": RuntimeError("provider failed")}
            await completion_event.wait()

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=failing_stream)
        stream = stream_agent_response(
            query="what internships are available?",
            runtime=runtime,
            session_id="session-runtime-error",
        )

        self.assertEqual((await anext(stream))["type"], "session")
        self.assertEqual((await anext(stream))["type"], "error")
        self.assertEqual((await anext(stream))["type"], "done")
        mock_latency_class.return_value.complete.assert_not_called()
        with self.assertRaises(StopAsyncIteration):
            await anext(stream)
        mock_latency_class.return_value.complete.assert_called_once_with("error")

    async def test_disconnect_cleans_up_with_a_buffered_runtime_event(self) -> None:
        second_event_buffered = asyncio.Event()
        runtime_cancelled = asyncio.Event()

        async def buffered_stream(**_kwargs):
            try:
                yield {"type": "token", "text": "first"}
                yield {"type": "token", "text": "second"}
                second_event_buffered.set()
                await asyncio.Event().wait()
            finally:
                runtime_cancelled.set()

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=buffered_stream)
        stream = stream_agent_response(
            query="what internships are available?",
            runtime=runtime,
            session_id="session-buffered-disconnect",
        )

        self.assertEqual((await anext(stream))["type"], "session")
        self.assertEqual((await anext(stream))["text"], "first")
        await asyncio.wait_for(second_event_buffered.wait(), timeout=0.1)
        await asyncio.wait_for(stream.aclose(), timeout=0.1)
        self.assertTrue(runtime_cancelled.is_set())

    @patch("src.agents.service.get_stream_turn_timeout_seconds", return_value=0.01)
    @patch("src.agents.service.logger")
    async def test_stream_deadline_cancels_runtime_and_yields_one_safe_error_then_done(
        self, mock_logger, _mock_timeout
    ) -> None:
        cancellation_received = asyncio.Event()
        cleaned_up = asyncio.Event()

        async def blocked_stream(**_kwargs):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancellation_received.set()
                await asyncio.sleep(0.2)
                raise
            finally:
                cleaned_up.set()
            yield  # pragma: no cover - keeps this an async generator

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=blocked_stream)

        started_at = asyncio.get_running_loop().time()
        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-timeout",
            )
        ]

        self.assertLess(asyncio.get_running_loop().time() - started_at, 0.1)
        await asyncio.wait_for(cancellation_received.wait(), timeout=0.1)
        self.assertFalse(cleaned_up.is_set())
        self.assertEqual(
            events,
            [
                {"type": "session", "session_id": "session-timeout"},
                {
                    "type": "error",
                    "message": BUSY_MESSAGE,
                    "code": PROVIDER_BUSY_ERROR_CODE,
                    "retryable": True,
                },
                {"type": "done"},
            ],
        )
        self.assertTrue(mock_logger.error.call_args.kwargs["deadline_exceeded"])

        async def completed_stream(**_kwargs):
            yield {"type": "token", "text": "A subsequent turn succeeds."}
            yield {"type": "metadata", "trace_id": None, "trace_url": None}

        _mock_timeout.return_value = 1
        runtime.astream = MagicMock(side_effect=completed_stream)
        follow_up_events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-after-timeout",
            )
        ]

        self.assertEqual(
            [event["type"] for event in follow_up_events],
            ["session", "token", "metadata", "done"],
        )

        await asyncio.wait_for(cleaned_up.wait(), timeout=0.3)

    @patch("src.agents.service.get_stream_turn_timeout_seconds", return_value=0.01)
    @patch("src.agents.service.StreamLatency")
    async def test_deadline_completes_as_error_after_done(
        self, mock_latency_class, _mock_timeout
    ) -> None:
        async def blocked_stream(**_kwargs):
            await asyncio.Event().wait()
            yield  # pragma: no cover

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=blocked_stream)
        stream = stream_agent_response(
            query="what internships are available?",
            runtime=runtime,
            session_id="session-deadline-outcome",
        )

        self.assertEqual((await anext(stream))["type"], "session")
        self.assertEqual((await anext(stream))["type"], "error")
        self.assertEqual((await anext(stream))["type"], "done")
        mock_latency_class.return_value.complete.assert_not_called()
        with self.assertRaises(StopAsyncIteration):
            await anext(stream)
        mock_latency_class.return_value.complete.assert_called_once_with("error")

    @patch("src.agents.service.logger")
    async def test_stream_failure_logs_and_yields_generic_message(self, mock_logger) -> None:
        async def failing_stream(**_kwargs):
            raise RuntimeError("db is down")
            yield  # pragma: no cover — makes this an async generator

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=failing_stream)

        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-1",
            )
        ]

        error_events = [e for e in events if e["type"] == "error"]
        self.assertEqual(
            error_events,
            [
                {
                    "type": "error",
                    "message": GENERIC_ERROR_MESSAGE,
                    "code": INTERNAL_ERROR_CODE,
                    "retryable": False,
                }
            ],
        )
        self.assertNotIn("db is down", str(error_events))
        self.assertEqual(events[-1], {"type": "done"})

        mock_logger.error.assert_called_once()
        self.assertEqual(mock_logger.error.call_args.args[0], "stream_agent_response.failed")
        kwargs = mock_logger.error.call_args.kwargs
        self.assertEqual(kwargs["session_id"], "session-1")
        self.assertIn("db is down", kwargs["error"])
        self.assertFalse(kwargs["reclassified_busy"])
        self.assertFalse(kwargs["deadline_exceeded"])

    @patch("src.agents.service.logger")
    async def test_stream_failure_records_reclassified_busy(self, mock_logger) -> None:
        async def failing_stream(**_kwargs):
            raise RuntimeError("Request timed out after 30s")
            yield  # pragma: no cover — makes this an async generator

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=failing_stream)

        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-2",
            )
        ]

        error_events = [event for event in events if event["type"] == "error"]
        self.assertEqual(
            error_events,
            [
                {
                    "type": "error",
                    "message": BUSY_MESSAGE,
                    "code": PROVIDER_BUSY_ERROR_CODE,
                    "retryable": True,
                }
            ],
        )
        self.assertNotIn("Request timed out after 30s", str(error_events))
        self.assertTrue(mock_logger.error.call_args.kwargs["reclassified_busy"])

    @patch("src.agents.service.logger")
    async def test_empty_stream_fallback_is_logged(self, mock_logger) -> None:
        async def empty_stream(**_kwargs):
            if False:  # pragma: no cover - keeps this an async generator
                yield {}

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=empty_stream)

        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-empty-stream",
            )
        ]

        self.assertIn(
            {"type": "token", "text": FALLBACK_ANSWER},
            events,
        )
        mock_logger.warning.assert_called_once_with(
            "stream_agent_response.empty_answer_fallback",
            session_id="session-empty-stream",
        )


if __name__ == "__main__":
    unittest.main()
