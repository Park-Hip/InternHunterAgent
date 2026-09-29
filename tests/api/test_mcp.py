from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from src.api.app import create_app
from src.agents.mcp.job_server import mcp_endpoint_enabled


def _mcp_subapp() -> Starlette:
    """A minimal ASGI stand-in whose route lives at the endpoint path /mcp."""
    return Starlette(routes=[Route("/mcp", lambda request: PlainTextResponse("mcp-ok"))])


class McpRegistrationTests(unittest.TestCase):
    def test_mcp_endpoint_resolves_before_static_catch_all(self) -> None:
        client = TestClient(
            create_app(docs_enabled=False, mcp_app=_mcp_subapp(), mcp_path="/mcp")
        )

        self.assertEqual(client.get("/mcp").text, "mcp-ok")

    def test_root_static_still_serves_when_mcp_is_registered(self) -> None:
        client = TestClient(
            create_app(docs_enabled=True, mcp_app=_mcp_subapp(), mcp_path="/mcp")
        )

        self.assertEqual(client.get("/").status_code, 200)
        self.assertIn("InternHunter", client.get("/").text)

    def test_without_mcp_subapp_endpoint_is_not_registered(self) -> None:
        client = TestClient(create_app(docs_enabled=False))

        self.assertEqual(client.get("/mcp").status_code, 404)


class McpEndpointGateTests(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCP_ENABLED", None)
            self.assertFalse(mcp_endpoint_enabled())

    def test_enabled_by_truthy_env_value(self) -> None:
        with patch.dict(os.environ, {"MCP_ENABLED": "1"}):
            self.assertTrue(mcp_endpoint_enabled())

    def test_disabled_by_false_env_value(self) -> None:
        with patch.dict(os.environ, {"MCP_ENABLED": "0"}):
            self.assertFalse(mcp_endpoint_enabled())


if __name__ == "__main__":
    unittest.main()