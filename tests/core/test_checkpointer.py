import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from evals.fixtures.loader import (
    fixture_database_endpoint,
    fixture_database_reachable,
    fixture_database_url,
)
from src.core import checkpointer as checkpointer_module
from src.core import db as db_module
from src.core.checkpointer import (
    _checkpointer_dsn,
    build_checkpointer,
    build_checkpointer_pool,
    delete_stale_threads,
)
from src.core.db import connect_timeout_seconds


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
    assert pool.kwargs["connect_timeout"] == connect_timeout_seconds()


@pytest.mark.asyncio
async def test_pool_open_does_not_wait_for_an_unreachable_database(monkeypatch) -> None:
    """Issue #642: without `wait=True`, `open()` starts workers and returns.

    The pool's own 30 s acquisition timeout and its 5 s close timeout stay the
    outer bounds; the connect attempts themselves carry the configured bound.
    """

    class _Unreachable:
        DATABASE_URL = "postgresql+psycopg://u:p@127.0.0.1:1/db"
        config_yaml = {"database": {"connect_timeout_seconds": 1}}

    monkeypatch.setattr(checkpointer_module, "settings", _Unreachable())
    monkeypatch.setattr(db_module, "settings", _Unreachable())

    pool = build_checkpointer_pool()
    started = time.monotonic()
    await pool.open()
    try:
        assert time.monotonic() - started < 5
    finally:
        await pool.close()


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


RETENTION_DAYS = 30
_CHECKPOINT_TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")


async def _count_thread_rows(
    pool: AsyncConnectionPool, table: str, thread_id: str
) -> int:
    async with pool.connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                f"SELECT count(*) AS n FROM {table} WHERE thread_id = %s",
                (thread_id,),
            )
            row = await cursor.fetchone()
    assert row is not None
    return int(row["n"])


async def _write_turn(
    saver: AsyncPostgresSaver, thread_id: str, *, at: datetime
) -> None:
    """Write one checkpoint of a thread, with a blob row and a write row."""
    checkpoint = empty_checkpoint()
    checkpoint["ts"] = at.isoformat()
    checkpoint["channel_versions"] = {"messages": "v1"}
    checkpoint["channel_values"] = {"messages": [{"role": "human", "content": "hi"}]}
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    config = await saver.aput(config, checkpoint, {"source": "input"}, {"messages": "v1"})
    await saver.aput_writes(
        config, [("tools", [{"name": "query_clean_jobs"}])], task_id="task-1"
    )


async def _sweep_scenario() -> None:
    now = datetime.now(timezone.utc)
    stale_id = f"retention-stale-{uuid4().hex}"
    fresh_id = f"retention-fresh-{uuid4().hex}"
    reactivated_id = f"retention-reactivated-{uuid4().hex}"

    pool = build_checkpointer_pool()
    await pool.open()
    try:
        saver = await build_checkpointer(pool)
        try:
            await _write_turn(
                saver, stale_id, at=now - timedelta(days=RETENTION_DAYS + 1)
            )
            await _write_turn(saver, fresh_id, at=now - timedelta(minutes=5))
            # The newest checkpoint decides: an old turn followed by a recent one
            # keeps the whole thread.
            await _write_turn(
                saver, reactivated_id, at=now - timedelta(days=RETENTION_DAYS + 1)
            )
            await _write_turn(saver, reactivated_id, at=now - timedelta(minutes=5))

            deleted = await delete_stale_threads(saver, retention_days=RETENTION_DAYS)

            assert stale_id in deleted
            assert fresh_id not in deleted
            assert reactivated_id not in deleted
            for table in _CHECKPOINT_TABLES:
                assert await _count_thread_rows(pool, table, stale_id) == 0
                assert await _count_thread_rows(pool, table, fresh_id) >= 1
                assert await _count_thread_rows(pool, table, reactivated_id) >= 1
        finally:
            for thread_id in (stale_id, fresh_id, reactivated_id):
                await saver.adelete_thread(thread_id)
    finally:
        await pool.close()


def test_the_sweep_deletes_only_threads_older_than_the_retention(
    monkeypatch,
) -> None:
    """The verification plan of #673, against a real checkpointer and database."""
    if not fixture_database_reachable():
        host, port = fixture_database_endpoint()
        pytest.skip(
            f"Fixture Postgres is not reachable at {host}:{port}; start it with "
            "`docker compose up -d postgres`. A skipped retention check is not a pass."
        )

    class _FixtureDatabase:
        DATABASE_URL = fixture_database_url()

    monkeypatch.setattr(checkpointer_module, "settings", _FixtureDatabase())

    # psycopg's async I/O refuses native Windows' default Proactor loop, so this
    # test owns its loop, like scripts/capture_stream_error.py does. Production
    # runs on Linux, where the default loop is already selector-based.
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(_sweep_scenario())
