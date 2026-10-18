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

        with (
            patch.object(langfuse, "get_langfuse_client", return_value=client),
            patch.object(
                langfuse,
                "_fetch_project_id",
                side_effect=RuntimeError("invalid credentials"),
            ),
            patch.object(langfuse.logger, "warning") as warning,
        ):
            await langfuse.diagnose_langfuse_startup()

        warning.assert_called_once_with(
            "Langfuse startup authentication failed", error="invalid credentials"
        )

    async def test_startup_resolution_caches_the_project_id(self) -> None:
        client = MagicMock()

        with (
            patch.object(langfuse, "_project_id", None),
            patch.object(langfuse, "get_langfuse_client", return_value=client),
            patch.object(
                langfuse, "_fetch_project_id", return_value="project-1"
            ) as fetch,
            patch.object(langfuse.logger, "info") as info,
        ):
            await langfuse.diagnose_langfuse_startup()

            self.assertEqual(langfuse._project_id, "project-1")

        fetch.assert_called_once_with(client)
        info.assert_called_once_with("Langfuse startup authentication succeeded")

    async def test_startup_resolution_without_a_project_id_warns(self) -> None:
        client = MagicMock()

        with (
            patch.object(langfuse, "_project_id", None),
            patch.object(langfuse, "get_langfuse_client", return_value=client),
            patch.object(langfuse, "_fetch_project_id", return_value=None),
            patch.object(langfuse.logger, "warning") as warning,
        ):
            await langfuse.diagnose_langfuse_startup()

            self.assertIsNone(langfuse._project_id)

        warning.assert_called_once_with("Langfuse startup authentication failed")

    async def test_startup_resolution_is_skipped_when_tracing_is_disabled(
        self,
    ) -> None:
        with (
            patch.object(langfuse, "get_langfuse_client", return_value=None),
            patch.object(langfuse, "_fetch_project_id") as fetch,
            patch.object(langfuse.logger, "info") as info,
        ):
            await langfuse.diagnose_langfuse_startup()

        fetch.assert_not_called()
        info.assert_called_once_with(
            "Langfuse startup authentication skipped: tracing disabled"
        )

    async def test_shutdown_drains_the_initialized_client(self) -> None:
        client = MagicMock()

        with patch.object(langfuse, "get_langfuse_client", return_value=client):
            await langfuse.shutdown_langfuse()

        client.shutdown.assert_called_once()

    async def test_shutdown_is_a_noop_when_tracing_is_disabled(self) -> None:
        with (
            patch.object(langfuse, "get_langfuse_client", return_value=None),
            patch.object(langfuse, "_project_id", "project-1"),
        ):
            await langfuse.shutdown_langfuse()

            self.assertIsNone(langfuse._project_id)

    async def test_shutdown_clears_state_so_a_later_init_starts_fresh(self) -> None:
        client = MagicMock()

        with (
            patch.object(langfuse, "_langfuse", client),
            patch.object(langfuse, "_langfuse_handler", MagicMock()),
            patch.object(langfuse, "_project_id", "project-1"),
        ):
            await langfuse.shutdown_langfuse()

            client.shutdown.assert_called_once_with()
            self.assertIsNone(langfuse.get_langfuse_client())
            self.assertIsNone(langfuse.get_langfuse_handler())
            self.assertIsNone(langfuse._project_id)

    async def test_shutdown_clears_state_even_when_draining_fails(self) -> None:
        client = MagicMock()
        client.shutdown.side_effect = RuntimeError("drain failed")

        with (
            patch.object(langfuse, "_langfuse", client),
            patch.object(langfuse, "_langfuse_handler", MagicMock()),
            patch.object(langfuse, "_project_id", "project-1"),
            patch.object(langfuse.logger, "warning") as warning,
        ):
            await langfuse.shutdown_langfuse()

            self.assertIsNone(langfuse.get_langfuse_client())
            self.assertIsNone(langfuse.get_langfuse_handler())
            self.assertIsNone(langfuse._project_id)

        warning.assert_called_once_with(
            "Langfuse shutdown failed", error="drain failed"
        )


class LangfuseTraceUrlTests(unittest.TestCase):
    """#699: the trace URL comes from cached state, never from request-path I/O."""

    def test_returns_none_without_a_trace_id(self) -> None:
        with (
            patch.object(langfuse, "_project_id", "project-1"),
            patch.object(
                langfuse,
                "settings",
                SimpleNamespace(LANGFUSE_BASE_URL="https://langfuse.example"),
            ),
        ):
            self.assertIsNone(langfuse.langfuse_trace_url(trace_id=None))

    def test_returns_none_without_a_resolved_project_id(self) -> None:
        with (
            patch.object(langfuse, "_project_id", None),
            patch.object(
                langfuse,
                "settings",
                SimpleNamespace(LANGFUSE_BASE_URL="https://langfuse.example"),
            ),
        ):
            self.assertIsNone(langfuse.langfuse_trace_url(trace_id="trace-1"))

    def test_returns_none_without_a_base_url(self) -> None:
        with (
            patch.object(langfuse, "_project_id", "project-1"),
            patch.object(
                langfuse, "settings", SimpleNamespace(LANGFUSE_BASE_URL=None)
            ),
        ):
            self.assertIsNone(langfuse.langfuse_trace_url(trace_id="trace-1"))

    def test_builds_the_url_from_config_without_touching_the_client(self) -> None:
        with (
            patch.object(langfuse, "_project_id", "project-1"),
            patch.object(
                langfuse,
                "settings",
                SimpleNamespace(LANGFUSE_BASE_URL="https://langfuse.example"),
            ),
            patch.object(langfuse, "get_langfuse_client") as get_client,
        ):
            url = langfuse.langfuse_trace_url(trace_id="trace-1")

        self.assertEqual(
            url, "https://langfuse.example/project/project-1/traces/trace-1"
        )
        get_client.assert_not_called()

    def test_matches_the_sdk_url_for_the_same_configuration(self) -> None:
        """The literal string is what the SDK's `get_trace_url` produced before #699."""
        settings = SimpleNamespace(
            LANGFUSE_PUBLIC_KEY="pk-lf-trace-url-parity",
            LANGFUSE_SECRET_KEY="sk-lf-trace-url-parity",
            LANGFUSE_BASE_URL="https://langfuse.example",
        )
        with (
            patch.object(langfuse, "settings", settings),
            patch.object(langfuse, "get_langfuse_environment", return_value="test"),
            patch.object(langfuse, "get_langfuse_release", return_value=None),
        ):
            client = langfuse.create_langfuse_client()

        try:
            # A seeded project id keeps the SDK's own lookup network-free.
            client._project_id = "project-1"
            sdk_url = client.get_trace_url(trace_id="trace-1")

            with (
                patch.object(langfuse, "_project_id", "project-1"),
                patch.object(langfuse, "settings", settings),
            ):
                url = langfuse.langfuse_trace_url(trace_id="trace-1")

            self.assertEqual(url, sdk_url)
        finally:
            client.shutdown()


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
