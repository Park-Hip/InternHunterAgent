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
            "Kho dữ liệu lịch sử · ngày chụp chưa rõ · kết quả không xác nhận vị trí đang tuyển.",
            response.text,
        )

    def test_demo_marks_corpus_as_frozen_historical_snapshot(self) -> None:
        index = self.client.get("/")
        app = self.client.get("/app.js")

        self.assertNotIn("Hỏi về các vị trí AI và dữ liệu đang tuyển", index.text)
        for text in (index.text, app.text):
            self.assertIn("Kho dữ liệu lịch sử", text)
            self.assertIn("không xác nhận vị trí đang tuyển", text)
        self.assertIn("ảnh chụp ${date}", app.text)

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

    def test_conversation_is_a_live_region_in_the_served_markup(self) -> None:
        index = self.client.get("/").text

        self.assertIn('role="log"', index)
        self.assertIn('aria-live="polite"', index)
        self.assertIn('aria-relevant="additions text"', index)
        self.assertIn('aria-busy="false"', index)

    def test_composer_offers_a_stop_control(self) -> None:
        index = self.client.get("/").text
        app = self.client.get("/app.js").text

        self.assertIn('id="stop"', index)
        self.assertIn("Dừng", index)
        # Cancellation must be a real abort, not a cosmetic state change.
        self.assertIn("AbortController", app)
        self.assertIn("controller.abort()", app)

    def test_stream_is_coalesced_before_it_is_painted(self) -> None:
        app = self.client.get("/app.js").text

        self.assertIn("PAINT_INTERVAL_MS", app)
        self.assertIn("schedulePaint(ctx)", app)

    def test_client_does_not_submit_during_ime_composition(self) -> None:
        app = self.client.get("/app.js").text

        self.assertIn("e.isComposing", app)

    def test_client_no_answer_constant_matches_the_server_constant(self) -> None:
        """The no-answer card is triggered by matching the server's own constant.

        If the two drift, the card silently stops appearing. Pin them together.
        """
        from src.agents.service import FALLBACK_ANSWER

        app = self.client.get("/app.js").text

        self.assertIn("NO_ANSWER_TEXT", app)
        self.assertIn(FALLBACK_ANSWER, app)

    def test_client_handles_the_tool_event(self) -> None:
        """A `tool` event must reach a card. An unhandled event type would be
        silently dropped, which is how tool work would stay invisible."""
        app = self.client.get("/app.js").text
        styles = self.client.get("/styles.css").text

        self.assertIn('ev === "tool"', app)
        self.assertIn("upsertToolCard", app)
        self.assertIn(".toolcard", styles)

    def test_tool_event_is_part_of_the_published_stream_contract(self) -> None:
        """The union in schemas.py is what the OpenAPI document publishes, so a
        new event type must appear in the schema, not only in the code."""
        from src.api.schemas import STREAM_EVENT_SCHEMA

        schema = str(STREAM_EVENT_SCHEMA)
        self.assertIn("StreamToolEvent", schema)

    def test_tool_event_rejects_statuses_outside_the_contract(self) -> None:
        import pydantic

        from src.api.schemas import StreamToolEvent

        with self.assertRaises(pydantic.ValidationError):
            StreamToolEvent(type="tool", name="x", status="exploded")


if __name__ == "__main__":
    unittest.main()
