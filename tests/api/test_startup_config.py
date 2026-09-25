from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.schema_guard import SchemaGuardError
from src.core.config import ConfigLoadError
from src.serving import composition


class StartupConfigTests(unittest.TestCase):
    def test_lifespan_fails_fast_when_config_load_fails(self) -> None:
        with patch(
            "src.serving.composition.load_settings",
            side_effect=ConfigLoadError("bad config"),
        ):
            with self.assertRaises(ConfigLoadError) as ctx:
                with TestClient(composition.app):
                    pass

        self.assertIn("bad config", str(ctx.exception))

    def test_lifespan_fails_before_pool_when_schema_guard_fails(self) -> None:
        with (
            patch("src.serving.composition.load_settings"),
            patch(
                "src.serving.composition.assert_serving_schema",
                side_effect=SchemaGuardError("clean_jobs drift"),
            ),
            patch("src.serving.composition.build_checkpointer_pool") as build_pool,
        ):
            with self.assertRaises(SchemaGuardError, msg="clean_jobs drift"):
                with TestClient(composition.app):
                    pass

        build_pool.assert_not_called()

    def test_lifespan_preserves_dependency_lifecycle_order(self) -> None:
        events: list[str] = []
        pool = MagicMock()

        async def pool_open() -> None:
            events.append("pool open")

        async def pool_close() -> None:
            events.append("pool close")

        async def build_checkpointer(_pool: MagicMock) -> object:
            events.append("checkpointer setup")
            return object()

        async def diagnose() -> None:
            events.append("langfuse diagnostic")

        async def shutdown() -> None:
            events.append("langfuse shutdown")

        pool.open = AsyncMock(side_effect=pool_open)
        pool.close = AsyncMock(side_effect=pool_close)

        with (
            patch(
                "src.serving.composition.load_settings",
                side_effect=lambda: events.append("settings load"),
            ),
            patch(
                "src.serving.composition.assert_serving_schema",
                side_effect=lambda: events.append("schema guard"),
            ),
            patch("src.serving.composition.build_checkpointer_pool", return_value=pool),
            patch(
                "src.serving.composition.build_checkpointer",
                new=AsyncMock(side_effect=build_checkpointer),
            ),
            patch(
                "src.serving.composition.agent_factory",
                side_effect=lambda **_: events.append("runtime construction") or object(),
            ),
            patch(
                "src.serving.composition.diagnose_langfuse_startup",
                new=AsyncMock(side_effect=diagnose),
            ),
            patch(
                "src.serving.composition.shutdown_langfuse",
                new=AsyncMock(side_effect=shutdown),
            ),
        ):
            with TestClient(
                create_app(lifespan=composition.lifespan, docs_enabled=False)
            ):
                pass

        self.assertEqual(
            events,
            [
                "settings load",
                "schema guard",
                "pool open",
                "checkpointer setup",
                "runtime construction",
                "langfuse diagnostic",
                "langfuse shutdown",
                "pool close",
            ],
        )
