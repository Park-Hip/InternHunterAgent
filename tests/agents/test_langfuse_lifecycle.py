from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.agents.tracing import langfuse

ROOT = Path(__file__).resolve().parents[2]


class LangfuseInitTests(unittest.TestCase):
    """`init_langfuse` owns creation; importing the module must not."""

    def test_init_creates_the_client_and_handler_exactly_once(self) -> None:
        settings = SimpleNamespace(
            LANGFUSE_PUBLIC_KEY="pk", LANGFUSE_SECRET_KEY="sk"
        )

        with (
            patch.dict(os.environ, {"LANGFUSE_ENABLED": "true"}),
            patch.object(langfuse, "_langfuse", None),
            patch.object(langfuse, "_langfuse_handler", None),
            patch.object(langfuse, "settings", settings),
            patch.object(langfuse, "create_langfuse_client") as create,
            patch.object(langfuse, "CallbackHandler") as handler,
        ):
            langfuse.init_langfuse()
            langfuse.init_langfuse()

            create.assert_called_once_with()
            handler.assert_called_once_with()
            self.assertIs(langfuse.get_langfuse_client(), create.return_value)
            self.assertIs(langfuse.get_langfuse_handler(), handler.return_value)

    def test_init_leaves_tracing_disabled_when_the_switch_is_off(self) -> None:
        with (
            patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}),
            patch.object(langfuse, "_langfuse", None),
            patch.object(langfuse, "_langfuse_handler", None),
            patch.object(langfuse, "create_langfuse_client") as create,
            patch.object(langfuse.logger, "info") as info,
        ):
            langfuse.init_langfuse()

            self.assertIsNone(langfuse.get_langfuse_client())

        create.assert_not_called()
        info.assert_called_once_with("Langfuse tracing disabled for this process")

    def test_init_without_credentials_warns_and_creates_nothing(self) -> None:
        settings = SimpleNamespace(
            LANGFUSE_PUBLIC_KEY="pk", LANGFUSE_SECRET_KEY=None
        )

        with (
            patch.dict(os.environ, {"LANGFUSE_ENABLED": "true"}),
            patch.object(langfuse, "_langfuse", None),
            patch.object(langfuse, "_langfuse_handler", None),
            patch.object(langfuse, "settings", settings),
            patch.object(langfuse, "create_langfuse_client") as create,
            patch.object(langfuse.logger, "warning") as warning,
        ):
            langfuse.init_langfuse()

            self.assertIsNone(langfuse.get_langfuse_client())

        create.assert_not_called()
        warning.assert_called_once_with(
            "Langfuse tracing disabled: missing Langfuse credentials"
        )

    def test_init_failure_is_logged_and_never_raised(self) -> None:
        settings = SimpleNamespace(
            LANGFUSE_PUBLIC_KEY="pk", LANGFUSE_SECRET_KEY="sk"
        )

        with (
            patch.dict(os.environ, {"LANGFUSE_ENABLED": "true"}),
            patch.object(langfuse, "_langfuse", None),
            patch.object(langfuse, "_langfuse_handler", None),
            patch.object(langfuse, "settings", settings),
            patch.object(
                langfuse,
                "create_langfuse_client",
                side_effect=RuntimeError("bad host"),
            ),
            patch.object(langfuse.logger, "warning") as warning,
        ):
            langfuse.init_langfuse()

            self.assertIsNone(langfuse.get_langfuse_client())

        warning.assert_called_once_with(
            "Langfuse tracing disabled: failed to initialize", error="bad host"
        )


class LangfuseLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_authentication_failure_is_non_fatal(self) -> None:
        client = MagicMock()
        client.auth_check.side_effect = RuntimeError("invalid credentials")

        with (
            patch.object(langfuse, "get_langfuse_client", return_value=client),
            patch.object(langfuse.logger, "warning") as warning,
        ):
            await langfuse.diagnose_langfuse_startup()

        client.auth_check.assert_called_once()
        warning.assert_called_once_with(
            "Langfuse startup authentication failed", error="invalid credentials"
        )

    async def test_shutdown_drains_the_initialized_client(self) -> None:
        client = MagicMock()

        with patch.object(langfuse, "get_langfuse_client", return_value=client):
            await langfuse.shutdown_langfuse()

        client.shutdown.assert_called_once()

    async def test_shutdown_is_a_noop_when_tracing_is_disabled(self) -> None:
        with patch.object(langfuse, "get_langfuse_client", return_value=None):
            await langfuse.shutdown_langfuse()

    async def test_shutdown_clears_state_so_a_later_init_starts_fresh(self) -> None:
        client = MagicMock()

        with (
            patch.object(langfuse, "_langfuse", client),
            patch.object(langfuse, "_langfuse_handler", MagicMock()),
        ):
            await langfuse.shutdown_langfuse()

            client.shutdown.assert_called_once_with()
            self.assertIsNone(langfuse.get_langfuse_client())
            self.assertIsNone(langfuse.get_langfuse_handler())

    async def test_shutdown_clears_state_even_when_draining_fails(self) -> None:
        client = MagicMock()
        client.shutdown.side_effect = RuntimeError("drain failed")

        with (
            patch.object(langfuse, "_langfuse", client),
            patch.object(langfuse, "_langfuse_handler", MagicMock()),
            patch.object(langfuse.logger, "warning") as warning,
        ):
            await langfuse.shutdown_langfuse()

            self.assertIsNone(langfuse.get_langfuse_client())
            self.assertIsNone(langfuse.get_langfuse_handler())

        warning.assert_called_once_with(
            "Langfuse shutdown failed", error="drain failed"
        )


class ImportSideEffectTests(unittest.TestCase):
    """#643: importing the tracing module creates nothing and logs nothing."""

    def _probe(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "from src.agents.tracing import langfuse;"
                "assert langfuse.get_langfuse_client() is None;"
                "assert langfuse.get_langfuse_handler() is None;"
                "print('no-clients')",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def _credentials_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "LANGFUSE_ENABLED": "true",
                "LANGFUSE_PUBLIC_KEY": "pk-lf-import-probe",
                "LANGFUSE_SECRET_KEY": "sk-lf-import-probe",
                "LANGFUSE_BASE_URL": "https://example.test",
            }
        )
        return env

    def test_import_creates_no_client_even_with_credentials_exported(self) -> None:
        result = self._probe(self._credentials_env())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no-clients", result.stdout)

    def test_import_neither_loads_settings_nor_logs_without_a_database(self) -> None:
        env = self._credentials_env()
        env.pop("DATABASE_URL", None)
        env.pop("AGENT_DATABASE_URL", None)

        result = self._probe(env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no-clients", result.stdout)
        self.assertEqual(result.stderr, "")
