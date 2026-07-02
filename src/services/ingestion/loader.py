from __future__ import annotations

from src.core.logger import logger
from src.services.ingestion.clean_store import replace_clean_jobs
from src.services.ingestion.models import NormalizedJob
from src.services.ingestion.normalize.vietnamworks import to_normalized_job
from src.services.ingestion.raw_store import upsert_raw_postings
from src.services.ingestion.sources.base import JobSource


def run_ingestion(source: JobSource | None = None) -> dict:
    if source is None:
        from src.services.ingestion.sources.vietnamworks import VietnamWorksSource

        source = VietnamWorksSource()

    postings = list(source.fetch())
    raw_count = upsert_raw_postings(postings)

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

    clean_count = replace_clean_jobs(normalized)
    return {
        "fetched": len(postings),
        "raw_upserted": raw_count,
        "clean_loaded": clean_count,
        "skipped": skipped,
    }


def main() -> None:
    result = run_ingestion()
    logger.info("ingestion.completed", **result)


if __name__ == "__main__":
    main()
