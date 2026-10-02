"""Give every request attempt a first-class record, and retire provider-execution-v1.

The provider execution trace used to be one raw_artifacts row per run, keyed by
`representation_version = 'provider-execution-v1'`. That representation is retired
here, not deleted: raw_artifacts is append-only, so an existing row cannot be updated
or removed even in principle. Every row written before this migration stays exactly
as it was and stays readable; what changes is that no run writes one again, and a run
written from now on carries one request record and one execution record per attempt.

Existing rows are the whole point. A run recorded before this migration has no
collection_request_bodies rows, and the trace of that run is still its single
legacy artifact, so a reader must treat the legacy representation as a run's
execution history rather than as its only one.

Revision ID: a1c3e5f70924
Revises: e51a8c07d942
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "a1c3e5f70924"
down_revision = "e51a8c07d942"
branch_labels = None
depends_on = None


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
        "collection_request_bodies", _id(), _ref("collection_run_id", "collection_runs.id"),
        _int("request_ordinal"), _int("attempt_number"), _text("adapter_id"), _text("method"),
        _text("endpoint"),
        sa.Column("query_parameters", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        # none_as_null keeps a bodyless request a SQL NULL rather than a stored JSON
        # null, so "no body was sent" is never readable as a body that was sent null.
        sa.Column("body", JSONB(none_as_null=True), nullable=True),
        _text("credential_env", True),
        _text("body_digest"), _json("declared_caps"),
        _json("requested_fields"), _time("sent_at"), _time("created_at"),
        sa.UniqueConstraint("collection_run_id", "request_ordinal", "attempt_number"),
        # A body is absent only for a method that carries none by definition, so an
        # omitted parameter stays distinguishable from an empty body.
        sa.CheckConstraint(
            "body IS NOT NULL OR method IN ('GET', 'HEAD', 'DELETE')",
            name="ck_collection_request_bodies_body"),
        # A credential is retained by the name of its location, never by value.
        sa.CheckConstraint(
            "credential_env IS NULL OR credential_env ~ '^[A-Z][A-Z0-9_]*$'",
            name="ck_collection_request_bodies_credential"),
        sa.CheckConstraint("request_ordinal > 0 AND attempt_number > 0",
                           name="ck_collection_request_bodies_position"),
    )
    op.create_table(
        "collection_request_executions", _id(),
        _ref("collection_run_id", "collection_runs.id"),
        _ref("request_body_id", "collection_request_bodies.id"),
        _int("request_ordinal"), _int("attempt_number"), _text("phase"),
        _int("http_status", True), _text("transport_error", True), _text("response_digest"),
        _text("execution_digest"), _json("observed_facts"), _time("observed_at"),
        sa.Column("waited_before_seconds", sa.Numeric(), nullable=False), _time("created_at"),
        sa.UniqueConstraint("request_body_id"),
        # A request that never reached the provider has no status, and recording a
        # zero for it would claim the provider answered.
        sa.CheckConstraint("http_status IS NULL OR http_status >= 0",
                           name="ck_collection_request_executions_status"),
        sa.CheckConstraint("(http_status IS NULL) = (transport_error IS NOT NULL)",
                           name="ck_collection_request_executions_delivery"),
        sa.CheckConstraint("waited_before_seconds >= 0",
                           name="ck_collection_request_executions_wait"),
    )
    op.create_index(
        "ix_collection_request_executions_run", "collection_request_executions",
        ["collection_run_id", "request_ordinal", "attempt_number"],
    )
    for table in ("collection_request_executions", "collection_request_bodies"):
        op.execute(
            f"CREATE TRIGGER immutable_evidence BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_ingestion_evidence_mutation()"
        )


def downgrade() -> None:
    for table in ("collection_request_executions", "collection_request_bodies"):
        op.drop_table(table)
