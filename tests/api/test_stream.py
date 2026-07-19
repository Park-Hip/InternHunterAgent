from __future__ import annotations

import json
import uuid
import unittest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.agents.service import FALLBACK_ANSWER
from src.api.app import create_app
from src.core.errors import BUSY_MESSAGE


def _parse_sse_events(body: str) -> list[tuple[str, dict[str, str | None]]]:
    events: list[tuple[str, dict[str, str | None]]] = []
    for block in body.strip().split("\n\n"):
        event_type = None
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ")
            if line.startswith("data: "):
                data = line.removeprefix("data: ")
        if event_type is not None:
            events.append((event_type, json.loads(data)))
    return events


class StreamQueryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(rate_limit="1000/minute", docs_enabled=False)
        self.app.state.runtime = AsyncMock()
        self.client = TestClient(self.app)

    def test_stream_route_returns_session_tokens_metadata_and_done(self) -> None:
        async def _fake_astream(**kwargs):
            yield {"type": "token", "text": "There are "}
            yield {"type": "token", "text": "3 roles."}
            yield {
                "type": "metadata",
                "trace_id": "t-1",
                "trace_url": "https://cloud.langfuse.com/project/p/traces/t-1",
            }

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={
                "query": "list 3 data engineer jobs",
                "session_id": "session-123",
                "user_id": "user-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertEqual(response.headers["x-accel-buffering"], "no")
        events = _parse_sse_events(response.text)
        self.assertEqual([event_type for event_type, _ in events], ["session", "token", "token", "metadata", "done"])
        self.assertEqual(events[0][1], {"session_id": "session-123"})
        self.assertEqual(events[1][1], {"text": "There are "})
        self.assertEqual(events[2][1], {"text": "3 roles."})
        self.assertEqual(
            events[3][1],
            {
                "trace_id": "t-1",
                "trace_url": "https://cloud.langfuse.com/project/p/traces/t-1",
            },
        )
        self.assertEqual(events[4][1], {})

    def test_stream_route_returns_fallback_before_metadata_when_no_tokens(self) -> None:
        async def _fake_astream(**kwargs):
            yield {"type": "metadata", "trace_id": None, "trace_url": None}

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "what time is it?", "session_id": "session-123"},
        )

        self.assertEqual(response.status_code, 200)
        events = _parse_sse_events(response.text)
        self.assertEqual([event_type for event_type, _ in events], ["session", "token", "metadata", "done"])
        self.assertEqual(events[1][1], {"text": FALLBACK_ANSWER})
        self.assertEqual(events[2][1], {"trace_id": None, "trace_url": None})

    def test_stream_route_returns_in_band_error_and_done_for_mid_run_failure(self) -> None:
        async def _fake_astream(**kwargs):
            yield {"type": "token", "text": "Partial answer"}
            raise RuntimeError("database password leaked")

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list 3 data engineer jobs", "session_id": "session-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("database password leaked", response.text)
        events = _parse_sse_events(response.text)
        self.assertEqual([event_type for event_type, _ in events], ["session", "token", "error", "done"])
        self.assertEqual(events[2][1], {"message": BUSY_MESSAGE})
        self.assertEqual(events[3][1], {})

    def test_stream_route_returns_uuid4_session_when_omitted(self) -> None:
        async def _fake_astream(**kwargs):
            yield {"type": "metadata", "trace_id": None, "trace_url": None}

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list 3 data engineer jobs"},
        )

        self.assertEqual(response.status_code, 200)
        events = _parse_sse_events(response.text)
        self.assertEqual(events[0][0], "session")
        returned_id = events[0][1]["session_id"]
        self.assertIsNotNone(returned_id)
        self.assertEqual(uuid.UUID(returned_id).version, 4)

    def test_stream_route_rejects_blank_query_before_stream_starts(self) -> None:
        self.app.state.runtime.astream = AsyncMock()

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "   "},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Query must not be empty."})
        self.app.state.runtime.astream.assert_not_called()
