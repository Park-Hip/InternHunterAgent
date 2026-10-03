"""Give the submitted request and the provider's execution of it their own records.

Before this revision a run's request body and provider execution trace were both
squashed into one `raw_artifacts` row per run, representation
`provider-execution-v1`. That is a fit rather than a home, for three reasons this
revision removes:

1. `raw_artifacts` is defined as one retained representation of one retrieval. The
   handoff, the progress envelopes, and the terminal delivery are the provider's
   account of *running* a request, not of a listing, and they correctly carry no
   `raw_observations` row.
2. One row per run collapses the per-attempt facts. A retry, a second discovery
   input, or a second submit inside one run became list entries inside one
   document rather than records with their own `request_ordinal` and
   `attempt_number`.
3. The submitted body was digested into `collection_runs.input_digest` rather than
   stored as its own row, so a live run against a request that differs from the
   declared one had nowhere to record what was actually sent.

`collection_request_bodies` is the record the evidence-first ingestion blueprint
already specified for the submitted request, keyed by `(collection_run_id,
request_ordinal, attempt_number)`. `collection_request_executions` gives the
provider's answer to one of those requests its own record, so the two never merge
into one document and a reader can answer "what did this project ask for" without
reading provider output.

The blueprint's column table predates the multi-request shape and the store now
also retains three columns it had no column for: `endpoint_name` and
`path_parameters`, which together let the writer check that a request resolved
from an entry in the executed plan's `declared_endpoint_set`, and
`query_parameters`, which is where a request that declares filters on the query
string keeps them. `docs/decisions/evidence-first-ingestion-blueprint.md` records
the amendment.

`provider-execution-v1` is retired rather than rewritten. The rows already written
are **kept and stay readable**: `raw_artifacts` carries the append-only
`immutable_evidence` trigger, so a row written under the old representation
cannot be deleted or amended without dropping the protection every evidence table
relies on, and there is nothing this revision needs to change about them. What
changes is that no run writes the representation again.

Revision ID: a41d7c93be05
Revises: e51a8c07d942
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "a41d7c93be05"
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
        _text("endpoint_name"), _text("endpoint"),
        _json("path_parameters"), _json("query_parameters"), _json("body"),
        _text("body_digest"), _text("credential_env", True),
        _json("declared_caps"), _json("requested_fields"),
        _time("sent_at"), _time("created_at"),
        sa.UniqueConstraint("collection_run_id", "request_ordinal", "attempt_number"),
        sa.CheckConstraint(
            "request_ordinal > 0 AND attempt_number > 0",
            name="ck_collection_request_bodies_count"),
        sa.CheckConstraint(
            "credential_env IS NULL OR credential_env ~ '^[A-Z][A-Z0-9_]*$'",
            name="ck_collection_request_bodies_credential"),
    )
    op.create_table(
        "collection_request_executions", _id(), _ref("collection_run_id", "collection_runs.id"),
        _ref("request_body_id", "collection_request_bodies.id"),
        _int("http_status", True), _text("transport_error", True), _text("response_digest"),
        _time("observed_at"), _json("provider_facts"), _time("created_at"),
        sa.UniqueConstraint("request_body_id"),
        sa.CheckConstraint(
            "(http_status IS NULL) <> (transport_error IS NULL)",
            name="ck_collection_request_executions_response"),
    )
    op.create_index(
        "ix_collection_request_executions_run",
        "collection_request_executions", ["collection_run_id"],
    )
    for table in ("collection_request_bodies", "collection_request_executions"):
        op.execute(
            f"CREATE TRIGGER immutable_evidence BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_ingestion_evidence_mutation()"
        )


def downgrade() -> None:
    # Dropping a table drops the triggers on it, so `immutable_evidence` and the
    # function it executes both go with the revision that installed them. Nothing
    # survives here that a later teardown could wedge on.
    op.drop_index(
        "ix_collection_request_executions_run", table_name="collection_request_executions")
    op.drop_table("collection_request_executions")
    op.drop_table("collection_request_bodies")
