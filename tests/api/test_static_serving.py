from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import create_app


class StaticServingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(docs_enabled=True))

    def test_root_serves_placeholder_index(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("InternHunter", response.text)

    def test_docs_are_not_shadowed_by_static_mount(self) -> None:
        response = self.client.get("/docs")

        self.assertEqual(response.status_code, 200)

    def test_api_routes_are_not_shadowed_by_static_mount(self) -> None:
        with patch("src.api.routes.health._select_one", return_value=None), patch(
            "src.api.routes.health._select_max_last_seen", return_value=None
        ):
            response = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 200)

    def test_root_sets_frame_guard_header(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_demo_dateline_only_calls_a_measured_date_a_snapshot(self) -> None:
        response = self.client.get("/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data_snapshot_date_provenance === "measured"', response.text)
        self.assertIn("refresh date unavailable", response.text)


if __name__ == "__main__":
    unittest.main()
