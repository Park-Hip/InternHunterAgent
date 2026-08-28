from src.core.db import session_factory
from src.core.logger import logger
from src.services.ingestion.models import IngestionRun, IngestionRunSummary


def persist_ingestion_run(summary: IngestionRunSummary) -> bool:
    """Append a run summary without affecting the ingestion attempt's outcome.

    The table intentionally has no update or conflict path: a retry and every
    individual attempt must remain independently inspectable.
    """
    try:
        with session_factory() as session:
            session.add(
                IngestionRun(
                    source=summary.source,
                    started_at=summary.started_at,
                    finished_at=summary.finished_at,
                    outcome=summary.outcome,
                    failure_phase=summary.failure_phase,
                    failure_code=summary.failure_code,
                    fetched=summary.fetched,
                    raw_upserted=summary.raw_upserted,
                    raw_new=summary.raw_new,
                    raw_changed=summary.raw_changed,
                    raw_unchanged=summary.raw_unchanged,
                    clean_loaded=summary.clean_loaded,
                    skipped=summary.skipped,
                    expired_count=summary.expired_count,
                    pages_failed=summary.pages_failed,
                )
            )
            session.commit()
    except Exception:
        logger.warning(
            "ingestion.summary_persist_failed",
            source=summary.source,
            outcome=summary.outcome,
        )
        return False

    logger.info(
        "ingestion.summary_persisted", source=summary.source, outcome=summary.outcome
    )
    return True
