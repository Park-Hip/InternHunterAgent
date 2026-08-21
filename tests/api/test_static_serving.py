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
        self.assertIn(
            "Dữ liệu thử nghiệm · chưa có ngày cập nhật · tin tuyển dụng công khai, có thể không chính xác.",
            response.text,
        )

    def test_demo_loads_pinned_same_origin_markdown_dependencies(self) -> None:
        index = self.client.get("/")
        marked = self.client.get("/vendor/marked-18.0.10.min.js")
        dompurify = self.client.get("/vendor/dompurify-3.4.14.min.js")
        app = self.client.get("/app.js")

        self.assertEqual(marked.status_code, 200)
        self.assertEqual(dompurify.status_code, 200)
        self.assertIn('src="./vendor/marked-18.0.10.min.js"', index.text)
        self.assertIn('src="./vendor/dompurify-3.4.14.min.js"', index.text)
        self.assertIn("DOMPurify.sanitize", app.text)
        self.assertIn("renderMarkdown(ctx)", app.text)


if __name__ == "__main__":
    unittest.main()
