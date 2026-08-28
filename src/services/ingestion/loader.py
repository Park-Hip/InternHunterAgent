from __future__ import annotations

import sys
from dataclasses import replace
from datetime import UTC, datetime

from src.core.config import settings
from src.core.logger import logger
from src.services.ingestion.clean_store import (
    expire_stale_clean_jobs,
    upsert_clean_jobs,
)
from src.services.ingestion.models import (
    IngestionFailurePhase,
    IngestionRunSummary,
    NormalizedJob,
)
from src.services.ingestion.normalize.vietnamworks import to_normalized_job
from src.services.ingestion.raw_store import upsert_raw_postings
from src.services.ingestion.run_store import persist_ingestion_run
from src.services.ingestion.safety import (
    IngestionSafetyError,
    assert_clean_jobs_schema,
    assert_min_yield,
    send_dead_man_ping,
)
from src.services.ingestion.sources.base import JobSource

# Rollback runbook: if clean_jobs needs to be rebuilt (e.g. a bad load), it can
# always be reconstructed from raw_jobs - raw_jobs accumulates natural-key rows
# and is never truncated. Replay: fetch every raw_jobs row, run its raw_payload back through
# to_normalized_job, and re-run upsert_clean_jobs over the results. This is the
# same recovery performed live on 2026-07-15.


def run_ingestion(source: JobSource | None = None) -> dict:
    """Run ingestion and append a best-effort non-PII operational summary."""
    source_name = getattr(source, "source", "vietnamworks")
    summary = IngestionRunSummary(
        source=source_name,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        outcome="failed",
    )
    phase: IngestionFailurePhase = "schema_check"

    try:
        assert_clean_jobs_schema()

        if source is None:
            phase = "source_initialization"
            from src.services.ingestion.sources.vietnamworks import VietnamWorksSource

            source = VietnamWorksSource()

        phase = "fetch"
        postings = list(source.fetch())
        summary = replace(
            summary,
            fetched=len(postings),
            pages_failed=getattr(source, "pages_failed", 0),
        )

        phase = "raw_upsert"
        raw_counts = upsert_raw_postings(postings)
        summary = replace(
            summary,
            raw_upserted=raw_counts.total,
            raw_new=raw_counts.new,
            raw_changed=raw_counts.changed,
            raw_unchanged=raw_counts.unchanged,
        )

        phase = "yield_check"
        assert_min_yield(len(postings), settings.ingestion_yaml["safety"]["min_yield"])

        phase = "normalize"
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
        summary = replace(summary, skipped=skipped)

        phase = "clean_upsert"
        clean_count = upsert_clean_jobs(normalized)
        summary = replace(summary, clean_loaded=clean_count)

        phase = "expiry"
        expire_after_days = settings.ingestion_yaml["lifecycle"]["expire_after_days"]
        expired_count = expire_stale_clean_jobs(expire_after_days)
        summary = replace(
            summary,
            expired_count=expired_count,
            outcome="completed",
        )

        return {
            "fetched": len(postings),
            "raw_upserted": raw_counts.total,
            "raw_new": raw_counts.new,
            "raw_changed": raw_counts.changed,
            "raw_unchanged": raw_counts.unchanged,
            "clean_loaded": clean_count,
            "skipped": skipped,
            "expired_count": expired_count,
            "pages_failed": summary.pages_failed,
        }
    except IngestionSafetyError:
        summary = replace(
            summary,
            outcome="safety_aborted",
            failure_phase=phase,
            failure_code="safety_check_failed",
        )
        raise
    except Exception:
        summary = replace(
            summary,
            outcome="failed",
            failure_phase=phase,
            failure_code="unexpected_error",
        )
        raise
    finally:
        persist_ingestion_run(replace(summary, finished_at=datetime.now(UTC)))


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
