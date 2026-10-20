"""Boot-time schema guard for the serving (read) path.

Fails the FastAPI boot loudly if a column the serving path relies on is missing
or has changed type, instead of erroring mid-query on a renamed column.

The guard deliberately tolerates extra physical columns. Since ADR-0063 the
agent reads through a role that holds column-level ``SELECT`` on exactly the 16
visible columns, so a column this guard does not know is already invisible to
the agent. Refusing boot on one used to turn every additive migration into an
outage: migrations deploy separately from code, and the next restart demanded a
release whose frozen column literal already listed the new column. The
complete contract now lives in ``src.core.column_contract``.
"""

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.column_contract import CONTRACT_COLUMN_NAMES, VISIBLE_COLUMN_TYPES
from src.core.db import session_factory
from src.core.logger import logger


class SchemaGuardError(RuntimeError):
    """Raised when the serving-path clean_jobs schema check fails. Aborts boot."""


def assert_serving_schema() -> None:
    """Check the visible clean_jobs columns and their PostgreSQL types.

    Raises SchemaGuardError naming the missing or retyped columns. Extra
    physical columns are logged and ignored: the agent grant, not this guard,
    keeps them out of an answer.
    """
    stmt = text(
        "SELECT column_name, data_type FROM information_schema.columns"
        " WHERE table_name = 'clean_jobs' AND table_schema = 'public'"
    )

    try:
        with session_factory() as session:
            actual = {row[0]: row[1] for row in session.execute(stmt)}
    except (OperationalError, DBAPIError) as exc:
        raise SchemaGuardError(f"Failed to inspect clean_jobs schema: {exc}") from exc

    if not actual:
        raise SchemaGuardError(
            "clean_jobs table not found in the database (information_schema query "
            "returned no columns) - refusing to serve"
        )

    missing = sorted(set(VISIBLE_COLUMN_TYPES) - set(actual))
    wrong_types = sorted(
        (name, expected, actual[name])
        for name, expected in VISIBLE_COLUMN_TYPES.items()
        if name in actual and actual[name] != expected
    )
    extra = sorted(set(actual) - CONTRACT_COLUMN_NAMES)

    if missing or wrong_types:
        logger.error(
            "api.schema_drift",
            missing=missing,
            wrong_types=[list(item) for item in wrong_types],
        )
        raise SchemaGuardError(
            f"clean_jobs schema drift detected: missing={missing} "
            f"wrong_type={wrong_types}"
        )

    if extra:
        logger.info("api.schema_extra_columns", columns=extra)
    logger.info(
        "api.schema_ok",
        columns=len(VISIBLE_COLUMN_TYPES),
        extra_columns=len(extra),
    )
