from unittest.mock import AsyncMock, patch

import pytest
from psycopg_pool import AsyncConnectionPool

from src.core.checkpointer import _checkpointer_dsn, build_checkpointer, build_checkpointer_pool


def test_checkpointer_dsn_strips_sqlalchemy_driver_suffix() -> None:
    dsn = _checkpointer_dsn()

    assert "+psycopg" not in dsn
    assert dsn.startswith("postgresql://")


def test_build_checkpointer_pool_uses_required_kwargs() -> None:
    pool = build_checkpointer_pool()

    assert pool.kwargs["autocommit"] is True
    assert pool.kwargs["prepare_threshold"] == 0
    assert "+psycopg" not in pool.conninfo
    assert pool._check is AsyncConnectionPool.check_connection


@pytest.mark.asyncio
async def test_build_checkpointer_runs_setup_once() -> None:
    fake_pool = AsyncMock()

    with patch("src.core.checkpointer.AsyncPostgresSaver") as mock_saver_cls:
        mock_saver = mock_saver_cls.return_value
        mock_saver.setup = AsyncMock()

        checkpointer = await build_checkpointer(fake_pool)

    mock_saver_cls.assert_called_once_with(fake_pool)
    mock_saver.setup.assert_awaited_once()
    assert checkpointer is mock_saver
