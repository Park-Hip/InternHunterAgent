from __future__ import annotations

import unittest
from unittest.mock import ANY, AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.app import app


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
            "trace_url": None,
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
                "trace_url": None,
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
        self.assertEqual(response.json(), {"detail": "Failed to process query"})
