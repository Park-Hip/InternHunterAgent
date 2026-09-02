from __future__ import annotations

import json
import uuid
import unittest
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
        self.assertEqual(
            events[2][1],
            {
                "message": GENERIC_ERROR_MESSAGE,
                "code": INTERNAL_ERROR_CODE,
                "retryable": False,
            },
        )
        self.assertEqual(events[3][1], {})

    def test_stream_route_marks_provider_busy_as_retryable(self) -> None:
        async def _fake_astream(**kwargs):
            raise RuntimeError("provider quota exhausted")
            yield  # pragma: no cover - makes this an async generator

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list 3 data engineer jobs", "session_id": "session-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("provider quota exhausted", response.text)
        events = _parse_sse_events(response.text)
        self.assertEqual([event_type for event_type, _ in events], ["session", "error", "done"])
        self.assertEqual(
            events[1][1],
            {
                "message": BUSY_MESSAGE,
                "code": PROVIDER_BUSY_ERROR_CODE,
                "retryable": True,
            },
        )

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


class StreamOpenAPITests(unittest.TestCase):
    def test_stream_operation_documents_sse_event_variants(self) -> None:
        app = create_app(rate_limit="1000/minute", docs_enabled=True)
        response = TestClient(app).get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        schema = response.json()
        content = schema["paths"]["/api/v1/agent/chat/stream"]["post"][
            "responses"
        ]["200"]["content"]
        self.assertIn("text/event-stream", content)

        event_schema = content["text/event-stream"]["schema"]
        discriminator = event_schema["discriminator"]
        self.assertEqual(discriminator["propertyName"], "type")
        self.assertEqual(
            set(discriminator["mapping"]),
            {"session", "token", "metadata", "error", "done"},
        )
        self.assertEqual(len(event_schema["oneOf"]), 5)

        error_ref = discriminator["mapping"]["error"]
        error_schema = event_schema["$defs"][
            error_ref.rsplit("/", maxsplit=1)[-1]
        ]
        self.assertTrue(
            {"message", "code", "retryable"}.issubset(error_schema["properties"])
        )

    def test_server_sent_event_uses_exact_sse_framing(self) -> None:
        self.assertEqual(
            _server_sent_event(event="token", data={"text": "first\nsecond"}),
            'event: token\ndata: {"text": "first\\nsecond"}\n\n',
        )


class _MultiTurnRuntime:
    """A runtime mock that yields different SSE events per call, enabling multi-turn HTTP probes."""

    def __init__(self) -> None:
        self.call_count = 0
        self.calls: list[tuple[str, str, str | None]] = []
        self._events_per_turn: list[list[dict[str, str | bool | None]]] = []
        self._raise_during_turn: bool = False

    def set_turn_events(self, events: list[dict[str, str | bool | None]]) -> None:
        self._events_per_turn.append(events)

    def set_raise_during_turn(self) -> None:
        self._raise_during_turn = True

    async def astream(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
        latency=None,
    ):
        self.call_count += 1
        self.calls.append((query, session_id, user_id))
        if self._events_per_turn:
            idx = min(self.call_count - 1, len(self._events_per_turn) - 1)
            events = self._events_per_turn[idx]
            for i, event in enumerate(events):
                yield event
                if self._raise_during_turn and i == len(events) - 1:
                    raise RuntimeError("database password leaked")
            return
        if self.call_count == 1:
            yield {"type": "token", "text": "First answer"}
            yield {"type": "metadata", "trace_id": "t-1", "trace_url": None}
        else:
            yield {"type": "token", "text": "Second answer"}
            yield {"type": "metadata", "trace_id": "t-2", "trace_url": None}


class StreamMultiTurnTests(unittest.TestCase):
    """Black-box HTTP/SSE probes for multi-turn conversation behavior."""

    def setUp(self) -> None:
        self.app = create_app(rate_limit="1000/minute", docs_enabled=False)
        self.runtime = _MultiTurnRuntime()
        self.app.state.runtime = self.runtime
        self.client = TestClient(self.app)

    def test_multi_turn_session_continuity(self) -> None:
        """Same session_id across two turns is echoed back by the server each time."""
        session_id = "persistent-session"
        for _ in range(2):
            response = self.client.post(
                "/api/v1/agent/chat/stream",
                json={"query": "next job", "session_id": session_id},
            )
            self.assertEqual(response.status_code, 200)
            events = _parse_sse_events(response.text)
            self.assertEqual(events[0][0], "session")
            self.assertEqual(events[0][1]["session_id"], session_id)

        self.assertEqual(self.runtime.call_count, 2)
        for query, sid, uid in self.runtime.calls:
            self.assertEqual(sid, session_id)

    def test_multi_turn_session_isolation(self) -> None:
        """Different session_ids produce different session events and do not leak state."""
        session_a = "session-alpha"
        session_b = "session-beta"

        response_a = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "query for alpha", "session_id": session_a},
        )
        self.assertEqual(response_a.status_code, 200)
        events_a = _parse_sse_events(response_a.text)
        self.assertEqual(events_a[0][1]["session_id"], session_a)

        response_b = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "query for beta", "session_id": session_b},
        )
        self.assertEqual(response_b.status_code, 200)
        events_b = _parse_sse_events(response_b.text)
        self.assertEqual(events_b[0][1]["session_id"], session_b)
        self.assertNotEqual(events_a[0][1]["session_id"], events_b[0][1]["session_id"])

        self.assertEqual(self.runtime.call_count, 2)
        session_ids_seen = {sid for _, sid, _ in self.runtime.calls}
        self.assertEqual(session_ids_seen, {session_a, session_b})

    def test_multi_turn_correction_referent_handled(self) -> None:
        """Turn 2 yields a response that semantically references turn 1 content."""
        self.runtime.set_turn_events([
            {"type": "token", "text": "Acme uses Python"},
            {"type": "metadata", "trace_id": "t-c1", "trace_url": None},
        ])
        self.runtime.set_turn_events([
            {"type": "token", "text": "Acme also uses SQL"},
            {"type": "metadata", "trace_id": "t-c2", "trace_url": None},
        ])
        session_id = "referent-session"

        self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "What stack does Acme use?", "session_id": session_id},
        )
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "Which language does Acme use for queries?", "session_id": session_id},
        )
        self.assertEqual(response.status_code, 200)
        events = _parse_sse_events(response.text)
        token_events = [e for e in events if e[0] == "token"]
        self.assertEqual(len(token_events), 1)
        self.assertIn("Acme", token_events[0][1]["text"])
        self.assertIn("SQL", token_events[0][1]["text"])

    def test_multi_turn_refusal_after_normal_prior_turn(self) -> None:
        """A normal first turn succeeds; a subsequent turn returns an in-band error before done."""
        self.runtime.set_turn_events([
            {"type": "token", "text": "ok"},
            {"type": "metadata", "trace_id": None, "trace_url": None},
        ])
        # Second turn: yield nothing, then raise provider-busy error
        async def _refusal_astream(**kwargs):
            yield {"type": "token", "text": "partial"}
            raise RuntimeError("provider quota exhausted")

        self.runtime.astream = _refusal_astream

        first = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list jobs", "session_id": "refusal-session"},
        )
        self.assertEqual(first.status_code, 200)
        first_events = _parse_sse_events(first.text)
        self.assertEqual(first_events[-1][0], "done")

        second = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list more", "session_id": "refusal-session"},
        )
        self.assertEqual(second.status_code, 200)
        second_events = _parse_sse_events(second.text)
        event_types = [e[0] for e in second_events]
        self.assertIn("error", event_types)
        self.assertIn("done", event_types)
        error_event = next(e for e in second_events if e[0] == "error")
        self.assertEqual(error_event[1]["code"], PROVIDER_BUSY_ERROR_CODE)
        self.assertTrue(error_event[1]["retryable"])

    def test_completed_stream_ends_with_done(self) -> None:
        """A stream that yields tokens and metadata terminates with a done event."""
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list data engineer jobs", "session_id": "completion-session"},
        )
        self.assertEqual(response.status_code, 200)
        events = _parse_sse_events(response.text)
        event_types = [e[0] for e in events]
        self.assertEqual(event_types[-1], "done")
        self.assertEqual(event_types[0], "session")

    def test_aborted_stream_emits_error_then_done(self) -> None:
        """A stream that fails mid-run emits an error event followed by done."""
        self.runtime.set_turn_events([
            {"type": "token", "text": "Partial answer"},
        ])
        self.runtime.set_raise_during_turn()

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "crash me", "session_id": "abort-session"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("database password leaked", response.text)
        events = _parse_sse_events(response.text)
        event_types = [e[0] for e in events]
        self.assertEqual(event_types, ["session", "token", "error", "done"])
        error_event = next(e for e in events if e[0] == "error")
        self.assertEqual(error_event[1]["code"], INTERNAL_ERROR_CODE)
        self.assertFalse(error_event[1]["retryable"])
        self.assertEqual(events[-1][0], "done")
