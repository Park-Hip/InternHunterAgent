from sqlalchemy import text

from src.core.column_contract import VISIBLE_COLUMN_NAMES
from src.services.query.executor import (
    ResultTooLargeError,
    _bounded_session,
    execution_limits,
    row_bytes,
)

#: Columns fetched for one posting, in order: the frozen 16-column contract.
FULL_DETAIL_COLUMNS = ", ".join(VISIBLE_COLUMN_NAMES)


def fetch_job_details(ids: list[int]) -> list[dict]:
    if not ids:
        return []

    limits = execution_limits()
    # This column list is the frozen 16-column contract from
    # src/core/column_contract.py. The prompt's schema context is its own
    # literal declaration of the same set, and the consistency test keeps the
    # two equal. Selecting anything beyond the contract (clean_jobs also holds
    # source, external_id, posted_date, first_seen_at, last_seen_at) hands the
    # agent vocabulary it was never given and the database grant would refuse.
    #
    # The read runs through the shared bounded session, so the statement
    # timeout, the read-only transaction, and the byte budget apply here too
    # (#702 E6).
    with _bounded_session() as session:
        result = session.execute(
            text(f"SELECT {FULL_DETAIL_COLUMNS} FROM clean_jobs WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
        rows = [dict(row) for row in result.mappings().all()]
        if row_bytes(rows) > limits["max_result_bytes"]:
            raise ResultTooLargeError(
                "The query returned more data than this agent is allowed to read."
            )
        return rows
