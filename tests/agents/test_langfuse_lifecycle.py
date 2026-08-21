from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.agents.tracing import langfuse


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
