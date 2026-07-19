from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy import BigInteger, Boolean, Date, Identity, Numeric, Text, UniqueConstraint
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
