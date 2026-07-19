from __future__ import annotations

import sys

from src.core.config import settings
from src.core.logger import logger
from src.services.ingestion.clean_store import expire_stale_clean_jobs, upsert_clean_jobs
from src.services.ingestion.models import NormalizedJob
from src.services.ingestion.normalize.vietnamworks import to_normalized_job
from src.services.ingestion.raw_store import upsert_raw_postings
from src.services.ingestion.safety import (
    IngestionSafetyError,
    assert_clean_jobs_schema,
    assert_min_yield,
    send_dead_man_ping,
)
from src.services.ingestion.sources.base import JobSource

# Rollback runbook: if clean_jobs needs to be rebuilt (e.g. a bad load), it can
# always be reconstructed from raw_jobs — raw_jobs is append-only and never
# truncated. Replay: fetch every raw_jobs row, run its raw_payload back through
# to_normalized_job, and re-run upsert_clean_jobs over the results. This is the
# same recovery performed live on 2026-07-15.


def run_ingestion(source: JobSource | None = None) -> dict:
    assert_clean_jobs_schema()

    if source is None:
        from src.services.ingestion.sources.vietnamworks import VietnamWorksSource

        source = VietnamWorksSource()

    postings = list(source.fetch())
    raw_count = upsert_raw_postings(postings)

    assert_min_yield(len(postings), settings.ingestion_yaml["safety"]["min_yield"])

    normalized: list[NormalizedJob] = []
    skipped = 0
    for p in postings:
        try:
            normalized.append(to_normalized_job(p.raw_payload))
        except Exception:
            skipped += 1
            logger.warning(
                "ingestion.normalize_skipped",
                source=p.source,
                external_id=p.external_id,
            )

    clean_count = upsert_clean_jobs(normalized)

    expire_after_days = settings.ingestion_yaml["lifecycle"]["expire_after_days"]
    expired_count = expire_stale_clean_jobs(expire_after_days)

    pages_failed = getattr(source, "pages_failed", 0)

    return {
        "fetched": len(postings),
        "raw_upserted": raw_count,
        "clean_loaded": clean_count,
        "skipped": skipped,
        "expired_count": expired_count,
        "pages_failed": pages_failed,
    }


def main() -> None:
    try:
        result = run_ingestion()
    except IngestionSafetyError as exc:
        logger.error("ingestion.aborted", error=str(exc))
        sys.exit(1)

    logger.info("ingestion.completed", **result)
    send_dead_man_ping(settings.HEALTHCHECKS_URL)


if __name__ == "__main__":
    main()
