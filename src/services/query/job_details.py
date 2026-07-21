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
            # This column list mirrors config/prompts.yaml -> prompts.schema_context,
            # the 16-column frozen contract, in that file's own order. The two must
            # change together: schema_context tells the model "unlisted columns do not
            # exist in this schema", while this query decides what the model actually
            # receives. Selecting anything beyond the contract (clean_jobs also holds
            # is_active, first_seen_at, last_seen_at, posted_date, source, external_id)
            # hands the agent vocabulary it was never given and never calibrated for.
            result = session.execute(
                text(
                    "SELECT id, title, company, role, description, tech_stack, "
                    "location, source_url, job_level, listing_expires_on, created_on, "
                    "is_internship, salary_min, salary_max, salary_currency, "
                    "is_salary_negotiable "
                    "FROM clean_jobs WHERE id = ANY(:ids)"
                ),
                {"ids": ids},
            )
            return [dict(row) for row in result.mappings().all()]
    except (OperationalError, DBAPIError) as exc:
        raise ExecutorError(f"Failed to execute query: {exc}") from exc
