from __future__ import annotations

import uuid
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from src.agents.service import (
    BUSY_MESSAGE,
    FALLBACK_ANSWER,
    GENERIC_ERROR_MESSAGE,
    generate_agent_response,
    stream_agent_response,
)


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
        self.assertEqual(error_events, [{"type": "error", "message": GENERIC_ERROR_MESSAGE}])
        self.assertEqual(events[-1], {"type": "done"})

        mock_logger.error.assert_called_once()
        self.assertEqual(mock_logger.error.call_args.args[0], "stream_agent_response.failed")
        kwargs = mock_logger.error.call_args.kwargs
        self.assertEqual(kwargs["session_id"], "session-1")
        self.assertIn("db is down", kwargs["error"])
        self.assertFalse(kwargs["reclassified_busy"])

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
        self.assertEqual(error_events, [{"type": "error", "message": BUSY_MESSAGE}])
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
