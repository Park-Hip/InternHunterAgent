from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Identity,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ---------------------------------------------------------------------------
# Pydantic record models — internal pipeline DTOs (no DB connection on import)
# ---------------------------------------------------------------------------


class RawPosting(BaseModel):
    """Verbatim landing record yielded by a source adapter and upserted into raw_jobs.

    Fields mirror the raw_jobs insert shape; surrogate id and fetched_at are
    assigned by the database, not the adapter.
    """

    source: str
    external_id: str
    source_url: str | None
    raw_payload: dict
    content_hash: str


class NormalizedJob(BaseModel):
    """Canonical shape produced by the normalizer + shared transform.

    Consumed by the T0009.6 loader to upsert into clean_jobs. Fields map
    one-to-one onto the agent-visible clean_jobs columns; surrogate id is
    assigned by the database. Field values are populated by later sub-tickets.
    """

    source: str
    external_id: str
    source_url: str | None = None
    title: str
    company: str
    role: str
    description: str | None = None
    tech_stack: str | None = None
    job_level: str | None = None
    location: str | None = None
    posted_date: date | None = None
    listing_expires_on: date | None = None
    created_on: date | None = None
    is_internship: bool
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    is_salary_negotiable: bool


# ---------------------------------------------------------------------------
# SQLAlchemy ORM models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


IngestionRunOutcome = Literal["completed", "safety_aborted", "failed"]
IngestionFailurePhase = Literal[
    "schema_check",
    "source_initialization",
    "fetch",
    "raw_upsert",
    "yield_check",
    "normalize",
    "clean_upsert",
    "expiry",
]
IngestionFailureCode = Literal["safety_check_failed", "unexpected_error"]


@dataclass(frozen=True)
class IngestionRunSummary:
    """Safe, immutable operational facts collected for one ingestion attempt."""

    source: str
    started_at: datetime
    finished_at: datetime
    outcome: IngestionRunOutcome
    failure_phase: IngestionFailurePhase | None = None
    failure_code: IngestionFailureCode | None = None
    fetched: int | None = None
    raw_upserted: int | None = None
    raw_new: int | None = None
    raw_changed: int | None = None
    raw_unchanged: int | None = None
    clean_loaded: int | None = None
    skipped: int | None = None
    expired_count: int | None = None
    pages_failed: int | None = None


class RawJob(Base):
    __tablename__ = "raw_jobs"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )


class IngestionRun(Base):
    """Append-only, non-PII operational summary of an ingestion attempt."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('completed', 'safety_aborted', 'failed')",
            name="ck_ingestion_runs_outcome",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    failure_phase: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw_upserted: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw_new: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw_changed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw_unchanged: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clean_loaded: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    skipped: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expired_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pages_failed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CleanJob(Base):
    __tablename__ = "clean_jobs"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    listing_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_internship: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    salary_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_salary_negotiable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
