from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory
from src.services.ingestion.models import CleanJob, NormalizedJob


class CleanStoreError(Exception):
    """Raised when a clean_jobs upsert or expiry pass fails at the database layer."""


def upsert_clean_jobs(jobs: Iterable[NormalizedJob]) -> int:
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
            "listing_expires_on": j.listing_expires_on,
            "created_on": j.created_on,
            "is_internship": j.is_internship,
            "salary_min": j.salary_min,
            "salary_max": j.salary_max,
            "salary_currency": j.salary_currency,
            "is_salary_negotiable": j.is_salary_negotiable,
        }
        for j in jobs
    ]

    # Postgres ON CONFLICT DO UPDATE cannot affect the same key twice in one
    # statement, so a batch with a duplicate (source, external_id) would crash.
    # Dedup here, keeping the last occurrence (last-write-wins for a refresh).
    deduped: dict[tuple[object, object], dict] = {}
    for row in rows:
        deduped[(row["source"], row["external_id"])] = row
    rows = list(deduped.values())

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
            "listing_expires_on": insert(CleanJob).excluded.listing_expires_on,
            "created_on": insert(CleanJob).excluded.created_on,
            "is_internship": insert(CleanJob).excluded.is_internship,
            "salary_min": insert(CleanJob).excluded.salary_min,
            "salary_max": insert(CleanJob).excluded.salary_max,
            "salary_currency": insert(CleanJob).excluded.salary_currency,
            "is_salary_negotiable": insert(CleanJob).excluded.is_salary_negotiable,
            "last_seen_at": text("now()"),
            "is_active": text("true"),
        },
    )

    try:
        with session_factory() as session:
            session.execute(stmt)
            session.commit()
    except (OperationalError, DBAPIError) as exc:
        raise CleanStoreError(f"Failed to upsert clean jobs: {exc}") from exc

    return len(rows)


def expire_stale_clean_jobs(expire_after_days: int) -> int:
    """Soft-expire postings unseen for N consecutive days. Never deletes rows.

    Time-based only — a posting flips is_active=false purely because
    last_seen_at has aged past the window, never because it was absent from a
    single run. Rollback: clean_jobs can always be rebuilt from raw_jobs via
    to_normalized_job + upsert_clean_jobs, since raw_jobs is never truncated.
    """
    stmt = text(
        "UPDATE clean_jobs"
        " SET is_active = false"
        " WHERE last_seen_at < now() - make_interval(days => :days)"
    )

    try:
        with session_factory() as session:
            result = session.execute(stmt, {"days": expire_after_days})
            session.commit()
    except (OperationalError, DBAPIError) as exc:
        raise CleanStoreError(f"Failed to expire stale clean jobs: {exc}") from exc

    return result.rowcount
