from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agents.tracing import langfuse


@pytest.mark.asyncio
async def test_sql_prompt_reference_fetches_only_the_production_reference() -> None:
    client = MagicMock()
    reference = SimpleNamespace(name="resumi-sql-generation", version=4)
    client.get_prompt.return_value = reference

    with patch.object(langfuse, "get_langfuse_client", return_value=client):
        assert await langfuse.get_sql_generation_prompt_reference() is reference

    client.get_prompt.assert_called_once_with(
        "resumi-sql-generation",
        label="production",
        type="text",
        cache_ttl_seconds=60,
        max_retries=0,
        fetch_timeout_seconds=250,
    )


@pytest.mark.asyncio
async def test_sql_prompt_reference_is_nonfatal_when_tracing_or_remote_prompt_is_unavailable() -> (
    None
):
    with patch.object(langfuse, "get_langfuse_client", return_value=None):
        assert await langfuse.get_sql_generation_prompt_reference() is None

    client = MagicMock()
    client.get_prompt.side_effect = RuntimeError("not registered")
    with (
        patch.object(langfuse, "get_langfuse_client", return_value=client),
        patch.object(langfuse.logger, "warning") as warning,
    ):
        assert await langfuse.get_sql_generation_prompt_reference() is None

    warning.assert_called_once_with(
        "Langfuse SQL prompt reference unavailable", error="not registered"
    )
