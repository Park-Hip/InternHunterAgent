from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.routes.health import get_data_snapshot_date


class ReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(rate_limit="2/minute")
        self.app.state.runtime = AsyncMock()
        self.client = TestClient(self.app)

    def test_ready_returns_ok_with_snapshot_date(self) -> None:
        with patch("src.api.routes.health._select_one", return_value=None):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "data_snapshot_date": get_data_snapshot_date()},
        )

    def test_ready_returns_503_when_db_check_fails(self) -> None:
        with patch("src.api.routes.health._select_one", side_effect=RuntimeError("down")):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error"})

    def test_ready_is_not_rate_limited(self) -> None:
        with patch("src.api.routes.health._select_one", return_value=None):
            responses = [self.client.get("/api/v1/ready") for _ in range(5)]

        self.assertTrue(all(response.status_code == 200 for response in responses))

    def test_ready_surfaces_configured_snapshot_date(self) -> None:
        with patch("src.api.routes.health._select_one", return_value=None):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data_snapshot_date"], "2026-07-14")


if __name__ == "__main__":
    unittest.main()
