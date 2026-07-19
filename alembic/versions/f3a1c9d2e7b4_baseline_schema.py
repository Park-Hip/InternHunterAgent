"""baseline schema

Reproduces the schema built by scripts/init_db.sql exactly, so that
`alembic upgrade head` is a clean no-op on an already-initialised database.

Revision ID: f3a1c9d2e7b4
Revises:
Create Date: 2026-07-18

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f3a1c9d2e7b4"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("source", "external_id"),
    )

    op.create_table(
        "clean_jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tech_stack", sa.Text(), nullable=True),
        sa.Column("job_level", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("posted_date", sa.Date(), nullable=True),
        sa.Column("listing_expires_on", sa.Date(), nullable=True),
        sa.Column("created_on", sa.Date(), nullable=True),
        sa.Column(
            "is_internship",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("salary_min", sa.Numeric(), nullable=True),
        sa.Column("salary_max", sa.Numeric(), nullable=True),
        sa.Column("salary_currency", sa.Text(), nullable=True),
        sa.Column(
            "is_salary_negotiable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.UniqueConstraint("source", "external_id"),
    )


def downgrade() -> None:
    op.drop_table("clean_jobs")
    op.drop_table("raw_jobs")
