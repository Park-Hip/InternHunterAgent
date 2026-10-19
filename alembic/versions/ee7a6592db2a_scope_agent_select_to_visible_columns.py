"""Give internhunter_agent column-level SELECT on the 16 visible columns (#722).

The role held table-level ``SELECT`` on ``clean_jobs``, which made the SQL
validator's hidden-column token check cosmetic: ``SELECT *`` names no hidden
column, and a table grant returns all 21 physical columns. Column grants make
PostgreSQL the boundary: star, ``c.*``, subquery, CTE, and whole-row forms all
fail instead of leaking, and a new physical column is denied by default.

The revision is guarded because the agent role is provisioned by an operator,
not by this migration: a blank CI database has no ``internhunter_agent``, and
both directions no-op there with a notice. Only the agent role is touched; the
writer role keeps every privilege it has.
"""
import logging

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ee7a6592db2a"
down_revision = "1d032eb356bf"
branch_labels = None
depends_on = None

_AGENT_ROLE = "internhunter_agent"
# Mirrors the prompt's schema context, the read probe in
# src/api/privilege_guard.py, and src/services/query/sql_validator.py.
# Change all four together.
_VISIBLE_COLUMNS = (
    "id",
    "title",
    "company",
    "role",
    "description",
    "tech_stack",
    "location",
    "source_url",
    "job_level",
    "listing_expires_on",
    "created_on",
    "is_internship",
    "salary_min",
    "salary_max",
    "salary_currency",
    "is_salary_negotiable",
)
_HIDDEN_COLUMNS = (
    "source",
    "external_id",
    "posted_date",
    "first_seen_at",
    "last_seen_at",
)

_logger = logging.getLogger("alembic.runtime.migration")


def _agent_role_exists(bind) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": _AGENT_ROLE},
        ).scalar()
    )


def _say_absent() -> None:
    _logger.info(
        "agent role %s is absent; leaving clean_jobs grants unchanged",
        _AGENT_ROLE,
    )


def upgrade() -> None:
    """Replace table-level SELECT with SELECT on exactly the visible columns."""
    if not _agent_role_exists(op.get_bind()):
        _say_absent()
        return
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE clean_jobs FROM {_AGENT_ROLE}")
    # A table-level revoke does not clear column grants, so drop any earlier
    # grant on a hidden column explicitly; otherwise it would survive and keep
    # leaking even though the table-level grant is gone.
    op.execute(
        f"REVOKE SELECT ({', '.join(_HIDDEN_COLUMNS)})"
        f" ON TABLE clean_jobs FROM {_AGENT_ROLE}"
    )
    op.execute(
        f"GRANT SELECT ({', '.join(_VISIBLE_COLUMNS)})"
        f" ON TABLE clean_jobs TO {_AGENT_ROLE}"
    )


def downgrade() -> None:
    """Restore the table-level SELECT the role held before #722."""
    if not _agent_role_exists(op.get_bind()):
        _say_absent()
        return
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE clean_jobs FROM {_AGENT_ROLE}")
    op.execute(
        f"REVOKE SELECT ({', '.join(_VISIBLE_COLUMNS)})"
        f" ON TABLE clean_jobs FROM {_AGENT_ROLE}"
    )
    op.execute(f"GRANT SELECT ON TABLE clean_jobs TO {_AGENT_ROLE}")
