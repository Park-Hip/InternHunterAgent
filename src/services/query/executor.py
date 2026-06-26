from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory


class ExecutorError(Exception):
    """Raised when validated SQL fails to execute against the database."""


def execute_validated_sql(sql: str) -> list[dict]:
    try:
        with session_factory() as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            result = session.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]
    except (OperationalError, DBAPIError) as exc:
        raise ExecutorError(f"Failed to execute query: {exc}") from exc
