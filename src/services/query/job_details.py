from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory
from src.services.query.executor import ExecutorError


def fetch_job_details(ids: list[int]) -> list[dict]:
    if not ids:
        return []

    try:
        with session_factory() as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            result = session.execute(
                text("SELECT * FROM clean_jobs WHERE id = ANY(:ids)"), {"ids": ids}
            )
            return [dict(row) for row in result.mappings().all()]
    except (OperationalError, DBAPIError) as exc:
        raise ExecutorError(f"Failed to execute query: {exc}") from exc
