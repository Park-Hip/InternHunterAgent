"""Drop clean_jobs.is_active and ingestion_runs.expired_count (ADR-0059)."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1d032eb356bf"
down_revision = "f4b91860ea32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("clean_jobs", "is_active")
    op.drop_column("ingestion_runs", "expired_count")


def downgrade() -> None:
    op.add_column("ingestion_runs", sa.Column("expired_count", sa.BigInteger(), nullable=True))
    op.add_column(
        "clean_jobs",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )