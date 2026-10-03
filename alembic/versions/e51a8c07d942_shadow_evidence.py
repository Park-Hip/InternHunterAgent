"""Add append-only shadow evidence, leaving legacy serving tables intact.

Revision ID: e51a8c07d942
Revises: c9d3e6f7a2b1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "e51a8c07d942"
down_revision = "c9d3e6f7a2b1"
branch_labels = None
depends_on = None

# The append-only tables this revision creates, in foreign-key dependency order.
#
# Deliberately a local literal rather than an import from
# src.services.ingestion.models: this file is the historical record of one
# revision and must keep reproducing that revision even after the models move,
# which is the single allowed duplicate of the roster. What must not survive is
# two copies of it *inside this file*: the trigger loop and the downgrade loop
# used to spell it out separately, in opposite orders, with nothing failing when
# they disagreed. They share this definition, and downgrade() derives its order
# with reversed().
_SHADOW_EVIDENCE_TABLES = (
    "collection_plans", "collection_runs", "raw_artifacts", "raw_observations",
    "duplicate_deliveries", "normalization_results", "field_provenance",
)


def _id():
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def _text(name, nullable=False):
    return sa.Column(name, sa.Text(), nullable=nullable)


def _time(name, nullable=False):
    return sa.Column(name, sa.TIMESTAMP(timezone=True), nullable=nullable)


def _json(name, nullable=False):
    return sa.Column(name, JSONB(), nullable=nullable)


def _int(name, nullable=False):
    return sa.Column(name, sa.Integer(), nullable=nullable)


def _ref(name, target, nullable=False):
    return sa.Column(name, sa.BigInteger(), sa.ForeignKey(target), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "collection_plans", _id(), _text("source_id"), _text("plan_version"),
        _json("declared_scope"), _json("declared_caps"), _json("requested_fields"),
        _text("declared_completion_rule"), _json("declared_endpoint_set"),
        _text("retrieval_precision"), _text("authorization_revision"),
        _text("configuration_digest"), _time("created_at"),
        sa.UniqueConstraint("source_id", "plan_version"),
    )
    op.create_table(
        "collection_runs", _id(), _ref("plan_id", "collection_plans.id"),
        _text("idempotency_key"), _text("run_kind"), _time("started_at"),
        _time("finished_at", True), _text("outcome"), _text("coverage_result"),
        _int("declared_record_cap", True), _int("observed_record_count"),
        _text("declared_scope_digest"), _int("request_count"),
        _text("failure_category", True), _text("configuration_digest"),
        _text("input_digest"), _ref("replay_of_run_id", "collection_runs.id", True),
        _text("replay_reason", True), _time("created_at"),
        sa.UniqueConstraint("idempotency_key"),
        sa.CheckConstraint("run_kind IN ('scheduled', 'manual', 'replay')", name="ck_collection_runs_kind"),
        sa.CheckConstraint("outcome IN ('complete', 'incomplete', 'failed', 'authorization_blocked', 'aborted')", name="ck_collection_runs_outcome"),
        sa.CheckConstraint("coverage_result IN ('complete', 'partial', 'unknown') AND (coverage_result <> 'complete' OR outcome = 'complete')", name="ck_collection_runs_coverage"),
        sa.CheckConstraint("(outcome <> 'complete' OR (finished_at IS NOT NULL AND failure_category IS NULL)) AND (outcome = 'complete' OR failure_category IS NOT NULL) AND (run_kind <> 'replay' OR (replay_of_run_id IS NOT NULL AND replay_reason IS NOT NULL))", name="ck_collection_runs_result"),
        sa.CheckConstraint("observed_record_count >= 0 AND request_count >= 0 AND (declared_record_cap IS NULL OR declared_record_cap >= 0)", name="ck_collection_runs_counts"),
    )
    op.create_table(
        "raw_artifacts", _id(), _ref("collection_run_id", "collection_runs.id"),
        _text("content_digest"), _text("representation_version"),
        _text("media_type"), sa.Column("byte_length", sa.BigInteger(), nullable=False),
        _text("storage_locator"), _json("representation", True),
        _time("acquired_at"), _text("retention_disposition"),
        _time("retention_until", True), _text("authorization_revision"),
        _json("redaction_rules", True), _time("created_at"),
        sa.CheckConstraint("retention_disposition IN ('retained_full', 'retained_redacted', 'retained_derived', 'discarded')", name="ck_raw_artifacts_disposition"),
        sa.CheckConstraint("(retention_disposition = 'discarded' OR (retention_until IS NOT NULL AND representation IS NOT NULL)) AND (retention_disposition <> 'retained_redacted' OR redaction_rules IS NOT NULL)", name="ck_raw_artifacts_retention"),
        sa.CheckConstraint("byte_length >= 0", name="ck_raw_artifacts_length"),
    )
    op.create_table(
        "raw_observations", _id(), _ref("collection_run_id", "collection_runs.id"),
        _ref("raw_artifact_id", "raw_artifacts.id"),
        _text("source_id"), _text("source_listing_key"),
        _text("provider_listing_key", True), _text("delivery_id", True),
        _time("retrieved_at"), _json("source_urls"), _json("field_presence"),
        _text("idempotency_key"), _time("created_at"),
        sa.UniqueConstraint("source_id", "delivery_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_table(
        "duplicate_deliveries", _id(), _ref("collection_run_id", "collection_runs.id"),
        _ref("existing_observation_id", "raw_observations.id"), _time("created_at"),
    )
    op.create_table(
        "normalization_results", _id(), _ref("observation_id", "raw_observations.id"),
        _ref("collection_run_id", "collection_runs.id"), _text("normalization_version"), _int("attempt_number"),
        _text("outcome"), _text("quarantine_reason_code", True),
        _text("rule_version"), _text("output_digest", True),
        _json("output_values", True), _json("warnings"),
        _json("evaluator_metadata", True), _time("created_at"),
        sa.UniqueConstraint("observation_id", "normalization_version", "attempt_number"),
        sa.CheckConstraint("outcome IN ('succeeded', 'quarantined', 'rejected', 'superseded')", name="ck_normalization_results_outcome"),
        sa.CheckConstraint("(outcome <> 'quarantined' OR (quarantine_reason_code IS NOT NULL AND quarantine_reason_code IN ('identity_absent', 'listing_key_absent', 'artifact_integrity_failed', 'adapter_contract_violated', 'shape_unparseable', 'display_field_invalid', 'unauthorized_field'))) AND (outcome = 'quarantined' OR quarantine_reason_code IS NULL) AND (outcome <> 'succeeded' OR (output_digest IS NOT NULL AND output_values IS NOT NULL))", name="ck_normalization_results_values"),
        sa.CheckConstraint("attempt_number > 0", name="ck_normalization_results_attempt"),
    )
    op.create_table(
        "field_provenance", _id(), _ref("normalization_result_id", "normalization_results.id"),
        _text("output_field"), _text("source_field"), _text("locale", True),
        _ref("observation_id", "raw_observations.id"), _text("artifact_digest"),
        _text("rule_version"), _text("transform"), _text("value_state"),
        _text("review_status"), _time("created_at"),
        sa.UniqueConstraint("normalization_result_id", "output_field"),
        sa.CheckConstraint("transform IN ('copy', 'parse', 'normalize', 'derive', 'unavailable')", name="ck_field_provenance_transform"),
        sa.CheckConstraint("value_state IN ('present', 'source_empty', 'source_missing', 'invalid', 'unavailable', 'unknown')", name="ck_field_provenance_state"),
        sa.CheckConstraint("review_status IN ('automatic', 'reviewed', 'quarantined', 'superseded')", name="ck_field_provenance_review"),
    )
    op.execute("""
        CREATE FUNCTION reject_ingestion_evidence_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'ingestion evidence is append-only';
        END;
        $$
    """)
    for table in _SHADOW_EVIDENCE_TABLES:
        op.execute(
            f"CREATE TRIGGER immutable_evidence BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_ingestion_evidence_mutation()"
        )


def downgrade() -> None:
    # Reverse dependency order: every table is dropped before the one it points
    # at, so no drop has to rely on CASCADE. The function goes last because the
    # triggers still depend on it.
    for table in reversed(_SHADOW_EVIDENCE_TABLES):
        op.drop_table(table)
    op.execute("DROP FUNCTION reject_ingestion_evidence_mutation()")
