from collections.abc import Iterable

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory
from src.services.ingestion.models import RawJob, RawPosting


class RawStoreError(Exception):
    """Raised when a raw_jobs upsert fails at the database layer."""


def upsert_raw_postings(postings: Iterable[RawPosting]) -> int:
    rows = [
        {
            "source": p.source,
            "external_id": p.external_id,
            "source_url": p.source_url,
            "raw_payload": p.raw_payload,
            "content_hash": p.content_hash,
        }
        for p in postings
    ]
    if not rows:
        return 0

    stmt = (
        insert(RawJob)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["source", "external_id"],
            set_={
                "raw_payload": insert(RawJob).excluded.raw_payload,
                "content_hash": insert(RawJob).excluded.content_hash,
                "source_url": insert(RawJob).excluded.source_url,
                "fetched_at": func.now(),
            },
        )
    )

    try:
        with session_factory() as session:
            session.execute(stmt)
            session.commit()
    except (OperationalError, DBAPIError) as exc:
        raise RawStoreError(f"Failed to upsert raw postings: {exc}") from exc

    return len(rows)
