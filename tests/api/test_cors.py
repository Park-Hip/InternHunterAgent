from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from src.api.app import create_app


class CorsMiddlewareTests(unittest.TestCase):
    def test_allowed_origin_preflight_returns_cors_headers(self) -> None:
        app = create_app(
            cors_config={
                "allowed_origins": ["http://localhost:5173"],
                "allow_credentials": False,
                "allowed_methods": ["GET", "POST", "OPTIONS"],
                "allowed_headers": ["*"],
            }
        )
        client = TestClient(app)

        response = client.options(
            "/api/v1/agent/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )
        self.assertIn("POST", response.headers.get("access-control-allow-methods", ""))

    def test_disallowed_origin_preflight_omits_allow_origin_header(self) -> None:
        app = create_app(
            cors_config={
                "allowed_origins": ["http://localhost:5173"],
                "allow_credentials": False,
                "allowed_methods": ["GET", "POST", "OPTIONS"],
                "allowed_headers": ["*"],
            }
        )
        client = TestClient(app)

        response = client.options(
            "/api/v1/agent/chat",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.headers.get("access-control-allow-origin"))
