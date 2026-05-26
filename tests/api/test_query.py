from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.app import app


class QueryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_query_route_returns_structured_response(self) -> None:
        fake_response = {
            "answer": "The current time is 14:01:52.",
            "trace_id": None,
            "trace_url": None,
        }

        with patch(
            "src.api.routes.query.generate_agent_response",
            new=AsyncMock(return_value=fake_response),
        ) as mock_generate:
            response = self.client.post(
                "/api/v1/agent/query",
                json={"query": "what time is it?", "session_id": "session-123"},
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
        mock_generate.assert_awaited_once_with("what time is it?")
