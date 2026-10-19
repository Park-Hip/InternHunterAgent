from __future__ import annotations

import asyncio
import json
import unittest
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.agents.models import (
    StreamErrorEvent,
    StreamEvent,
    StreamMetadataEvent,
    StreamTokenEvent,
    StreamToolEvent,
)
from src.agents.runtime.react_agent import AgentRuntime
from src.agents.runtime.tool_events import emit_tool_event, new_result_facts
from src.api.app import create_app
from src.api.routes.query import _server_sent_event
from src.api.schemas import STREAM_EVENT_SCHEMA
from src.core.errors import (
    GENERIC_ERROR_MESSAGE,
    INTERNAL_ERROR_CODE,
    PROVIDER_BUSY_ERROR_CODE,
)

# The user-facing strings are written out rather than read from the constants:
# ADR-0061 makes the server the owner of the copy, so changing it must show up
# as a deliberate test edit instead of passing invisibly through a shared name.


def _parse_sse_events(body: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
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
            yield StreamTokenEvent(type="token", text="There are ")
            yield StreamTokenEvent(type="token", text="3 roles.")
            yield StreamMetadataEvent(
                type="metadata",
                trace_id="t-1",
                trace_url="https://cloud.langfuse.com/project/p/traces/t-1",
            )

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
        self.assertEqual(
            [event_type for event_type, _ in events],
            ["session", "token", "token", "metadata", "done"],
        )
        # The payload carries `type` because the published schema requires it; the
        # SSE `event:` line remains the authoritative name for the frame.
        self.assertEqual(events[0][1], {"type": "session", "session_id": "session-123"})
        self.assertEqual(events[1][1], {"type": "token", "text": "There are "})
        self.assertEqual(events[2][1], {"type": "token", "text": "3 roles."})
        self.assertEqual(
            events[3][1],
            {
                "type": "metadata",
                "trace_id": "t-1",
                "trace_url": "https://cloud.langfuse.com/project/p/traces/t-1",
                "answer_source": "model",
            },
        )
        self.assertEqual(events[4][1], {"type": "done"})

    def test_stream_route_returns_fallback_before_metadata_when_no_tokens(self) -> None:
        async def _fake_astream(**kwargs):
            yield StreamMetadataEvent(type="metadata", trace_id=None, trace_url=None)

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "what time is it?", "session_id": "session-123"},
        )

        self.assertEqual(response.status_code, 200)
        events = _parse_sse_events(response.text)
        self.assertEqual(
            [event_type for event_type, _ in events],
            ["session", "token", "metadata", "done"],
        )
        self.assertEqual(
            events[1][1],
            {
                "type": "token",
                "text": "Chưa thể trả lời câu hỏi này - vui lòng thử diễn đạt lại.",
            },
        )
        self.assertEqual(
            events[2][1],
            {
                "type": "metadata",
                "trace_id": None,
                "trace_url": None,
                "answer_source": "fallback",
            },
        )

    def test_stream_route_returns_in_band_error_and_done_for_mid_run_failure(
        self,
    ) -> None:
        async def _fake_astream(**kwargs):
            yield StreamTokenEvent(type="token", text="Partial answer")
            raise RuntimeError("database password leaked")

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list 3 data engineer jobs", "session_id": "session-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("database password leaked", response.text)
        events = _parse_sse_events(response.text)
        self.assertEqual(
            [event_type for event_type, _ in events],
            ["session", "token", "error", "done"],
        )
        self.assertEqual(
            events[2][1],
            {
                "type": "error",
                "message": "Hiện chưa thể hoàn tất yêu cầu này. Vui lòng thử lại sau.",
                "code": INTERNAL_ERROR_CODE,
                "retryable": False,
            },
        )
        self.assertEqual(events[3][1], {"type": "done"})

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
        self.assertEqual(
            [event_type for event_type, _ in events], ["session", "error", "done"]
        )
        self.assertEqual(
            events[1][1],
            {
                "type": "error",
                "message": "Bản thử nghiệm đang bận - vui lòng thử lại sau một lát.",
                "code": PROVIDER_BUSY_ERROR_CODE,
                "retryable": True,
            },
        )

    def test_stream_route_returns_uuid4_session_when_omitted(self) -> None:
        async def _fake_astream(**kwargs):
            yield StreamMetadataEvent(type="metadata", trace_id=None, trace_url=None)

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
        content = schema["paths"]["/api/v1/agent/chat/stream"]["post"]["responses"][
            "200"
        ]["content"]
        self.assertIn("text/event-stream", content)

        event_schema = content["text/event-stream"]["schema"]
        discriminator = event_schema["discriminator"]
        self.assertEqual(discriminator["propertyName"], "type")
        self.assertEqual(
            set(discriminator["mapping"]),
            {"session", "token", "metadata", "error", "tool", "done"},
        )
        self.assertEqual(len(event_schema["oneOf"]), 6)

        error_ref = discriminator["mapping"]["error"]
        error_schema = event_schema["$defs"][error_ref.rsplit("/", maxsplit=1)[-1]]
        self.assertTrue(
            {"message", "code", "retryable"}.issubset(error_schema["properties"])
        )

        metadata_ref = discriminator["mapping"]["metadata"]
        metadata_schema = event_schema["$defs"][
            metadata_ref.rsplit("/", maxsplit=1)[-1]
        ]
        self.assertIn("answer_source", metadata_schema["properties"])

    def test_server_sent_event_uses_exact_sse_framing(self) -> None:
        self.assertEqual(
            _server_sent_event(event="token", data={"text": "first\nsecond"}),
            'event: token\ndata: {"text": "first\\nsecond"}\n\n',
        )


class StreamPublishedContractTests(unittest.TestCase):
    """The bytes on the wire must satisfy the schema published at /openapi.json.

    The published ``STREAM_EVENT_SCHEMA`` is a union discriminated on ``type``,
    so every variant lists ``type`` among its required properties, and every
    frame must carry it (#689). These tests assert the contract rather than the
    implementation: they check the streamed frames against the published schema,
    not against the route's own copy of it.
    """

    def setUp(self) -> None:
        self.app = create_app(rate_limit="1000/minute", docs_enabled=False)
        self.app.state.runtime = AsyncMock()
        self.client = TestClient(self.app)

    @staticmethod
    def _required_properties(event_type: str) -> set[str]:
        ref = STREAM_EVENT_SCHEMA["discriminator"]["mapping"][event_type]
        definition = ref.rsplit("/", maxsplit=1)[-1]
        return set(STREAM_EVENT_SCHEMA["$defs"][definition].get("required", []))

    def test_every_streamed_frame_satisfies_the_published_schema(self) -> None:
        async def _fake_astream(**kwargs):
            yield StreamTokenEvent(type="token", text="There are ")
            yield StreamToolEvent(
                type="tool",
                name="query_jobs",
                status="ok",
                call_id="call-1",
                arguments={"technology": "python"},
                duration_ms=12,
                error=None,
                row_count=7,
                truncated=False,
            )
            yield StreamMetadataEvent(
                type="metadata",
                trace_id="t-1",
                trace_url="https://cloud.langfuse.com/project/p/traces/t-1",
            )

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list 3 data engineer jobs", "session_id": "session-123"},
        )

        self.assertEqual(response.status_code, 200)
        events = _parse_sse_events(response.text)
        self.assertEqual(
            [event_type for event_type, _ in events],
            ["session", "token", "tool", "metadata", "done"],
        )
        for event_type, payload in events:
            with self.subTest(event=event_type):
                missing = self._required_properties(event_type) - set(payload)
                self.assertEqual(
                    missing,
                    set(),
                    f"the {event_type!r} frame omits {sorted(missing)}, which the "
                    f"published schema marks as required",
                )

    def test_the_error_frame_satisfies_the_published_schema(self) -> None:
        async def _fake_astream(**kwargs):
            yield StreamErrorEvent(
                type="error",
                message=GENERIC_ERROR_MESSAGE,
                code=INTERNAL_ERROR_CODE,
                retryable=False,
            )

        self.app.state.runtime.astream = _fake_astream

        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "list 3 data engineer jobs", "session_id": "session-123"},
        )

        self.assertEqual(response.status_code, 200)
        errors = [
            (event_type, payload)
            for event_type, payload in _parse_sse_events(response.text)
            if event_type == "error"
        ]
        self.assertEqual(len(errors), 1)
        _, payload = errors[0]
        missing = self._required_properties("error") - set(payload)
        self.assertEqual(missing, set(), f"the error frame omits {sorted(missing)}")


class _MultiTurnRuntime:
    """A runtime mock that yields different SSE events per call, enabling multi-turn HTTP probes."""

    def __init__(self) -> None:
        self.call_count = 0
        self.calls: list[tuple[str, str, str | None]] = []
        self._events_per_turn: list[list[StreamEvent]] = []
        self._raise_during_turn: bool = False

    def set_turn_events(self, events: list[StreamEvent]) -> None:
        self._events_per_turn.append(events)

    def set_raise_during_turn(self) -> None:
        self._raise_during_turn = True

    async def astream(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
        observation=None,
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
                    raise RuntimeError("database password leaked")
            return
        if self.call_count == 1:
            yield StreamTokenEvent(type="token", text="First answer")
            yield StreamMetadataEvent(type="metadata", trace_id="t-1", trace_url=None)
        else:
            yield StreamTokenEvent(type="token", text="Second answer")
            yield StreamMetadataEvent(type="metadata", trace_id="t-2", trace_url=None)


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
        self.runtime.set_turn_events(
            [
                StreamTokenEvent(type="token", text="Acme uses Python"),
                StreamMetadataEvent(type="metadata", trace_id="t-c1", trace_url=None),
            ]
        )
        self.runtime.set_turn_events(
            [
                StreamTokenEvent(type="token", text="Acme also uses SQL"),
                StreamMetadataEvent(type="metadata", trace_id="t-c2", trace_url=None),
            ]
        )
        session_id = "referent-session"

        self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": "What stack does Acme use?", "session_id": session_id},
        )
        response = self.client.post(
            "/api/v1/agent/chat/stream",
            json={
                "query": "Which language does Acme use for queries?",
                "session_id": session_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        events = _parse_sse_events(response.text)
        token_events = [e for e in events if e[0] == "token"]
        self.assertEqual(len(token_events), 1)
        self.assertIn("Acme", token_events[0][1]["text"])
        self.assertIn("SQL", token_events[0][1]["text"])

    def test_multi_turn_refusal_after_normal_prior_turn(self) -> None:
        """A normal first turn succeeds; a subsequent turn returns an in-band error before done."""
        self.runtime.set_turn_events(
            [
                StreamTokenEvent(type="token", text="ok"),
                StreamMetadataEvent(type="metadata", trace_id=None, trace_url=None),
            ]
        )

        # Second turn: yield nothing, then raise provider-busy error
        async def _refusal_astream(**kwargs):
            yield StreamTokenEvent(type="token", text="partial")
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
            json={
                "query": "list data engineer jobs",
                "session_id": "completion-session",
            },
        )
        self.assertEqual(response.status_code, 200)
        events = _parse_sse_events(response.text)
        event_types = [e[0] for e in events]
        self.assertEqual(event_types[-1], "done")
        self.assertEqual(event_types[0], "session")

    def test_aborted_stream_emits_error_then_done(self) -> None:
        """A stream that fails mid-run emits an error event followed by done."""
        self.runtime.set_turn_events(
            [
                StreamTokenEvent(type="token", text="Partial answer"),
            ]
        )
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


#: The recorded turn behind the wire-format contract test: the manual check
#: question from #679, answered from one tool call.
RECORDED_TURN_QUESTION = "Có bao nhiêu tin tuyển dụng ở Đà Nẵng?"
RECORDED_TURN_SESSION = "recorded-turn-session"
RECORDED_TRACE_ID = "recorded-trace-id"
RECORDED_TRACE_URL = (
    "https://cloud.langfuse.com/project/recorded/traces/recorded-trace-id"
)
RECORDED_TOOL_ARGUMENTS = {"city": "Đà Nẵng", "limit": "10"}


def _recorded_chunk(
    content: str,
    tool_call_chunks: list[dict[str, str]] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_call_chunks=tool_call_chunks or [])


async def _recorded_turn_agent_stream(*_args, **_kwargs):
    """The agent's output for one recorded turn: a tool call, then the answer.

    The tool frames come from the same public seam the observation middleware
    uses, so the replay exercises the real runtime queue and not a shortcut.
    """
    yield (
        _recorded_chunk(
            "",
            [
                {
                    "name": "query_clean_jobs",
                    "args": json.dumps(RECORDED_TOOL_ARGUMENTS, ensure_ascii=False),
                }
            ],
        ),
        {"langgraph_node": "model"},
    )
    await emit_tool_event(
        name="query_clean_jobs",
        status="running",
        call_id="recorded-call-1",
        arguments=RECORDED_TOOL_ARGUMENTS,
    )
    yield (
        _recorded_chunk("SELECT count(*) FROM clean_jobs"),
        {"langgraph_node": "tools"},
    )
    facts = new_result_facts()
    facts.row_count = 7
    facts.truncated = False
    await emit_tool_event(
        name="query_clean_jobs",
        status="ok",
        call_id="recorded-call-1",
        arguments=RECORDED_TOOL_ARGUMENTS,
        duration_ms=42,
        facts=facts,
    )
    yield (_recorded_chunk("Ở Đà Nẵng hiện có "), {"langgraph_node": "model"})
    yield (_recorded_chunk("7 tin tuyển dụng."), {"langgraph_node": "model"})


class StreamWireFormatContractTests(unittest.TestCase):
    """The frames of a recorded turn must stay the same across the refactor.

    ``fixtures/stream_frames_recorded_turn.json`` holds the frames the route
    wrote before the runtime, service, and route started passing typed events:
    the event name, the payload, and the order for a turn that calls one tool
    and streams its answer. The frames are compared after parsing, because
    JSON key order and whitespace are not part of the contract; the event
    names, the payload fields including ``type``, and the frame order are.
    """

    fixture = (
        Path(__file__).parent / "fixtures" / "stream_frames_recorded_turn.json"
    )

    def test_the_recorded_turn_writes_the_same_frames(self) -> None:
        app = create_app(rate_limit="1000/minute", docs_enabled=False)

        async def _agent_factory(**_kwargs):
            return SimpleNamespace(astream=_recorded_turn_agent_stream)

        app.state.runtime = AgentRuntime(agent_factory=_agent_factory)

        @asynccontextmanager
        async def _request_trace(**_kwargs):
            yield RECORDED_TRACE_ID

        with (
            patch(
                "src.agents.runtime.react_agent.build_langfuse_config",
                return_value={"callbacks": ["handler"]},
            ),
            patch(
                "src.agents.runtime.react_agent.langfuse_request_trace",
                side_effect=_request_trace,
            ),
            patch(
                "src.agents.runtime.react_agent.langfuse_trace_url",
                return_value=RECORDED_TRACE_URL,
            ),
        ):
            response = TestClient(app).post(
                "/api/v1/agent/chat/stream",
                json={
                    "query": RECORDED_TURN_QUESTION,
                    "session_id": RECORDED_TURN_SESSION,
                },
            )

        self.assertEqual(response.status_code, 200)
        frames = [
            [event_type, payload]
            for event_type, payload in _parse_sse_events(response.text)
        ]
        expected = json.loads(self.fixture.read_text(encoding="utf-8"))
        self.assertEqual(frames, expected)
