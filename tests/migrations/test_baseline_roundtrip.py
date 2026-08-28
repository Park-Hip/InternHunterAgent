import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from alembic import command
from alembic.config import Config
from src.services.ingestion.models import Base

SCRATCH_DSN = os.environ.get("SCRATCH_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not SCRATCH_DSN,
    reason="set SCRATCH_DATABASE_URL to a throwaway Postgres to run migration round-trip",
)

REPO_ROOT = Path(__file__).resolve().parents[2]


_TYPE_ALIASES = {
    "BIGINT": "BIGINTEGER",
}


def _normalized_type_name(name: str) -> str:
    name = name.upper()
    return _TYPE_ALIASES.get(name, name)


def _normalized_type(column) -> str:
    return _normalized_type_name(type(column["type"]).__name__)


def test_baseline_upgrade_matches_metadata():
    engine = create_engine(SCRATCH_DSN, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text("DROP TABLE IF EXISTS ingestion_runs, clean_jobs, raw_jobs CASCADE")
        )
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    os.environ["ALEMBIC_DATABASE_URL"] = SCRATCH_DSN
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "b7e2f4a91c3d")
    assert not inspect(engine).has_table("ingestion_runs")

    command.upgrade(alembic_cfg, "head")

    inspector = inspect(engine)

    for table_name, table in Base.metadata.tables.items():
        assert inspector.has_table(table_name), f"missing table {table_name}"

        reflected_columns = {
            col["name"]: col for col in inspector.get_columns(table_name)
        }
        expected_columns = {col.name: col for col in table.columns}

        assert set(reflected_columns) == set(expected_columns), table_name

        for name, expected in expected_columns.items():
            actual = reflected_columns[name]
            assert actual["nullable"] == expected.nullable, (table_name, name)
            assert _normalized_type(actual) == _normalized_type_name(
                type(expected.type).__name__
            ), (table_name, name)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "c9d3e6f7a2b1"
    assert {index["name"] for index in inspector.get_indexes("ingestion_runs")} == {
        "ix_ingestion_runs_finished_at",
        "ix_ingestion_runs_source_started_at",
    }

    command.downgrade(alembic_cfg, "b7e2f4a91c3d")
    downgraded_inspector = inspect(engine)
    assert not downgraded_inspector.has_table("ingestion_runs")
    assert downgraded_inspector.has_table("raw_jobs")
    assert downgraded_inspector.has_table("clean_jobs")

    engine.dispose()
