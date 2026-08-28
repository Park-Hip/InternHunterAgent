import math
from collections.abc import Iterable

import httpx
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory
from src.core.logger import logger
from src.services.ingestion.models import CleanJob, NormalizedJob


class IngestionSafetyError(Exception):
    """Raised when a pre-flight or pre-write safety check fails. The CLI exits non-zero on this."""


def assert_clean_jobs_schema() -> None:
    """Compare live clean_jobs columns against CleanJob's ORM metadata.

    Raises IngestionSafetyError naming the diff if they disagree.
    """
    stmt = text(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = 'clean_jobs' AND table_schema = 'public'"
    )

    try:
        with session_factory() as session:
            result = session.execute(stmt)
            actual = {row[0] for row in result}
    except (OperationalError, DBAPIError) as exc:
        raise IngestionSafetyError(f"Failed to inspect clean_jobs schema: {exc}") from exc

    if not actual:
        raise IngestionSafetyError(
            "clean_jobs table not found in the database (information_schema query "
            "returned no columns) — refusing to run"
        )

    expected = {c.name for c in CleanJob.__table__.columns}
    missing = expected - actual
    unexpected = actual - expected

    if missing or unexpected:
        logger.error(
            "ingestion.schema_drift",
            missing=sorted(missing),
            unexpected=sorted(unexpected),
        )
        raise IngestionSafetyError(
            f"clean_jobs schema drift detected: missing={sorted(missing)} "
            f"unexpected={sorted(unexpected)}"
        )

    logger.info("ingestion.schema_ok", columns=len(expected))


def assert_min_yield(fetched: int, min_yield: int) -> None:
    """Raise IngestionSafetyError if fetched < min_yield."""
    if fetched < min_yield:
        logger.error("ingestion.yield_floor_breached", fetched=fetched, min_yield=min_yield)
        raise IngestionSafetyError(
            f"Fetched yield below floor: fetched={fetched} min_yield={min_yield}"
        )


def assert_normalized_row_quality(jobs: Iterable[NormalizedJob]) -> None:
    """Block clean ingestion when any normalized row violates a quality invariant.

    Enforced invariants, one count per violated invariant (never per violating
    row, so the log cannot leak posting identifiers):

    - title/company required: neither may be empty or whitespace-only.
    - salary bounds: when both bounds are present, min must not exceed max.
    - finite salary: present bounds must be finite - reject NaN and ±infinity,
      which otherwise slip past the ordering comparison.
    - coherent dates: when both are present, expiry must not precede posted.

    A violation fails the whole run before any clean upsert or expiry pass.
    Nothing here repairs or skips a bad row.
    """
    title_missing = 0
    company_missing = 0
    salary_inverted = 0
    salary_non_finite = 0
    expiry_before_posted = 0

    for job in jobs:
        if not job.title or not job.title.strip():
            title_missing += 1
        if not job.company or not job.company.strip():
            company_missing += 1
        for bound in (job.salary_min, job.salary_max):
            if bound is not None and not math.isfinite(bound):
                salary_non_finite += 1
        if (
            job.salary_min is not None
            and job.salary_max is not None
            and job.salary_min > job.salary_max
        ):
            salary_inverted += 1
        if (
            job.posted_date is not None
            and job.listing_expires_on is not None
            and job.listing_expires_on < job.posted_date
        ):
            expiry_before_posted += 1

    violations = {
        "title_required": title_missing,
        "company_required": company_missing,
        "salary_finite": salary_non_finite,
        "salary_bounds": salary_inverted,
        "expiry_after_posted": expiry_before_posted,
    }
    failed = {name: count for name, count in violations.items() if count}

    if failed:
        logger.error("ingestion.row_quality_failed", **failed)
        detail = ", ".join(f"{name}={count}" for name, count in sorted(failed.items()))
        raise IngestionSafetyError(f"Normalized row-quality gate failed: {detail}")


def send_dead_man_ping(url: str | None) -> bool:
    """POST to the healthchecks.io URL. Returns True if pinged, False if skipped/failed."""
    if not url:
        logger.info("ingestion.ping_skipped", reason="HEALTHCHECKS_URL not configured")
        return False

    try:
        response = httpx.post(url, timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("ingestion.ping_failed", error=str(exc))
        return False

    logger.info("ingestion.ping_sent")
    return True
