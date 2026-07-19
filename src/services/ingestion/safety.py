import httpx
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory
from src.core.logger import logger
from src.services.ingestion.models import CleanJob


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
