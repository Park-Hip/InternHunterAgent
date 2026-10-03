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
execution history rather than as its only one. The NOT VALID check at the end makes
the retirement a rule for every row written from here on without touching the rows
that already exist, which is the only way to say both things at once in one table.

The downgrade is the other side of that honesty and is lossy: a run recorded since
this migration keeps its request_count and its input_digest, and loses both of its
request records and both execution records, because no representation of them
survives outside these two tables. That is the same loss the shadow-evidence
downgrade already accepts, and it is why this migration is a reversal rather than
something to run against a database whose request evidence anyone still needs.

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
        _text("endpoint"), _text("endpoint_name"),
        # No server default: an empty object is already the honest encoding of a
        # request that carried no query, and a default would make a writer that
        # forgot the column indistinguishable from one with nothing to send.
        _json("query_parameters"),
        # none_as_null keeps a bodyless request a SQL NULL rather than a stored JSON
        # null, so "no body was sent" is never readable as a body that was sent null.
        sa.Column("body", JSONB(none_as_null=True), nullable=True),
        _text("credential_env", True), _text("body_digest"), _json("declared_caps"),
        _json("requested_fields"), _time("sent_at"), _time("created_at"),
        sa.UniqueConstraint("collection_run_id", "request_ordinal", "attempt_number"),
        # The execution record repeats the run, position and attempt beside its
        # foreign key so a reader need not join, and this is what keeps that
        # repetition true: the child cannot name a position its request never had.
        sa.UniqueConstraint("id", "collection_run_id", "request_ordinal", "attempt_number"),
        sa.CheckConstraint("request_ordinal > 0 AND attempt_number > 0",
                           name="ck_collection_request_bodies_position"),
        # A stored JSON null would read as a body that was sent null, which is the
        # claim the SQL NULL above exists to make impossible.
        sa.CheckConstraint(
            "(body IS NOT NULL AND jsonb_typeof(body) = 'object') OR "
            "(body IS NULL AND method IN ('GET', 'HEAD', 'DELETE'))",
            name="ck_collection_request_bodies_body"),
        # A credential is retained by the name of its location, never by value.
        sa.CheckConstraint(
            "credential_env IS NULL OR credential_env ~ '^[A-Z][A-Z0-9_]*$'",
            name="ck_collection_request_bodies_credential"),
    )
    op.create_table(
        "collection_request_executions", _id(),
        _ref("collection_run_id", "collection_runs.id"),
        # The composite foreign key below carries the reference, so this column is
        # named rather than constrained twice.
        sa.Column("request_body_id", sa.BigInteger(), nullable=False),
        _int("request_ordinal"), _int("attempt_number"), _text("phase"),
        _int("http_status", True), _text("transport_error", True), _text("response_digest"),
        _text("execution_digest"), _json("observed_facts"), _time("observed_at"),
        sa.Column("waited_before_seconds", sa.Numeric(), nullable=False),
        _time("retention_until"), _text("authorization_revision"), _time("created_at"),
        sa.UniqueConstraint("request_body_id"),
        sa.ForeignKeyConstraint(
            ["request_body_id", "collection_run_id", "request_ordinal", "attempt_number"],
            ["collection_request_bodies.id", "collection_request_bodies.collection_run_id",
             "collection_request_bodies.request_ordinal",
             "collection_request_bodies.attempt_number"],
        ),
        # A request that never reached the provider has no status, and recording a
        # zero for it would claim the provider answered with one.
        sa.CheckConstraint("http_status IS NULL OR http_status >= 100",
                           name="ck_collection_request_executions_status"),
        sa.CheckConstraint("(http_status IS NULL) = (transport_error IS NOT NULL)",
                           name="ck_collection_request_executions_delivery"),
        sa.CheckConstraint("waited_before_seconds >= 0",
                           name="ck_collection_request_executions_wait"),
        # The provider's account of the request is retained evidence in its own right,
        # including for a run that delivered no records at all.
        sa.CheckConstraint("retention_until IS NOT NULL AND authorization_revision <> ''",
                           name="ck_collection_request_executions_retention"),
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
    # NOT VALID means "not yet enforced against the rows already there", which is
    # exactly the retirement: new rows may not carry the retired representation, and
    # every row that already does stays readable and unchanged.
    op.execute(
        "ALTER TABLE raw_artifacts ADD CONSTRAINT ck_raw_artifacts_retired_execution "
        "CHECK (representation_version <> 'provider-execution-v1') NOT VALID"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE raw_artifacts DROP CONSTRAINT IF EXISTS "
               "ck_raw_artifacts_retired_execution")
    for table in ("collection_request_executions", "collection_request_bodies"):
        op.drop_table(table)
