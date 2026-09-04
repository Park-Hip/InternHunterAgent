from __future__ import annotations

import asyncio
import json
import unittest
import uuid
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.agents.service import FALLBACK_ANSWER
from src.api.app import create_app
from src.api.routes.query import _server_sent_event
from src.core.errors import (
    BUSY_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    INTERNAL_ERROR_CODE,
    PROVIDER_BUSY_ERROR_CODE,
)


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


class _ConversationRuntime:
    """A runtime mock that yields different SSE events per call, enabling multi-turn HTTP probes."""

    def __init__(self) -> None:
        self.call_count = 0
        self.calls: list[tuple[str, str, str | None]] = []
        self._events_per_turn: list[list[dict[str, str | bool | None]]] = []
        self._raise_during_turn: bool = False
        self._sensitive_data: str = ""

    def set_turn_events(self, events: list[dict[str, str | bool | None]]) -> None:
        self._events_per_turn.append(events)

    def set_raise_during_turn(self) -> None:
        self._raise_during_turn = True

    def set_sensitive_data(self, data: str) -> None:
        self._sensitive_data = data

    async def astream(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
        latency=None,
        completion_event: asyncio.Event | None = None,
    ):
        self.call_count += 1
        self.calls.append((query, session_id, user_id))
        if self._events_per_turn:
            idx = min(self.call_count - 1, len(self._events_per_turn) - 1)
            events = self._events_per_turn[idx]
            for i, event in enumerate(events):
                yield event
                if self._raise_during_turn and i == len(events) - 1:
                    if self._sensitive_data:
                        raise RuntimeError(self._sensitive_data)
                    raise RuntimeError("database password leaked")
            return
        if self.call_count == 1:
            yield {"type": "token", "text": "First answer"}
            yield {"type": "metadata", "trace_id": "t-1", "trace_url": None}
        else:
            yield {"type": "token", "text": "Second answer"}
            yield {"type": "metadata", "trace_id": "t-2", "trace_url": None}


class TestMultiTurnSessionContinuity(unittest.TestCase):
    """Verifies session ID persistence across multiple turns in a conversation."""

    def setUp(self) -> None:
        self.app = create_app(rate_limit="1000/minute", docs_enabled=False)
        self.runtime = _ConversationRuntime()
        self.app.state.runtime = self.runtime
        self.client = TestClient(self.app)

    def test_multi_turn_session_continuity(self) -> None:
        """Same session_id across four turns is echoed back by the server each time."""
        session_id = "persistent-conversation-session"
        for turn_index in range(4):
            response = self.client.post(
                "/api/v1/agent/chat/stream",
                json={
                    "query": f"turn {turn_index + 1} question",
                    "session_id": session_id,
                    "user_id": "user-test",
                },
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            events = _parse_sse_events(response.text)
            assert events[0][0] == "session"
            assert events[0][1]["session_id"] == session_id

        assert self.runtime.call_count == 4
        for query, sid, uid in self.runtime.calls:
            assert sid == session_id

    def test_different_sessions_are_isolated(self) -> None:
        """Two concurrent sessions maintain independent session IDs."""
        session_a = "session-alpha"
        session_b = "session-beta"

        response_a = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "query for alpha", "session_id": session_a},
        )
        events_a = _parse_sse_events(response_a.text)
        assert events_a[0][1]["session_id"] == session_a

        response_b = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "query for beta", "session_id": session_b},
        )
        events_b = _parse_sse_events(response_b.text)
        assert events_b[0][1]["session_id"] == session_b
        assert events_a[0][1]["session_id"] != events_b[0][1]["session_id"]

        session_ids_seen = {sid for _, sid, _ in self.runtime.calls}
        assert session_ids_seen == {session_a, session_b}

    def test_omitted_session_id_generates_uuid4(self) -> None:
        """When no session_id is provided, the server generates a valid UUID v4."""
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "no session provided"},
        )
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        returned_id = events[0][1]["session_id"]
        assert returned_id is not None
        assert uuid.UUID(returned_id).version == 4


class TestMultiTurnTokenFiltering(unittest.TestCase):
    """Verifies that sensitive data does not leak across conversation turns."""

    def setUp(self) -> None:
        self.app = create_app(rate_limit="1000/minute", docs_enabled=False)
        self.runtime = _ConversationRuntime()
        self.app.state.runtime = self.runtime
        self.client = TestClient(self.app)

    def test_no_credential_leakage_across_turns(self) -> None:
        """Sensitive data injected as runtime context does not appear in any turn's response."""
        self.runtime.set_sensitive_data("postgresql://admin:secret@localhost/db")
        self.runtime.set_turn_events(
            [
                {"type": "token", "text": "Here are the Python jobs."},
                {"type": "metadata", "trace_id": "t-filter-1", "trace_url": None},
            ]
        )
        self.runtime.set_turn_events(
            [
                {"type": "token", "text": "And here are the SQL jobs."},
                {"type": "metadata", "trace_id": "t-filter-2", "trace_url": None},
            ]
        )

        session_id = "filter-test-session"
        responses = []
        for query in ["Python jobs", "SQL jobs"]:
            response = self.client.post(
                "/api/v1/agent/chat/stream",
                json={"query": query, "session_id": session_id},
            )
            assert response.status_code == 200
            responses.append(response.text)

        for body in responses:
            assert "postgresql://" not in body
            assert "secret" not in body
            assert "password=" not in body

    def test_error_body_does_not_leak_credentials(self) -> None:
        """When an error is raised mid-stream, the error response does not contain credentials."""
        self.runtime.set_sensitive_data("api_key=sk-abc123")
        self.runtime.set_turn_events(
            [{"type": "token", "text": "Partial answer"}]
        )
        self.runtime.set_raise_during_turn()

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "trigger error", "session_id": "error-session"},
        )
        assert response.status_code == 200
        assert "api_key" not in response.text
        assert "sk-abc123" not in response.text
        events = _parse_sse_events(response.text)
        event_types = [e[0] for e in events]
        assert "error" in event_types
        assert "done" in event_types


class TestMultiTurnErrorBubble(unittest.TestCase):
    """Verifies graceful error handling mid-conversation."""

    def setUp(self) -> None:
        self.app = create_app(rate_limit="1000/minute", docs_enabled=False)
        self.runtime = _ConversationRuntime()
        self.app.state.runtime = self.runtime
        self.client = TestClient(self.app)

    def test_error_mid_stream_emits_error_then_done(self) -> None:
        """A stream that fails mid-run emits an error event followed by done."""
        self.runtime.set_turn_events(
            [{"type": "token", "text": "Partial answer"}]
        )
        self.runtime.set_raise_during_turn()

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "crash me", "session_id": "error-bubble-session"},
        )
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        event_types = [e[0] for e in events]
        assert event_types == ["session", "token", "error", "done"]
        error_event = next(e for e in events if e[0] == "error")
        assert error_event[1]["code"] == INTERNAL_ERROR_CODE
        assert error_event[1]["retryable"] is False
        assert GENERIC_ERROR_MESSAGE == error_event[1]["message"]
        assert events[-1][0] == "done"

    def test_provider_busy_is_retryable_after_normal_prior_turn(self) -> None:
        """A normal first turn succeeds; a subsequent turn returns a retryable provider-busy error."""

        async def _refusal_astream(**kwargs):
            yield {"type": "token", "text": "partial"}
            raise RuntimeError("provider quota exhausted")

        # First request uses the default runtime (normal response)
        first = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list jobs", "session_id": "error-carryover-session"},
        )
        assert first.status_code == 200
        first_events = _parse_sse_events(first.text)
        assert first_events[-1][0] == "done"

        # Replace astream AFTER the first request so only the second turn is affected
        self.runtime.astream = _refusal_astream

        second = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list more", "session_id": "error-carryover-session"},
        )
        assert second.status_code == 200
        second_events = _parse_sse_events(second.text)
        event_types = [e[0] for e in second_events]
        assert "error" in event_types
        assert "done" in event_types
        error_event = next(e for e in second_events if e[0] == "error")
        assert error_event[1]["code"] == PROVIDER_BUSY_ERROR_CODE
        assert error_event[1]["retryable"] is True
        assert error_event[1]["message"] == BUSY_MESSAGE

    def test_completed_multi_turn_stream_ends_with_done(self) -> None:
        """A stream that yields tokens and metadata across multiple turns terminates with done."""
        self.runtime.set_turn_events(
            [
                {"type": "token", "text": "First turn answer"},
                {"type": "metadata", "trace_id": "t-e1", "trace_url": None},
            ]
        )
        self.runtime.set_turn_events(
            [
                {"type": "token", "text": "Second turn answer"},
                {"type": "metadata", "trace_id": "t-e2", "trace_url": None},
            ]
        )

        session_id = "completion-multi-turn"
        for _ in range(2):
            response = self.client.post(
                "/api/v1/agent/chat/stream",
                json={"query": "next question", "session_id": session_id},
            )
            assert response.status_code == 200
            events = _parse_sse_events(response.text)
            event_types = [e[0] for e in events]
            assert event_types[0] == "session"
            assert event_types[-1] == "done"
