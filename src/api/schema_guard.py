"""Boot-time schema guard for the serving (read) path.

Fails the FastAPI boot loudly if the live ``clean_jobs`` table has drifted from
the contract the serving path relies on, instead of erroring mid-query on a
renamed or missing column.

This mirrors the write-path guard in ``src/services/ingestion/safety.py`` but is
a separate serving-layer function: it imports only from ``src.core.*`` and does
not pull the ingestion package into the serving path. The expected column set is
therefore duplicated here as a frozen literal rather than derived from the
ingestion ORM (see ``EXPECTED_COLUMNS``).
"""

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory
from src.core.logger import logger


class SchemaGuardError(RuntimeError):
    """Raised when the serving-path clean_jobs schema check fails. Aborts boot."""


# The frozen clean_jobs contract: 16 agent-visible columns + source/external_id/
# posted_date bookkeeping + is_active/first_seen_at/last_seen_at lifecycle.
# Duplicated here deliberately to keep the serving path free of any
# src.services.ingestion import (layer-isolation rule, T0021.1). A legitimate
# schema change must update this constant AND the ingestion ORM in tandem.
EXPECTED_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "source",
        "external_id",
        "source_url",
        "title",
        "company",
        "role",
        "description",
        "tech_stack",
        "job_level",
        "location",
        "posted_date",
        "listing_expires_on",
        "created_on",
        "is_internship",
        "salary_min",
        "salary_max",
        "salary_currency",
        "is_salary_negotiable",
        "is_active",
        "first_seen_at",
        "last_seen_at",
    }
)


def assert_serving_schema() -> None:
    """Compare live clean_jobs columns against the frozen serving contract.

    Raises SchemaGuardError naming the diff if they disagree (exact match: both
    missing and unexpected columns fail), if the table is absent, or if the
    database cannot be inspected.
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
        raise SchemaGuardError(f"Failed to inspect clean_jobs schema: {exc}") from exc

    if not actual:
        raise SchemaGuardError(
            "clean_jobs table not found in the database (information_schema query "
            "returned no columns) — refusing to serve"
        )

    missing = EXPECTED_COLUMNS - actual
    unexpected = actual - EXPECTED_COLUMNS

    if missing or unexpected:
        logger.error(
            "api.schema_drift",
            missing=sorted(missing),
            unexpected=sorted(unexpected),
        )
        raise SchemaGuardError(
            f"clean_jobs schema drift detected: missing={sorted(missing)} "
            f"unexpected={sorted(unexpected)}"
        )

    logger.info("api.schema_ok", columns=len(EXPECTED_COLUMNS))
