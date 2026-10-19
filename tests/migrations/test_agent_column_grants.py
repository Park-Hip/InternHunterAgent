"""The #722 grant migration: table-level SELECT off, 16 column grants on.

The blank-database path, where the agent role is absent and the migration
no-ops, is exercised by the CI job's blank ``alembic upgrade head`` before this
test creates the role. Here the role is present, so both directions are proven
against a real database.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from alembic import command
from alembic.config import Config
from src.services.ingestion.models import ingestion_teardown_statements

SCRATCH_DSN = os.environ.get("SCRATCH_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not SCRATCH_DSN,
    reason="set SCRATCH_DATABASE_URL to a throwaway Postgres to run migration round-trip",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROLE = "internhunter_agent"
VISIBLE_COLUMNS = (
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
HIDDEN_COLUMNS = ("source", "external_id", "posted_date", "first_seen_at", "last_seen_at")


def _config() -> Config:
    os.environ["ALEMBIC_DATABASE_URL"] = SCRATCH_DSN
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return config


def _ensure_agent_role(engine) -> None:
    """Create the operator-provisioned role the migration looks for.

    NOLOGIN is enough for a privilege inspection, and this test never connects
    as the role. The role is left in place because roles are cluster-wide.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                f"DO $$ BEGIN IF NOT EXISTS "
                f"(SELECT 1 FROM pg_roles WHERE rolname = '{AGENT_ROLE}') "
                f"THEN CREATE ROLE {AGENT_ROLE} NOLOGIN; END IF; END $$;"
            )
        )


def _table_select(conn) -> bool:
    return conn.execute(
        text("SELECT has_table_privilege(:role, 'clean_jobs', 'SELECT')"),
        {"role": AGENT_ROLE},
    ).scalar_one()


def _column_select(conn, column: str) -> bool:
    return conn.execute(
        text(
            "SELECT has_column_privilege(:role, 'clean_jobs', :column, 'SELECT')"
        ),
        {"role": AGENT_ROLE, "column": column},
    ).scalar_one()


def test_the_grant_migration_scopes_the_agent_role_to_the_visible_columns() -> None:
    engine = create_engine(SCRATCH_DSN, pool_pre_ping=True)
    _ensure_agent_role(engine)
    with engine.begin() as conn:
        for statement in ingestion_teardown_statements(version_table="alembic_version"):
            conn.execute(text(statement))

    config = _config()
    command.upgrade(config, "head")

    with engine.connect() as conn:
        assert _table_select(conn) is False
        for column in VISIBLE_COLUMNS:
            assert _column_select(conn, column) is True, column
        for column in HIDDEN_COLUMNS:
            assert _column_select(conn, column) is False, column

    command.downgrade(config, "1d032eb356bf")

    with engine.connect() as conn:
        assert _table_select(conn) is True

    # Leave the scratch database at head for whatever runs next.
    command.upgrade(config, "head")
    engine.dispose()
