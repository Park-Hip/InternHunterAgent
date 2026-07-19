"""lifecycle columns

Adds hidden lifecycle bookkeeping to clean_jobs: is_active, first_seen_at,
last_seen_at. Existing rows are backfilled from raw_jobs.fetched_at so the
values are truthful rather than defaulted to the migration run time.

Revision ID: b7e2f4a91c3d
Revises: f3a1c9d2e7b4
Create Date: 2026-07-18

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b7e2f4a91c3d"
down_revision = "f3a1c9d2e7b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clean_jobs",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "clean_jobs",
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "clean_jobs",
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.execute(
        """
        UPDATE clean_jobs c
           SET first_seen_at = r.fetched_at,
               last_seen_at  = r.fetched_at
          FROM raw_jobs r
         WHERE r.source = c.source AND r.external_id = c.external_id
        """
    )


def downgrade() -> None:
    op.drop_column("clean_jobs", "last_seen_at")
    op.drop_column("clean_jobs", "first_seen_at")
    op.drop_column("clean_jobs", "is_active")
