from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from src.api.app import create_app


class DocsExposureTests(unittest.TestCase):
    def test_docs_are_exposed_when_enabled(self) -> None:
        client = TestClient(create_app(docs_enabled=True))

        self.assertEqual(client.get("/docs").status_code, 200)
        self.assertEqual(client.get("/redoc").status_code, 200)
        self.assertEqual(client.get("/openapi.json").status_code, 200)

    def test_docs_are_hidden_when_disabled(self) -> None:
        client = TestClient(create_app(docs_enabled=False))

        self.assertEqual(client.get("/docs").status_code, 404)
        self.assertEqual(client.get("/redoc").status_code, 404)
        self.assertEqual(client.get("/openapi.json").status_code, 404)
