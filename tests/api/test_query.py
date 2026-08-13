from __future__ import annotations

import unittest
from unittest.mock import ANY, AsyncMock, patch

from fastapi.testclient import TestClient

from src.agents.service import FALLBACK_ANSWER, generate_agent_response
from src.api.app import app
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
            "src.api.routes.query.generate_agent_response",
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
        )

    def test_query_route_returns_structured_response_for_job_data_question(self) -> None:
        fake_response = {
            "answer": "Acme uses Python, FastAPI, and Postgres.",
            "session_id": "session-123",
            "trace_id": "trace-456",
            "trace_url": "https://cloud.langfuse.com/project/p/traces/trace-456",
        }

        with patch(
            "src.api.routes.query.generate_agent_response",
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
        )

    def test_query_route_returns_generated_session_id_when_omitted(self) -> None:
        fake_response = {
            "answer": "The current time is 14:01:52.",
            "session_id": "generated-session-456",
            "trace_id": None,
            "trace_url": None,
        }

        with patch(
            "src.api.routes.query.generate_agent_response",
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
        )

    def test_query_route_returns_500_when_service_fails(self) -> None:
        with patch(
            "src.api.routes.query.generate_agent_response",
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
            "src.api.routes.query.generate_agent_response",
            new=AsyncMock(side_effect=ProviderBusyError(status_code=429)),
        ):
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": "what time is it?"},
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {"detail": BUSY_MESSAGE})

    def test_query_route_returns_400_for_blank_query(self) -> None:
        with patch(
            "src.api.routes.query.generate_agent_response",
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
            "src.api.routes.query.generate_agent_response",
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
        )

    def test_query_route_rejects_over_limit_query_before_service_call(self) -> None:
        over_limit_query = "x" * (DEFAULT_MAX_QUERY_CHARS + 1)

        with patch(
            "src.api.routes.query.generate_agent_response",
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
            "src.api.routes.query.generate_agent_response",
            new=AsyncMock(return_value=fake_response),
        ):
            response = self.client.post(
                "/api/v1/agent/chat",
                json={"query": "what time is it?", "session_id": "session-123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], FALLBACK_ANSWER)


class GenerateAgentResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_none_runtime_answer_coerces_to_fallback(self) -> None:
        runtime = AsyncMock()
        runtime.ainvoke = AsyncMock(
            return_value={"answer": None, "trace_id": "trace-1", "trace_url": None}
        )

        result = await generate_agent_response(
            query="what time is it?",
            runtime=runtime,
            session_id="session-123",
        )

        self.assertEqual(result["answer"], FALLBACK_ANSWER)
        self.assertEqual(result["session_id"], "session-123")
        self.assertEqual(result["trace_id"], "trace-1")
        self.assertIsNone(result["trace_url"])

    async def test_blank_runtime_answer_coerces_to_fallback(self) -> None:
        runtime = AsyncMock()
        runtime.ainvoke = AsyncMock(
            return_value={"answer": "   ", "trace_id": None, "trace_url": None}
        )

        result = await generate_agent_response(
            query="what time is it?",
            runtime=runtime,
        )

        self.assertEqual(result["answer"], FALLBACK_ANSWER)

    async def test_normal_runtime_answer_passes_through(self) -> None:
        runtime = AsyncMock()
        runtime.ainvoke = AsyncMock(
            return_value={"answer": "The current time is 14:01:52.", "trace_id": None, "trace_url": None}
        )

        result = await generate_agent_response(
            query="what time is it?",
            runtime=runtime,
        )

        self.assertEqual(result["answer"], "The current time is 14:01:52.")

    async def test_provider_timeout_maps_to_provider_busy_error(self) -> None:
        runtime = AsyncMock()
        runtime.ainvoke = AsyncMock(side_effect=TimeoutError("request timed out"))

        with self.assertRaises(ProviderBusyError) as ctx:
            await generate_agent_response(
                query="what time is it?",
                runtime=runtime,
            )

        self.assertEqual(ctx.exception.status_code, 503)
