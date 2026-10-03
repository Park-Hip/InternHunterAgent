import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from alembic.config import Config
from src.services.ingestion.models import (
    APPEND_ONLY_EVIDENCE_TABLES,
    Base,
    ingestion_teardown_statements,
)

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
        for statement in ingestion_teardown_statements(version_table="alembic_version"):
            conn.execute(text(statement))

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
    assert rows[0][0] == "9d4e7f1a2b60"
    assert {index["name"] for index in inspector.get_indexes("ingestion_runs")} == {
        "ix_ingestion_runs_finished_at",
        "ix_ingestion_runs_source_started_at",
    }
    with engine.begin() as conn:
        triggers = conn.execute(text(
            "SELECT COUNT(*) FROM pg_trigger "
            "WHERE tgname = 'immutable_evidence' AND NOT tgisinternal"
        )).scalar_one()
        assert triggers == len(APPEND_ONLY_EVIDENCE_TABLES)
        plan_id = conn.execute(text(
            "INSERT INTO collection_plans "
            "(source_id, plan_version, declared_scope, declared_caps, requested_fields, "
            "declared_completion_rule, declared_endpoint_set, retrieval_precision, "
            "authorization_revision, configuration_digest, created_at) VALUES "
            "('fixture', 'v1', '{}', '{}', '{}', 'terminal', '{}', 'second', "
            "'synthetic:fixture', 'digest', now()) RETURNING id"
        )).scalar_one()
        run_id = conn.execute(text(
            "INSERT INTO collection_runs "
            "(plan_id, idempotency_key, run_kind, started_at, finished_at, outcome, "
            "coverage_result, observed_record_count, declared_scope_digest, request_count, "
            "failure_category, configuration_digest, input_digest, created_at) VALUES "
            "(:plan_id, 'fixture-run', 'manual', now(), now(), 'failed', 'unknown', 0, "
            "'scope', 1, 'page_failed', 'config', 'input', now()) RETURNING id"
        ), {"plan_id": plan_id}).scalar_one()
        request_id = conn.execute(text(
            "INSERT INTO collection_request_bodies "
            "(collection_run_id, request_ordinal, attempt_number, adapter_id, method, "
            "endpoint_name, endpoint, path_parameters, query_parameters, body, body_digest, "
            "credential_env, declared_caps, requested_fields, sent_at, created_at) VALUES "
            "(:run_id, 1, 1, 'fixture', 'POST', 'search', 'https://api.example.test/scrape', "
            "'{}', '{}', '{}', 'digest', 'FIXTURE_KEY', '{}', '{}', now(), now()) "
            "RETURNING id"
        ), {"run_id": run_id}).scalar_one()
        execution_id = conn.execute(text(
            "INSERT INTO collection_request_executions "
            "(collection_run_id, request_body_id, http_status, transport_error, "
            "response_digest, observed_at, provider_facts, created_at) VALUES "
            "(:run_id, :request_id, 202, NULL, 'digest', now(), '{}', now()) RETURNING id"
        ), {"run_id": run_id, "request_id": request_id}).scalar_one()

    # Every evidence table refuses to be rewritten, not only the plans table: a
    # submitted request or a provider execution that can be edited after the fact is
    # not evidence of anything.
    for table, key in (
        ("collection_plans", plan_id),
        ("collection_request_bodies", request_id),
        ("collection_request_executions", execution_id),
    ):
        for statement in (
            f"UPDATE {table} SET created_at = created_at WHERE id = :id",
            f"DELETE FROM {table} WHERE id = :id",
        ):
            with pytest.raises(DBAPIError, match="append-only"):
                with engine.begin() as conn:
                    conn.execute(text(statement), {"id": key})

    command.downgrade(alembic_cfg, "c9d3e6f7a2b1")
    for evidence_table in reversed(APPEND_ONLY_EVIDENCE_TABLES):
        assert not inspect(engine).has_table(evidence_table)
    command.downgrade(alembic_cfg, "b7e2f4a91c3d")
    downgraded_inspector = inspect(engine)
    assert not downgraded_inspector.has_table("ingestion_runs")
    assert downgraded_inspector.has_table("raw_jobs")
    assert downgraded_inspector.has_table("clean_jobs")

    engine.dispose()
