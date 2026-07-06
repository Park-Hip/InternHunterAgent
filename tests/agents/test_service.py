from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from src.agents.service import generate_agent_response


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
        self.assertIsNone(result["trace_url"])
        runtime.ainvoke.assert_awaited_once_with(
            query="what time is it?",
            session_id=result["session_id"],
            user_id=None,
        )


if __name__ == "__main__":
    unittest.main()
