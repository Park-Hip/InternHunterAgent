"""ingestion run summaries

Adds an append-only, non-PII operational record for every ingestion attempt.
The isolated table and its indexes do not alter raw_jobs or clean_jobs.

Revision ID: c9d3e6f7a2b1
Revises: b7e2f4a91c3d
Create Date: 2026-08-28

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c9d3e6f7a2b1"
down_revision = "b7e2f4a91c3d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("failure_phase", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("fetched", sa.BigInteger(), nullable=True),
        sa.Column("raw_upserted", sa.BigInteger(), nullable=True),
        sa.Column("raw_new", sa.BigInteger(), nullable=True),
        sa.Column("raw_changed", sa.BigInteger(), nullable=True),
        sa.Column("raw_unchanged", sa.BigInteger(), nullable=True),
        sa.Column("clean_loaded", sa.BigInteger(), nullable=True),
        sa.Column("skipped", sa.BigInteger(), nullable=True),
        sa.Column("expired_count", sa.BigInteger(), nullable=True),
        sa.Column("pages_failed", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('completed', 'safety_aborted', 'failed')",
            name="ck_ingestion_runs_outcome",
        ),
    )
    op.create_index("ix_ingestion_runs_finished_at", "ingestion_runs", ["finished_at"])
    op.create_index(
        "ix_ingestion_runs_source_started_at",
        "ingestion_runs",
        ["source", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_source_started_at", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_finished_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
