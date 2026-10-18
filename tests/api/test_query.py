from __future__ import annotations

import asyncio
import unittest
from unittest.mock import ANY, AsyncMock, patch

from fastapi.testclient import TestClient

from src.agents.models import (
    StreamDoneEvent,
    StreamEvent,
    StreamMetadataEvent,
    StreamSessionEvent,
    StreamTokenEvent,
)
from src.agents.service import FALLBACK_ANSWER
from src.serving.composition import app
from src.api.routes.query import _server_sent_event, _with_heartbeats
from src.api.schemas import DEFAULT_MAX_QUERY_CHARS
from src.core.errors import BUSY_MESSAGE, GENERIC_ERROR_MESSAGE, ProviderBusyError


class QueryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        # Lifespan is not triggered (TestClient is not used as a context
        # manager), so app.state.runtime would otherwise be unset.
        app.state.runtime = AsyncMock()
        self.client = TestClient(app)

    def test_query_route_returns_structured_response(self) -> None:
        fake_response = {
            "answer": "The current time is 14:01:52.",
            "session_id": "session-123",
            "trace_id": None,
            "trace_url": None,
        }

        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(return_value=fake_response),
        ) as mock_generate:
            response = self.client.post(
                "/api/v1/agent/chat",
                json={
                    "query": "what time is it?",
                    "session_id": "session-123",
                    "user_id": "user-123",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "answer": "The current time is 14:01:52.",
                "session_id": "session-123",
                "trace_id": None,
                "trace_url": None,
            },
        )
        mock_generate.assert_awaited_once_with(
            query="what time is it?",
            session_id="session-123",
            user_id="user-123",
            runtime=ANY,
            stream_observation_factory=ANY,
        )

    def test_query_route_returns_structured_response_for_job_data_question(self) -> None:
        fake_response = {
            "answer": "Acme uses Python, FastAPI, and Postgres.",
            "session_id": "session-123",
            "trace_id": "trace-456",
            "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-456",
        }

        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(return_value=fake_response),
        ) as mock_generate:
            response = self.client.post(
                "/api/v1/agent/chat",
                json={
                    "query": "What tech stack does Acme use?",
                    "session_id": "session-123",
                    "user_id": "user-123",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body.keys()), {"answer", "session_id", "trace_id", "trace_url"})
        self.assertEqual(
            body,
            {
                "answer": "Acme uses Python, FastAPI, and Postgres.",
                "session_id": "session-123",
                "trace_id": "trace-456",
                "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-456",
            },
        )
        self.assertNotIn("sql", body)
        self.assertNotIn("table", body)
        mock_generate.assert_awaited_once_with(
            query="What tech stack does Acme use?",
            session_id="session-123",
            user_id="user-123",
            runtime=ANY,
            stream_observation_factory=ANY,
        )

    def test_query_route_returns_generated_session_id_when_omitted(self) -> None:
        fake_response = {
            "answer": "The current time is 14:01:52.",
            "session_id": "generated-session-456",
            "trace_id": None,
            "trace_url": None,
        }

        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(return_value=fake_response),
        ) as mock_generate:
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": "what time is it?"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["session_id"], "generated-session-456")
        mock_generate.assert_awaited_once_with(
            query="what time is it?",
            session_id=None,
            user_id=None,
            runtime=ANY,
            stream_observation_factory=ANY,
        )

    def test_query_route_returns_500_when_service_fails(self) -> None:
        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": "what time is it?"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": GENERIC_ERROR_MESSAGE})

    def test_query_route_returns_friendly_429_when_provider_is_rate_limited(self) -> None:
        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(side_effect=ProviderBusyError(status_code=429)),
        ):
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": "what time is it?"},
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {"detail": BUSY_MESSAGE})

    def test_query_route_returns_retryable_503_when_the_turn_deadline_expires(self) -> None:
        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(side_effect=ProviderBusyError()),
        ):
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": "what time is it?"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": BUSY_MESSAGE})

    def test_query_route_returns_400_for_blank_query(self) -> None:
        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(),
        ) as mock_generate:
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": "   "},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Query must not be empty."})
        mock_generate.assert_not_awaited()

    def test_query_route_accepts_query_at_length_cap(self) -> None:
        fake_response = {
            "answer": "ok",
            "session_id": "session-123",
            "trace_id": None,
            "trace_url": None,
        }
        capped_query = "x" * DEFAULT_MAX_QUERY_CHARS

        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(return_value=fake_response),
        ) as mock_generate:
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": capped_query, "session_id": "session-123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fake_response)
        mock_generate.assert_awaited_once_with(
            query=capped_query,
            session_id="session-123",
            user_id=None,
            runtime=ANY,
            stream_observation_factory=ANY,
        )

    def test_query_route_rejects_over_limit_query_before_service_call(self) -> None:
        over_limit_query = "x" * (DEFAULT_MAX_QUERY_CHARS + 1)

        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(),
        ) as mock_generate:
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": over_limit_query},
            )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["detail"][0]["type"], "string_too_long")
        self.assertEqual(body["detail"][0]["loc"], ["body", "query"])
        self.assertEqual(body["detail"][0]["ctx"]["max_length"], DEFAULT_MAX_QUERY_CHARS)
        mock_generate.assert_not_awaited()

    def test_query_route_returns_fallback_answer_when_runtime_answer_is_none(self) -> None:
        fake_response = {
            "answer": FALLBACK_ANSWER,
            "session_id": "session-123",
            "trace_id": None,
            "trace_url": None,
        }

        with patch(
            "src.api.routes.query.collect_agent_response",
            new=AsyncMock(return_value=fake_response),
        ):
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": "what time is it?", "session_id": "session-123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], FALLBACK_ANSWER)


class _CollectableRuntime:
    """A fake runtime whose streamed turn yields fixed events, blocks, or raises."""

    def __init__(self) -> None:
        self.events: list[StreamEvent] = []
        self.error: Exception | None = None
        self.block = False

    async def astream(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
        observation=None,
        completion_event: asyncio.Event | None = None,
    ):
        if self.block:
            await asyncio.Event().wait()
        if self.error is not None:
            raise self.error
            yield  # pragma: no cover - keeps this an async generator
        for event in self.events:
            yield event


class CollectingQueryRouteTests(unittest.TestCase):
    """The JSON route driven by the real service and a fake runtime (#689)."""

    def setUp(self) -> None:
        self.runtime = _CollectableRuntime()
        # Lifespan is not triggered, so app.state.runtime would otherwise be unset.
        app.state.runtime = self.runtime
        self.client = TestClient(app)

    def test_returns_the_collected_stream_as_the_response_body(self) -> None:
        self.runtime.events = [
            StreamTokenEvent(type="token", text="There are "),
            StreamTokenEvent(type="token", text="3 roles."),
            StreamMetadataEvent(
                type="metadata",
                trace_id="trace-1",
                trace_url="https://traces/trace-1",
            ),
        ]

        response = self.client.post(
            "/api/v1/agent/chat",
            json={"query": "how many roles?", "session_id": "session-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "answer": "There are 3 roles.",
                "session_id": "session-123",
                "trace_id": "trace-1",
                "trace_url": "https://traces/trace-1",
            },
        )

    def test_maps_a_rate_limited_provider_to_the_429_the_event_carries(self) -> None:
        self.runtime.error = RuntimeError("provider rate limit exceeded")

        response = self.client.post(
            "/api/v1/agent/chat", json={"query": "how many roles?"}
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {"detail": BUSY_MESSAGE})

    @patch("src.agents.service.settings")
    def test_maps_the_streamed_turn_deadline_to_a_retryable_503(
        self, mock_settings
    ) -> None:
        mock_settings.agent.stream_turn_timeout_seconds = 0.01
        self.runtime.block = True

        response = self.client.post(
            "/api/v1/agent/chat", json={"query": "how many roles?"}
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": BUSY_MESSAGE})



class StreamHeartbeatTests(unittest.IsolatedAsyncioTestCase):
    async def test_idle_source_emits_comment_heartbeats_before_preserving_event_order(self) -> None:
        release_token = asyncio.Event()

        async def events():
            yield StreamSessionEvent(type="session", session_id="session-123")
            await release_token.wait()
            yield StreamTokenEvent(type="token", text="Hello")
            yield StreamMetadataEvent(type="metadata", trace_id=None, trace_url=None)
            yield StreamDoneEvent(type="done")

        stream = _with_heartbeats(events(), heartbeat_seconds=0.001)
        first = await anext(stream)
        frames = [
            _server_sent_event(
                event=first.type, data=first.model_dump(exclude={"type"})
            )
        ]
        frames.append(await anext(stream))
        frames.append(await anext(stream))
        release_token.set()
        await asyncio.sleep(0)
        async for item in stream:
            if isinstance(item, str):
                frames.append(item)
                continue
            frames.append(
                _server_sent_event(
                    event=item.type,
                    data=item.model_dump(exclude={"type"}),
                )
            )

        self.assertEqual(frames[:3], [
            'event: session\ndata: {"session_id": "session-123"}\n\n',
            ": ping\n\n",
            ": ping\n\n",
        ])
        self.assertEqual(frames[3:], [
            'event: token\ndata: {"text": "Hello"}\n\n',
            'event: metadata\ndata: {"trace_id": null, "trace_url": null}\n\n',
            "event: done\ndata: {}\n\n",
        ])
