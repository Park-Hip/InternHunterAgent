from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.agents.runtime.provider import ProviderCredentialError
from src.api.app import create_app
from src.api.schema_guard import SchemaGuardError
from src.serving import composition

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# A fresh interpreter imports the entrypoint the way uvicorn does. Configuration is
# loaded before every other import, so the run fails fast without paying for the
# LangChain, LiteLLM, and FastMCP import chain. Two settings make the failure real
# rather than environmental: the required variables are removed from the child
# environment, and the `.env` file source is switched off, because a developer's
# `.env` (the documented local setup) would otherwise supply the very DSNs this
# test removes and the import would succeed. The child runs from an empty
# directory so no `.env` beside the working directory can be picked up either.
IMPORT_WITH_BAD_CONFIG = textwrap.dedent(
    """
    import src.core.config as config

    config.Settings.model_config["env_file"] = None

    from src.serving import composition  # noqa: F401
    """
)


class StartupConfigTests(unittest.TestCase):
    def test_import_fails_fast_when_config_load_fails(self) -> None:
        # Configuration is the import-time contract (#640): uvicorn loads
        # `src.serving.composition:app`, `load_settings()` runs, and a bad config
        # kills the process before the lifespan exists. This exercises that real
        # path rather than patching a call that cannot fail.
        env = dict(os.environ)
        env.pop("DATABASE_URL", None)
        env.pop("AGENT_DATABASE_URL", None)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(PROJECT_ROOT), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

        with tempfile.TemporaryDirectory() as empty_cwd:
            result = subprocess.run(
                [sys.executable, "-c", IMPORT_WITH_BAD_CONFIG],
                env=env,
                capture_output=True,
                text=True,
                cwd=empty_cwd,
            )

        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("ConfigLoadError", result.stderr)
        self.assertIn("DATABASE_URL", result.stderr)
        self.assertIn("AGENT_DATABASE_URL", result.stderr)
        # The refusal is composition's own module body, so the traceback names it:
        # the app object and the lifespan are never defined.
        self.assertIn("composition.py", result.stderr)

    def test_lifespan_fails_before_pool_when_schema_guard_fails(self) -> None:
        with (
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

    def test_lifespan_fails_before_pool_when_a_served_key_is_missing(self) -> None:
        with (
            patch("src.serving.composition.assert_serving_schema"),
            patch("src.serving.composition.assert_agent_privileges"),
            patch("src.serving.composition.build_checkpointer_pool") as build_pool,
            patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}),
        ):
            with self.assertRaises(ProviderCredentialError) as ctx:
                with TestClient(composition.app):
                    pass

        self.assertIn("agent.react.deployment", str(ctx.exception))
        self.assertIn("DEEPSEEK_API_KEY is unset or empty", str(ctx.exception))
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

        async def prefetch() -> None:
            events.append("prompt prefetch")

        def credentials_guard() -> None:
            events.append("credential guard")

        async def discover_tools(_mcp_server: object) -> list:
            events.append("tool discovery")
            return []

        async def diagnose() -> None:
            events.append("langfuse diagnostic")

        def init() -> None:
            events.append("langfuse init")

        async def shutdown() -> None:
            events.append("langfuse shutdown")

        pool.open = AsyncMock(side_effect=pool_open)
        pool.close = AsyncMock(side_effect=pool_close)

        with (
            patch(
                "src.serving.composition.assert_serving_schema",
                side_effect=lambda: events.append("schema guard"),
            ),
            patch(
                "src.serving.composition.assert_agent_privileges",
                side_effect=lambda: events.append("privilege guard"),
            ),
            patch(
                "src.serving.composition._assert_served_profile_credentials",
                side_effect=credentials_guard,
            ),
            patch("src.serving.composition.build_checkpointer_pool", return_value=pool),
            patch(
                "src.serving.composition.build_checkpointer",
                new=AsyncMock(side_effect=build_checkpointer),
            ),
            patch(
                "src.serving.composition.prepare_native_prompts_startup",
                new=AsyncMock(side_effect=prefetch),
            ),
            patch(
                "src.serving.composition.list_job_tools",
                new=AsyncMock(side_effect=discover_tools),
            ),
            patch(
                "src.serving.composition.AgentRuntime",
                side_effect=lambda **_: (
                    events.append("runtime construction") or object()
                ),
            ),
            patch(
                "src.serving.composition.init_langfuse",
                side_effect=init,
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
                "schema guard",
                "privilege guard",
                "credential guard",
                "pool open",
                "langfuse init",
                "checkpointer setup",
                "prompt prefetch",
                "tool discovery",
                "runtime construction",
                "langfuse diagnostic",
                "langfuse shutdown",
                "pool close",
            ],
        )
