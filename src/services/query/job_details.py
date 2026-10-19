from sqlalchemy import text

from src.services.query.executor import (
    ResultTooLargeError,
    _bounded_session,
    execution_limits,
    row_bytes,
)

#: Columns fetched for one posting, in order: the frozen 16-column contract.
FULL_DETAIL_COLUMNS = (
    "id, title, company, role, description, tech_stack, "
    "location, source_url, job_level, listing_expires_on, created_on, "
    "is_internship, salary_min, salary_max, salary_currency, "
    "is_salary_negotiable"
)


def fetch_job_details(ids: list[int]) -> list[dict]:
    if not ids:
        return []

    limits = execution_limits()
    # This column list mirrors config/prompts.yaml -> prompts.schema_context,
    # the 16-column frozen contract, in that file's own order. The two must
    # change together: schema_context tells the model "unlisted columns do not
    # exist in this schema", while this query decides what the model actually
    # receives. Selecting anything beyond the contract (clean_jobs also holds
    # first_seen_at, last_seen_at, posted_date, source, external_id)
    # hands the agent vocabulary it was never given and never calibrated for.
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
