from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.core.config import settings


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
        },
        open=False,
    )


async def build_checkpointer(pool: AsyncConnectionPool) -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
    await checkpointer.setup()
    return checkpointer
