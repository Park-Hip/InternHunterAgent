from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app, create_app
from src.core.config import ConfigLoadError


class StartupConfigTests(unittest.TestCase):
    def test_lifespan_fails_fast_when_config_load_fails(self) -> None:
        with patch("src.api.app.load_settings", side_effect=ConfigLoadError("bad config")):
            with self.assertRaises(ConfigLoadError) as ctx:
                with TestClient(app):
                    pass

        self.assertIn("bad config", str(ctx.exception))

    def test_lifespan_checks_tracing_without_blocking_shutdown(self) -> None:
        pool = MagicMock()
        pool.open = AsyncMock()
        pool.close = AsyncMock()

        with (
            patch("src.api.app.load_settings"),
            patch("src.api.app.assert_serving_schema"),
            patch("src.api.app.build_checkpointer_pool", return_value=pool),
            patch("src.api.app.build_checkpointer", new=AsyncMock()),
            patch("src.api.app.agent_factory", return_value=object()),
            patch("src.api.app.diagnose_langfuse_startup", new=AsyncMock()) as diagnose,
            patch("src.api.app.shutdown_langfuse", new=AsyncMock()) as shutdown,
        ):
            with TestClient(create_app(docs_enabled=False)):
                pass

        diagnose.assert_awaited_once()
        shutdown.assert_awaited_once()
        pool.open.assert_awaited_once()
        pool.close.assert_awaited_once()
