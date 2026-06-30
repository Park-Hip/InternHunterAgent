from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, Numeric, Text, UniqueConstraint
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawJob(Base):
    __tablename__ = "raw_jobs"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
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
    is_internship: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    salary_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_salary_negotiable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
