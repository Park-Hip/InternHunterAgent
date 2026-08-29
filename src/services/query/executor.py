from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from psycopg.errors import UndefinedColumn

from src.core.db import agent_session_factory


class ExecutorError(Exception):
    """Raised when validated SQL fails to execute against the database."""


class UndefinedColumnError(ExecutorError):
    """Raised when the generated query refers to a column outside the contract."""


def execute_validated_sql(sql: str) -> list[dict]:
    try:
        with agent_session_factory() as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            result = session.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]
    except (OperationalError, DBAPIError) as exc:
        if isinstance(getattr(exc, "orig", None), UndefinedColumn):
            raise UndefinedColumnError("Query referenced an unavailable column") from exc
        raise ExecutorError(f"Failed to execute query: {exc}") from exc
