from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver, Conn

from src.core.config import settings
from src.core.db import connect_timeout_seconds


def _checkpointer_dsn() -> str:
    return settings.DATABASE_URL.replace("+psycopg", "")


def build_checkpointer_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(
        conninfo=_checkpointer_dsn(),
        check=AsyncConnectionPool.check_connection,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
            # Background worker connects carry the same service-owned bound as the
            # engines. This does not make `open()` wait: called without `wait=True`
            # it only starts the workers, and the pool's own 30 s acquisition
            # timeout stays the outer bound (#642).
            "connect_timeout": connect_timeout_seconds(),
        },
        open=False,
    )


async def build_checkpointer(pool: AsyncConnectionPool) -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
    await checkpointer.setup()
    return checkpointer


# The retention question, answered once per sweep: which threads have no
# checkpoint newer than the cutoff. `ts` is the checkpoint's own ISO-8601
# timestamp and the tables have no timestamp column; `max` ignores rows
# without one, so a thread whose checkpoints all lack a parseable timestamp
# stays rather than being guessed at.
_STALE_THREADS_SQL = """
    SELECT thread_id
    FROM checkpoints
    GROUP BY thread_id
    HAVING max((checkpoint ->> 'ts')::timestamptz) < %(cutoff)s
"""


@asynccontextmanager
async def _connection(conn: Conn) -> AsyncIterator[AsyncConnection[DictRow]]:
    """Yield one connection for a statement, from a pool or a single connection.

    Mirrors how the saver itself reaches the database, so the sweep works
    whether a saver was built on the production pool or on one connection.
    """
    if isinstance(conn, AsyncConnectionPool):
        async with conn.connection() as pooled:
            yield pooled
    else:
        yield conn


async def delete_stale_threads(
    checkpointer: AsyncPostgresSaver, *, retention_days: int
) -> list[str]:
    """Delete every thread whose newest checkpoint is older than the retention.

    The age is read from ``checkpoint->>'ts'``; deletion goes through
    ``AsyncPostgresSaver.adelete_thread``, so each returned thread's
    checkpoints, blobs, and writes go together. Deleted threads are not
    recoverable; a client that kept its session id starts from empty memory.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    async with _connection(checkpointer.conn) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(_STALE_THREADS_SQL, {"cutoff": cutoff})
            rows = await cursor.fetchall()

    thread_ids: list[str] = [row["thread_id"] for row in rows]
    for thread_id in thread_ids:
        await checkpointer.adelete_thread(thread_id)
    return thread_ids
