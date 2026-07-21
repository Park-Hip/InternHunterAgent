from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app


class ReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(rate_limit="2/minute")
        self.app.state.runtime = AsyncMock()
        self.client = TestClient(self.app)

    def test_ready_returns_ok_with_snapshot_date(self) -> None:
        with patch("src.api.routes.health._select_one", return_value=None), patch(
            "src.api.routes.health._select_max_last_seen", return_value=date(2026, 7, 19)
        ):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "data_snapshot_date": "2026-07-19"},
        )

    def test_ready_returns_503_when_db_check_fails(self) -> None:
        with patch("src.api.routes.health._select_one", side_effect=RuntimeError("down")):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error"})

    def test_ready_is_not_rate_limited(self) -> None:
        with patch("src.api.routes.health._select_one", return_value=None), patch(
            "src.api.routes.health._select_max_last_seen", return_value=None
        ):
            responses = [self.client.get("/api/v1/ready") for _ in range(5)]

        self.assertTrue(all(response.status_code == 200 for response in responses))

    def test_ready_surfaces_configured_snapshot_date(self) -> None:
        """Empty clean_jobs (no MAX) falls back to the configured demo date."""
        with patch("src.api.routes.health._select_one", return_value=None), patch(
            "src.api.routes.health._select_max_last_seen", return_value=None
        ):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data_snapshot_date"], "2026-07-14")

    def test_ready_surfaces_max_last_seen_date(self) -> None:
        with patch("src.api.routes.health._select_one", return_value=None), patch(
            "src.api.routes.health._select_max_last_seen", return_value=date(2026, 7, 19)
        ):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data_snapshot_date"], "2026-07-19")

    def test_ready_falls_back_when_date_query_raises(self) -> None:
        with patch("src.api.routes.health._select_one", return_value=None), patch(
            "src.api.routes.health._select_max_last_seen", side_effect=RuntimeError("no table")
        ):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["data_snapshot_date"], "2026-07-14")

    def test_ready_skips_date_query_when_db_check_fails(self) -> None:
        with patch("src.api.routes.health._select_one", side_effect=RuntimeError("down")), patch(
            "src.api.routes.health._select_max_last_seen"
        ) as max_last_seen:
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error"})
        self.assertNotIn("data_snapshot_date", response.json())
        max_last_seen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
