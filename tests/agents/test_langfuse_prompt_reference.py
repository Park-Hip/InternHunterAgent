from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langfuse.api import NotFoundError

from src.agents.tracing import langfuse


@pytest.fixture(autouse=True)
def _reset_sql_generation_prompt_missing_guard() -> None:
    """Reset the module-level negative-cache guard so tests do not contaminate

    each other regardless of execution order.
    """
    langfuse._sql_generation_prompt_missing = False
    yield
    langfuse._sql_generation_prompt_missing = False


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
        fetch_timeout_seconds=3,
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


@pytest.mark.asyncio
async def test_sql_prompt_reference_stops_retrying_after_not_found_error() -> None:
    client = MagicMock()
    client.get_prompt.side_effect = NotFoundError(body="prompt not found")

    with (
        patch.object(langfuse, "get_langfuse_client", return_value=client),
        patch.object(langfuse.logger, "warning") as warning,
    ):
        assert await langfuse.get_sql_generation_prompt_reference() is None
        assert await langfuse.get_sql_generation_prompt_reference() is None

    client.get_prompt.assert_called_once()
    warning.assert_called_once()


@pytest.mark.asyncio
async def test_sql_prompt_reference_retries_after_transient_error() -> None:
    client = MagicMock()
    reference = SimpleNamespace(name="resumi-sql-generation", version=4)
    client.get_prompt.side_effect = [TimeoutError("timed out"), reference]

    with patch.object(langfuse, "get_langfuse_client", return_value=client):
        assert await langfuse.get_sql_generation_prompt_reference() is None
        assert await langfuse.get_sql_generation_prompt_reference() is reference

    assert client.get_prompt.call_count == 2
