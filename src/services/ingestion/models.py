from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal

from pydantic import BaseModel
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
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


# ---------------------------------------------------------------------------
# Canonical table lists
# ---------------------------------------------------------------------------
# Every site that tears the ingestion schema down used to spell these names out
# by hand: the fixture loader, and the migration round-trip test, and twice more
# inside the shadow-evidence migration itself. Four copies of one value, with
# nothing that fails when they disagree, is how a stale table survives a
# teardown and then wedges the next one.
#
# The migration keeps its own literal. A migration is the historical record of
# one revision and must not silently follow the models. That one deliberate
# duplicate is the whole allowance; the two callers below import instead.

#: Tables carrying the append-only ``immutable_evidence`` trigger, in creation
#: order. Asserted by the migration round-trip test, so a table added here that
#: the migration does not attach a trigger to fails there rather than silently
#: losing append-only protection.
APPEND_ONLY_EVIDENCE_TABLES: Final = (
    "collection_plans",
    "collection_runs",
    "raw_artifacts",
    "raw_observations",
    "duplicate_deliveries",
    "normalization_results",
    "field_provenance",
)

#: The trigger function guarding :data:`APPEND_ONLY_EVIDENCE_TABLES`.
APPEND_ONLY_EVIDENCE_FUNCTION: Final = "reject_ingestion_evidence_mutation"

#: Every table the ingestion layer owns, in a drop-safe order: children first,
#: then the append-only evidence block in reverse dependency order, then the
#: projection and landing tables. Teardown sites drop these with ``CASCADE``.
INGESTION_TABLES: Final = (
    "field_provenance",
    "normalization_results",
    "duplicate_deliveries",
    "raw_observations",
    "raw_artifacts",
    "collection_runs",
    "collection_plans",
    "ingestion_runs",
    "clean_jobs",
    "raw_jobs",
)


def ingestion_teardown_statements(*, version_table: str | None = None) -> tuple[str, ...]:
    """SQL statements that clear the ingestion layer, in an order that always runs.

    Derived from the canonical lists above rather than spelled out, so a new
    model is covered by every teardown the day it is declared instead of the day
    someone remembers three other files.

    The function drop carries ``CASCADE`` on purpose. Dropping the named tables
    in dependency order removes every trigger this repository installs, but a
    database is a thing that outlives the code that built it: a table left by an
    abandoned experiment, or by a revision this branch has not merged, can hold a
    trigger that depends on the function, and a teardown that wedges on that
    stops every caller behind it from resetting their own schema. ``CASCADE``
    cannot drift, and here it only ever drops a trigger on a database that is
    about to be rebuilt from scratch.

    ``version_table`` is dropped last and is Alembic's own bookkeeping rather
    than a model, so callers that track the revision pass it in explicitly.
    """
    tables = [*INGESTION_TABLES]
    if version_table is not None:
        tables.append(version_table)
    return (
        f"DROP TABLE IF EXISTS {', '.join(tables)} CASCADE",
        f"DROP FUNCTION IF EXISTS {APPEND_ONLY_EVIDENCE_FUNCTION}() CASCADE",
    )


IngestionRunOutcome = Literal["completed", "safety_aborted", "failed"]
IngestionFailurePhase = Literal[
    "schema_check",
    "source_initialization",
    "fetch",
    "raw_upsert",
    "yield_check",
    "normalize",
    "row_quality_check",
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
        Index("ix_ingestion_runs_finished_at", "finished_at"),
        Index(
            "ix_ingestion_runs_source_started_at",
            "source",
            "started_at",
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


class CollectionPlan(Base):
    __tablename__ = "collection_plans"
    __table_args__ = (UniqueConstraint("source_id", "plan_version"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    plan_version: Mapped[str] = mapped_column(Text, nullable=False)
    declared_scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    declared_caps: Mapped[dict] = mapped_column(JSONB, nullable=False)
    requested_fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    declared_completion_rule: Mapped[str] = mapped_column(Text, nullable=False)
    declared_endpoint_set: Mapped[dict] = mapped_column(JSONB, nullable=False)
    retrieval_precision: Mapped[str] = mapped_column(Text, nullable=False)
    authorization_revision: Mapped[str] = mapped_column(Text, nullable=False)
    configuration_digest: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        CheckConstraint("run_kind IN ('scheduled', 'manual', 'replay')", name="ck_collection_runs_kind"),
        CheckConstraint(
            "outcome IN ('complete', 'incomplete', 'failed', 'authorization_blocked', 'aborted')",
            name="ck_collection_runs_outcome",
        ),
        CheckConstraint(
            "coverage_result IN ('complete', 'partial', 'unknown') AND "
            "(coverage_result <> 'complete' OR outcome = 'complete')",
            name="ck_collection_runs_coverage",
        ),
        CheckConstraint(
            "(outcome <> 'complete' OR (finished_at IS NOT NULL AND failure_category IS NULL)) "
            "AND (outcome = 'complete' OR failure_category IS NOT NULL) "
            "AND (run_kind <> 'replay' OR (replay_of_run_id IS NOT NULL AND replay_reason IS NOT NULL))",
            name="ck_collection_runs_result",
        ),
        CheckConstraint(
            "observed_record_count >= 0 AND request_count >= 0 AND "
            "(declared_record_cap IS NULL OR declared_record_cap >= 0)",
            name="ck_collection_runs_counts",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("collection_plans.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    run_kind: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    coverage_result: Mapped[str] = mapped_column(Text, nullable=False)
    declared_record_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_scope_digest: Mapped[str] = mapped_column(Text, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    configuration_digest: Mapped[str] = mapped_column(Text, nullable=False)
    input_digest: Mapped[str] = mapped_column(Text, nullable=False)
    replay_of_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("collection_runs.id"), nullable=True)
    replay_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class RawArtifact(Base):
    __tablename__ = "raw_artifacts"
    __table_args__ = (
        CheckConstraint(
            "retention_disposition IN ('retained_full', 'retained_redacted', "
            "'retained_derived', 'discarded')",
            name="ck_raw_artifacts_disposition",
        ),
        CheckConstraint(
            "(retention_disposition = 'discarded' OR "
            "(retention_until IS NOT NULL AND representation IS NOT NULL)) AND "
            "(retention_disposition <> 'retained_redacted' OR redaction_rules IS NOT NULL)",
            name="ck_raw_artifacts_retention",
        ),
        CheckConstraint("byte_length >= 0", name="ck_raw_artifacts_length"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    collection_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("collection_runs.id"), nullable=False)
    content_digest: Mapped[str] = mapped_column(Text, nullable=False)
    representation_version: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_length: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_locator: Mapped[str] = mapped_column(Text, nullable=False)
    representation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    acquired_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    retention_disposition: Mapped[str] = mapped_column(Text, nullable=False)
    retention_until: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    authorization_revision: Mapped[str] = mapped_column(Text, nullable=False)
    redaction_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class RawObservation(Base):
    __tablename__ = "raw_observations"
    __table_args__ = (
        UniqueConstraint("source_id", "delivery_id"),
        UniqueConstraint("idempotency_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    collection_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("collection_runs.id"), nullable=False)
    raw_artifact_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("raw_artifacts.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_listing_key: Mapped[str] = mapped_column(Text, nullable=False)
    provider_listing_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    source_urls: Mapped[dict] = mapped_column(JSONB, nullable=False)
    field_presence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class DuplicateDelivery(Base):
    """Append-only duplicate outcome, pointing to the original observation."""

    __tablename__ = "duplicate_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    collection_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("collection_runs.id"), nullable=False)
    existing_observation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("raw_observations.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class NormalizationResult(Base):
    __tablename__ = "normalization_results"
    __table_args__ = (
        UniqueConstraint("observation_id", "normalization_version", "attempt_number"),
        CheckConstraint(
            "outcome IN ('succeeded', 'quarantined', 'rejected', 'superseded')",
            name="ck_normalization_results_outcome",
        ),
        CheckConstraint(
            "(outcome <> 'quarantined' OR (quarantine_reason_code IS NOT NULL AND quarantine_reason_code IN "
            "('identity_absent', 'listing_key_absent', 'artifact_integrity_failed', "
            "'adapter_contract_violated', 'shape_unparseable', "
            "'display_field_invalid', 'unauthorized_field'))) AND "
            "(outcome = 'quarantined' OR quarantine_reason_code IS NULL) AND "
            "(outcome <> 'succeeded' OR (output_digest IS NOT NULL AND output_values IS NOT NULL))",
            name="ck_normalization_results_values",
        ),
        CheckConstraint("attempt_number > 0", name="ck_normalization_results_attempt"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    observation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("raw_observations.id"), nullable=False)
    collection_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("collection_runs.id"), nullable=False)
    normalization_version: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    quarantine_reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    output_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False)
    evaluator_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class FieldProvenance(Base):
    __tablename__ = "field_provenance"
    __table_args__ = (
        UniqueConstraint("normalization_result_id", "output_field"),
        CheckConstraint(
            "transform IN ('copy', 'parse', 'normalize', 'derive', 'unavailable')",
            name="ck_field_provenance_transform",
        ),
        CheckConstraint(
            "value_state IN ('present', 'source_empty', 'source_missing', 'invalid', "
            "'unavailable', 'unknown')",
            name="ck_field_provenance_state",
        ),
        CheckConstraint(
            "review_status IN ('automatic', 'reviewed', 'quarantined', 'superseded')",
            name="ck_field_provenance_review",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    normalization_result_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("normalization_results.id"), nullable=False)
    output_field: Mapped[str] = mapped_column(Text, nullable=False)
    source_field: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str | None] = mapped_column(Text, nullable=True)
    observation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("raw_observations.id"), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(Text, nullable=False)
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    transform: Mapped[str] = mapped_column(Text, nullable=False)
    value_state: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


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
