from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory
from src.services.ingestion.models import CleanJob, NormalizedJob


class CleanStoreError(Exception):
    """Raised when a clean_jobs replace fails at the database layer."""


def replace_clean_jobs(jobs: Iterable[NormalizedJob]) -> int:
    rows = [
        {
            "source": j.source,
            "external_id": j.external_id,
            "source_url": j.source_url,
            "title": j.title,
            "company": j.company,
            "role": j.role,
            "description": j.description,
            "tech_stack": j.tech_stack,
            "job_level": j.job_level,
            "location": j.location,
            "posted_date": j.posted_date,
            "is_internship": j.is_internship,
            "salary_min": j.salary_min,
            "salary_max": j.salary_max,
            "salary_currency": j.salary_currency,
            "is_salary_negotiable": j.is_salary_negotiable,
        }
        for j in jobs
    ]
    if not rows:
        return 0

    stmt = insert(CleanJob).values(rows).on_conflict_do_update(
        index_elements=["source", "external_id"],
        set_={
            "source_url": insert(CleanJob).excluded.source_url,
            "title": insert(CleanJob).excluded.title,
            "company": insert(CleanJob).excluded.company,
            "role": insert(CleanJob).excluded.role,
            "description": insert(CleanJob).excluded.description,
            "tech_stack": insert(CleanJob).excluded.tech_stack,
            "job_level": insert(CleanJob).excluded.job_level,
            "location": insert(CleanJob).excluded.location,
            "posted_date": insert(CleanJob).excluded.posted_date,
            "is_internship": insert(CleanJob).excluded.is_internship,
            "salary_min": insert(CleanJob).excluded.salary_min,
            "salary_max": insert(CleanJob).excluded.salary_max,
            "salary_currency": insert(CleanJob).excluded.salary_currency,
            "is_salary_negotiable": insert(CleanJob).excluded.is_salary_negotiable,
        },
    )

    try:
        with session_factory() as session:
            session.execute(text("TRUNCATE clean_jobs"))
            session.execute(stmt)
            session.commit()
    except (OperationalError, DBAPIError) as exc:
        raise CleanStoreError(f"Failed to replace clean jobs: {exc}") from exc

    return len(rows)
