from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.db import session_factory
from src.services.ingestion.models import RawJob, RawPosting


class RawStoreError(Exception):
    """Raised when a raw_jobs upsert fails at the database layer."""


@dataclass(frozen=True)
class RawUpsertCounts:
    new: int
    changed: int
    unchanged: int

    @property
    def total(self) -> int:
        return self.new + self.changed + self.unchanged


def upsert_raw_postings(postings: Iterable[RawPosting]) -> RawUpsertCounts:
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
        return RawUpsertCounts(new=0, changed=0, unchanged=0)

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
            natural_keys = [(row["source"], row["external_id"]) for row in rows]
            existing_hashes = {
                (source, external_id): content_hash
                for source, external_id, content_hash in session.execute(
                    select(RawJob.source, RawJob.external_id, RawJob.content_hash).where(
                        tuple_(RawJob.source, RawJob.external_id).in_(natural_keys)
                    )
                ).all()
            }
            counts = RawUpsertCounts(
                new=sum((row["source"], row["external_id"]) not in existing_hashes for row in rows),
                changed=sum(
                    existing_hashes.get((row["source"], row["external_id"])) not in (None, row["content_hash"])
                    for row in rows
                ),
                unchanged=sum(
                    existing_hashes.get((row["source"], row["external_id"])) == row["content_hash"]
                    for row in rows
                ),
            )
            session.execute(stmt)
            session.commit()
    except (OperationalError, DBAPIError) as exc:
        raise RawStoreError(f"Failed to upsert raw postings: {exc}") from exc

    return counts
