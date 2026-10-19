from __future__ import annotations

import asyncio
import uuid
import unittest
from unittest.mock import ANY, MagicMock, patch

from src.agents.models import (
    InternalStreamError,
    RuntimeFailed,
    StreamMetadataEvent,
    StreamTokenEvent,
)
from src.agents.service import (
    BUSY_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    collect_agent_response,
    stream_agent_response,
)
from src.core.errors import (
    INTERNAL_ERROR_CODE,
    PROVIDER_BUSY_ERROR_CODE,
    ProviderBusyError,
)


class CollectAgentResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_collects_tokens_and_trace_link_from_one_streamed_turn(self) -> None:
        runtime = MagicMock()
        observation = MagicMock()
        observation_factory = MagicMock(return_value=observation)

        async def token_stream(**_kwargs):
            yield StreamTokenEvent(type="token", text="There are ")
            yield StreamTokenEvent(type="token", text="3 roles.")
            yield StreamMetadataEvent(
                type="metadata",
                trace_id="trace-123",
                trace_url="https://cloud.langfuse.com/project/p/traces/trace-123",
            )

        runtime.astream = MagicMock(side_effect=token_stream)

        result = await collect_agent_response(
            query="list 3 data engineer jobs",
            runtime=runtime,
            session_id="session-1",
            user_id="user-1",
            stream_observation_factory=observation_factory,
        )

        self.assertEqual(
            result,
            {
                "answer": "There are 3 roles.",
                "session_id": "session-1",
                "trace_id": "trace-123",
                "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-123",
            },
        )
        runtime.astream.assert_called_once_with(
            query="list 3 data engineer jobs",
            session_id="session-1",
            user_id="user-1",
            observation=observation,
            completion_event=ANY,
        )
        observation.complete.assert_called_once_with("success")

    async def test_generates_session_id_when_omitted(self) -> None:
        async def token_stream(**_kwargs):
            yield StreamTokenEvent(type="token", text="ok")
            yield StreamMetadataEvent(type="metadata", trace_id=None, trace_url=None)

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=token_stream)

        result = await collect_agent_response(query="hi", runtime=runtime)

        # A real UUID is generated and returned so the client can continue
        # the thread; it is also the id handed to the runtime as the thread key.
        returned_id = result["session_id"]
        self.assertEqual(uuid.UUID(returned_id).version, 4)
        runtime.astream.assert_called_once_with(
            query="hi",
            session_id=returned_id,
            user_id=None,
            observation=ANY,
            completion_event=ANY,
        )

    @patch("src.agents.service.logger")
    async def test_empty_answer_fallback_is_logged_once(self, mock_logger) -> None:
        async def empty_stream(**_kwargs):
            if False:  # pragma: no cover - keeps this an async generator
                yield StreamTokenEvent(type="token", text="")

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=empty_stream)

        result = await collect_agent_response(
            query="what time is it?",
            runtime=runtime,
            session_id="session-empty",
        )

        # Literal on purpose: the server owns the user-facing copy (ADR-0061),
        # so a wording change must be a deliberate test edit.
        self.assertEqual(
            result["answer"],
            "Chưa thể trả lời câu hỏi này - vui lòng thử diễn đạt lại.",
        )
        mock_logger.warning.assert_called_once_with(
            "stream_agent_response.empty_answer_fallback",
            session_id="session-empty",
        )

    async def test_rate_limited_provider_event_becomes_a_busy_error_with_429(
        self,
    ) -> None:
        async def rate_limited_stream(**_kwargs):
            raise RuntimeError("provider quota exhausted")
            yield  # pragma: no cover - keeps this an async generator

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=rate_limited_stream)

        with self.assertRaises(ProviderBusyError) as ctx:
            await collect_agent_response(
                query="what time is it?",
                runtime=runtime,
                session_id="session-rate-limited",
            )

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertTrue(ctx.exception.retryable)

    @patch("src.agents.service.settings")
    async def test_deadline_becomes_a_retryable_503(self, mock_settings) -> None:
        mock_settings.agent.stream_turn_timeout_seconds = 0.01

        async def blocked_stream(**_kwargs):
            await asyncio.Event().wait()
            yield  # pragma: no cover - keeps this an async generator

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=blocked_stream)

        with self.assertRaises(ProviderBusyError) as ctx:
            await collect_agent_response(
                query="what time is it?",
                runtime=runtime,
                session_id="session-chat-timeout",
            )

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertTrue(ctx.exception.retryable)

    async def test_internal_error_event_becomes_a_generic_failure(self) -> None:
        async def failing_stream(**_kwargs):
            raise RuntimeError("db is down")
            yield  # pragma: no cover - keeps this an async generator

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=failing_stream)

        with self.assertRaises(RuntimeError) as ctx:
            await collect_agent_response(
                query="what time is it?",
                runtime=runtime,
                session_id="session-internal",
            )

        self.assertEqual(str(ctx.exception), GENERIC_ERROR_MESSAGE)
        self.assertNotIn("db is down", str(ctx.exception))


class StreamAgentResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_marks_ttft_only_when_a_visible_token_is_emitted(
        self,
    ) -> None:
        async def token_stream(**_kwargs):
            yield StreamTokenEvent(type="token", text="Visible answer")
            yield StreamMetadataEvent(type="metadata", trace_id=None, trace_url=None)

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=token_stream)
        observation = MagicMock()
        observation_factory = MagicMock(return_value=observation)
        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-visible-token",
                stream_observation_factory=observation_factory,
            )
        ]

        self.assertEqual(
            [event.type for event in events],
            ["session", "token", "metadata", "done"],
        )
        metadata = next(
            event for event in events if isinstance(event, StreamMetadataEvent)
        )
        self.assertEqual(metadata.answer_source, "model")
        observation_factory.assert_called_once_with()
        observation.mark_user_visible.assert_called_once_with()
        observation.complete.assert_called_once_with("success")
        runtime.astream.assert_called_once_with(
            query="what internships are available?",
            session_id="session-visible-token",
            user_id=None,
            observation=observation,
            completion_event=ANY,
        )

    async def test_error_before_a_visible_token_does_not_mark_ttft(self) -> None:
        async def failing_stream(**_kwargs):
            raise RuntimeError("provider failed")
            yield  # pragma: no cover - keeps this an async generator

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=failing_stream)
        observation = MagicMock()
        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-no-visible-token",
                stream_observation_factory=MagicMock(return_value=observation),
            )
        ]

        self.assertEqual(
            [event.type for event in events], ["session", "error", "done"]
        )
        observation.mark_user_visible.assert_not_called()

    async def test_runtime_error_completes_after_the_error_and_done_events(
        self,
    ) -> None:
        async def failing_stream(*, completion_event, **_kwargs):
            yield RuntimeFailed(RuntimeError("provider failed"))
            await completion_event.wait()

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=failing_stream)
        observation = MagicMock()
        stream = stream_agent_response(
            query="what internships are available?",
            runtime=runtime,
            session_id="session-runtime-error",
            stream_observation_factory=MagicMock(return_value=observation),
        )

        self.assertEqual((await anext(stream)).type, "session")
        self.assertEqual((await anext(stream)).type, "error")
        self.assertEqual((await anext(stream)).type, "done")
        observation.complete.assert_not_called()
        with self.assertRaises(StopAsyncIteration):
            await anext(stream)
        observation.complete.assert_called_once_with("error")

    async def test_disconnect_cleans_up_with_a_buffered_runtime_event(self) -> None:
        second_event_buffered = asyncio.Event()
        runtime_cancelled = asyncio.Event()

        async def buffered_stream(**_kwargs):
            try:
                yield StreamTokenEvent(type="token", text="first")
                yield StreamTokenEvent(type="token", text="second")
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

        self.assertEqual((await anext(stream)).type, "session")
        self.assertEqual((await anext(stream)).text, "first")
        await asyncio.wait_for(second_event_buffered.wait(), timeout=0.1)
        await asyncio.wait_for(stream.aclose(), timeout=0.1)
        self.assertTrue(runtime_cancelled.is_set())

    @patch("src.agents.service.settings")
    @patch("src.agents.service.logger")
    async def test_stream_deadline_cancels_runtime_and_yields_one_safe_error_then_done(
        self, mock_logger, mock_settings
    ) -> None:
        mock_settings.agent.stream_turn_timeout_seconds = 0.01
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
            [event.model_dump() for event in events],
            [
                {"type": "session", "session_id": "session-timeout"},
                {
                    "type": "error",
                    "message": BUSY_MESSAGE,
                    "code": PROVIDER_BUSY_ERROR_CODE,
                    "retryable": True,
                    "status_code": 503,
                },
                {"type": "done"},
            ],
        )
        self.assertTrue(mock_logger.error.call_args.kwargs["deadline_exceeded"])

        async def completed_stream(**_kwargs):
            yield StreamTokenEvent(type="token", text="A subsequent turn succeeds.")
            yield StreamMetadataEvent(type="metadata", trace_id=None, trace_url=None)

        mock_settings.agent.stream_turn_timeout_seconds = 1
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
            [event.type for event in follow_up_events],
            ["session", "token", "metadata", "done"],
        )

        await asyncio.wait_for(cleaned_up.wait(), timeout=0.3)

    @patch("src.agents.service.settings")
    async def test_deadline_completes_as_error_after_done(self, mock_settings) -> None:
        mock_settings.agent.stream_turn_timeout_seconds = 0.01

        async def blocked_stream(**_kwargs):
            await asyncio.Event().wait()
            yield  # pragma: no cover

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=blocked_stream)
        observation = MagicMock()
        stream = stream_agent_response(
            query="what internships are available?",
            runtime=runtime,
            session_id="session-deadline-outcome",
            stream_observation_factory=MagicMock(return_value=observation),
        )

        self.assertEqual((await anext(stream)).type, "session")
        self.assertEqual((await anext(stream)).type, "error")
        self.assertEqual((await anext(stream)).type, "done")
        observation.complete.assert_not_called()
        with self.assertRaises(StopAsyncIteration):
            await anext(stream)
        observation.complete.assert_called_once_with("error")

    @patch("src.agents.service.settings")
    async def test_deadline_between_events_finishes_after_done_with_slow_consumer(
        self, mock_settings
    ) -> None:
        mock_settings.agent.stream_turn_timeout_seconds = 0.05
        third_token_requested = asyncio.Event()
        runtime_cancelled = asyncio.Event()

        async def buffering_stream(**_kwargs):
            try:
                yield StreamTokenEvent(type="token", text="first")
                yield StreamTokenEvent(type="token", text="second")
                third_token_requested.set()
                yield StreamTokenEvent(type="token", text="third")
                await asyncio.Event().wait()
            finally:
                runtime_cancelled.set()

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=buffering_stream)
        observation = MagicMock()
        stream = stream_agent_response(
            query="what internships are available?",
            runtime=runtime,
            session_id="session-deadline-between-events",
            stream_observation_factory=MagicMock(return_value=observation),
        )

        self.assertEqual((await anext(stream)).type, "session")

        # A slow consumer: the service yields the first token and then stalls,
        # so the producer buffers the second event and blocks putting the third
        # into the full size-1 queue.
        self.assertEqual((await anext(stream)).text, "first")
        await asyncio.wait_for(third_token_requested.wait(), timeout=0.1)
        await asyncio.sleep(0.15)  # let the deadline expire while we idle

        self.assertEqual((await anext(stream)).type, "error")
        self.assertEqual((await anext(stream)).type, "done")
        observation.complete.assert_not_called()

        # The finally must not await the runtime task, which is blocked on the
        # full queue, so the generator finishes right after done.
        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), timeout=0.2)
        observation.complete.assert_called_once_with("error")
        await asyncio.wait_for(runtime_cancelled.wait(), timeout=0.1)

    @patch("src.agents.service.logger")
    async def test_stream_failure_logs_and_yields_generic_message(
        self, mock_logger
    ) -> None:
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

        error_events = [e for e in events if isinstance(e, InternalStreamError)]
        self.assertEqual(
            [event.model_dump() for event in error_events],
            [
                {
                    "type": "error",
                    "message": GENERIC_ERROR_MESSAGE,
                    "code": INTERNAL_ERROR_CODE,
                    "retryable": False,
                    "status_code": 500,
                }
            ],
        )
        self.assertNotIn("db is down", str(error_events))
        self.assertEqual(events[-1].model_dump(), {"type": "done"})

        mock_logger.error.assert_called_once()
        self.assertEqual(
            mock_logger.error.call_args.args[0], "stream_agent_response.failed"
        )
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

        error_events = [event for event in events if isinstance(event, InternalStreamError)]
        self.assertEqual(
            [event.model_dump() for event in error_events],
            [
                {
                    "type": "error",
                    "message": BUSY_MESSAGE,
                    "code": PROVIDER_BUSY_ERROR_CODE,
                    "retryable": True,
                    "status_code": 503,
                }
            ],
        )
        self.assertNotIn("Request timed out after 30s", str(error_events))
        self.assertTrue(mock_logger.error.call_args.kwargs["reclassified_busy"])

    @patch("src.agents.service.logger")
    async def test_empty_stream_fallback_is_logged(self, mock_logger) -> None:
        async def empty_stream(**_kwargs):
            if False:  # pragma: no cover - keeps this an async generator
                yield StreamTokenEvent(type="token", text="")

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
            # Literal on purpose: the server owns the user-facing copy
            # (ADR-0061), so a wording change must be a deliberate test edit.
            StreamTokenEvent(
                type="token",
                text="Chưa thể trả lời câu hỏi này - vui lòng thử diễn đạt lại.",
            ),
            events,
        )
        metadata = next(
            event for event in events if isinstance(event, StreamMetadataEvent)
        )
        self.assertEqual(metadata.answer_source, "fallback")
        mock_logger.warning.assert_called_once_with(
            "stream_agent_response.empty_answer_fallback",
            session_id="session-empty-stream",
        )

    @patch("src.agents.service.logger")
    async def test_metadata_marks_the_early_fallback_as_fallback(
        self, _mock_logger
    ) -> None:
        async def metadata_only_stream(**_kwargs):
            yield StreamMetadataEvent(
                type="metadata",
                trace_id="trace-fallback",
                trace_url=None,
            )

        runtime = MagicMock()
        runtime.astream = MagicMock(side_effect=metadata_only_stream)

        events = [
            event
            async for event in stream_agent_response(
                query="what internships are available?",
                runtime=runtime,
                session_id="session-fallback-metadata",
            )
        ]

        fallback_tokens = [
            event.text
            for event in events
            if isinstance(event, StreamTokenEvent)
            and event.text == "Chưa thể trả lời câu hỏi này - vui lòng thử diễn đạt lại."
        ]
        self.assertEqual(len(fallback_tokens), 1)
        metadata = next(
            event for event in events if isinstance(event, StreamMetadataEvent)
        )
        self.assertEqual(metadata.answer_source, "fallback")


if __name__ == "__main__":
    unittest.main()
