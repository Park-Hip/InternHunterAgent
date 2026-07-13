from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.errors import BUSY_MESSAGE


class RateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(rate_limit="2/minute")
        self.app.state.runtime = AsyncMock()
        self.client = TestClient(self.app)

    def test_chat_limit_returns_friendly_429(self) -> None:
        fake_response = {
            "answer": "ok",
            "session_id": "session-123",
            "trace_id": None,
            "trace_url": None,
        }

        with patch(
            "src.api.routes.query.generate_agent_response",
            new=AsyncMock(return_value=fake_response),
        ):
            first = self.client.post("/api/v1/agent/chat", json={"query": "one"})
            second = self.client.post("/api/v1/agent/chat", json={"query": "two"})
            limited = self.client.post("/api/v1/agent/chat", json={"query": "three"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json(), {"detail": BUSY_MESSAGE})
        self.assertNotIn("Rate limit exceeded", limited.text)

    def test_health_is_not_rate_limited(self) -> None:
        responses = [self.client.get("/api/v1/health") for _ in range(5)]

        self.assertTrue(all(response.status_code == 200 for response in responses))
