import json
import os
import re
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

# The literals each check added by this change states, so the parity test compares
# the substance of the rule rather than PostgreSQL's rendering of it.
REQUEST_CHECK_LITERALS = {
    "ck_collection_request_bodies_body": ("'DELETE'", "'GET'", "'HEAD'", "'object'"),
    "ck_collection_request_bodies_credential": ("'^[A-Z][A-Z0-9_]*$'",),
    "ck_collection_request_executions_retention": ("''",),
}

# A constraint the migration states and the metadata cannot: NOT VALID is how a
# retirement applies to new rows only, which is the whole point of retiring a
# representation whose rows already exist.
MIGRATION_ONLY_CHECKS = {"ck_raw_artifacts_retired_execution"}


_TYPE_ALIASES = {
    "BIGINT": "BIGINTEGER",
}


def _normalized_type_name(name: str) -> str:
    name = name.upper()
    return _TYPE_ALIASES.get(name, name)


def _normalized_type(column) -> str:
    return _normalized_type_name(type(column["type"]).__name__)


def _normalized_check(sqltext) -> str:
    """The string literals a check mentions, which is the part a typo changes."""
    if sqltext is None:
        return ""
    value = sqltext if isinstance(sqltext, str) else str(sqltext)
    return tuple(sorted(re.findall(r"'[^']*'", value)))


def _assert_metadata_matches_schema(inspector) -> None:
    """Every table, every column, and every rule the database enforces.

    A column comparison alone would not notice a check constraint, a unique
    constraint, a foreign key or an index that only one of the two files declares,
    and those rules are where the ingestion invariants actually live.
    """
    for table_name, table in Base.metadata.tables.items():
        assert inspector.has_table(table_name), f"missing table {table_name}"

        reflected_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
        expected_columns = {col.name: col for col in table.columns}

        assert set(reflected_columns) == set(expected_columns), table_name

        for name, expected in expected_columns.items():
            actual = reflected_columns[name]
            assert actual["nullable"] == expected.nullable, (table_name, name)
            assert _normalized_type(actual) == _normalized_type_name(
                type(expected.type).__name__
            ), (table_name, name)

        reflected_checks = {check["name"] for check in inspector.get_check_constraints(table_name)}
        expected_checks = {constraint.name for constraint in table.constraints
                           if constraint.__class__.__name__ == "CheckConstraint"}
        # The name is what has to match. PostgreSQL rewrites the text of a check it
        # parsed (`IN` becomes `= any (array[...])`, `<>` becomes `!=`, and every
        # literal gains a cast), so comparing the SQL would compare a parser rather
        # than a rule. What each new check actually refuses is proved by inserting
        # the offending row in the test below, which is the stronger statement.
        assert expected_checks <= reflected_checks, table_name
        # Anything the database enforces beyond the ORM is migration-only, and only
        # the retirement check is: it has to be NOT VALID so the rows it describes
        # survive, which the metadata layer cannot express.
        assert not reflected_checks - expected_checks - MIGRATION_ONLY_CHECKS, table_name

        reflected_uniques = {frozenset(unique["column_names"])
                             for unique in inspector.get_unique_constraints(table_name)}
        expected_uniques = {frozenset(column.name for column in constraint.columns)
                            for constraint in table.constraints
                            if constraint.__class__.__name__ == "UniqueConstraint"}
        assert reflected_uniques == expected_uniques, table_name

        # Each foreign key is a set of (constrained column, referred table) pairs, so
        # a composite key and a single-column one compare in the same shape.
        reflected_foreign_keys = {frozenset(
            (column, fk["referred_table"])
            for column in fk["constrained_columns"])
            for fk in inspector.get_foreign_keys(table_name)}
        expected_foreign_keys = set()
        for constraint in table.constraints:
            if constraint.__class__.__name__ != "ForeignKeyConstraint":
                continue
            pairs = {(element.parent.name, element.column.table.name)
                     for element in constraint.elements}
            expected_foreign_keys.add(frozenset(pairs))
        assert reflected_foreign_keys == expected_foreign_keys, (
            table_name, sorted(reflected_foreign_keys))

        # The literals of every check this change added, compared one by one, so a
        # mistyped method name or secret-name pattern is caught even though the
        # database rewrites the rest of the expression.
        for name, literals in REQUEST_CHECK_LITERALS.items():
            if name not in expected_checks:
                continue
            check = next(check for check in inspector.get_check_constraints(table_name)
                         if check["name"] == name)
            assert _normalized_check(check["sqltext"]) == literals, (name, check["sqltext"])


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

    _assert_metadata_matches_schema(inspector)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "a1c3e5f70924"
    assert {index["name"] for index in inspector.get_indexes("ingestion_runs")} == {
        "ix_ingestion_runs_finished_at",
        "ix_ingestion_runs_source_started_at",
    }
    # Every index on the new execution table is either the one this change declares or
    # the index PostgreSQL builds for a unique constraint, which it names after it.
    declared_indexes = {index.name for index
                        in Base.metadata.tables["collection_request_executions"].indexes}
    reflected_indexes = {index["name"] for index in inspector.get_indexes(
        "collection_request_executions")}
    assert declared_indexes <= reflected_indexes
    # Every index beyond the declared one is the index PostgreSQL builds to enforce a
    # unique constraint, so nothing on the table is an index nobody asked for.
    backing = reflected_indexes - declared_indexes
    assert len(backing) == len(inspector.get_unique_constraints(
        "collection_request_executions"))
    assert all(name.endswith("_key") for name in backing)
    with engine.begin() as conn:
        # The trigger is counted per table, so a trigger on the wrong table fails
        # here rather than being cancelled out by another one.
        triggers = conn.execute(text(
            "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE t.tgname = 'immutable_evidence' AND NOT t.tgisinternal"
        )).scalars().all()
        # Counted per table and against the canonical list, so a trigger on the wrong
        # table fails here instead of being cancelled out by another one.
        assert sorted(triggers) == sorted(APPEND_ONLY_EVIDENCE_TABLES)
        plan_id = conn.execute(text(
            "INSERT INTO collection_plans "
            "(source_id, plan_version, declared_scope, declared_caps, requested_fields, "
            "declared_completion_rule, declared_endpoint_set, retrieval_precision, "
            "authorization_revision, configuration_digest, created_at) VALUES "
            "('fixture', 'v1', '{}', '{}', '{}', 'terminal', '{}', 'second', "
            "'synthetic:fixture', 'digest', now()) RETURNING id"
        )).scalar_one()
    for statement in (
        "UPDATE collection_plans SET plan_version = 'v2' WHERE id = :id",
        "DELETE FROM collection_plans WHERE id = :id",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(text(statement), {"id": plan_id})

    command.downgrade(alembic_cfg, "c9d3e6f7a2b1")
    for evidence_table in (
        "collection_request_executions", "collection_request_bodies", "field_provenance",
        "normalization_results", "duplicate_deliveries", "raw_observations", "raw_artifacts",
        "collection_runs", "collection_plans",
    ):
        assert not inspect(engine).has_table(evidence_table)
    command.downgrade(alembic_cfg, "b7e2f4a91c3d")
    downgraded_inspector = inspect(engine)
    assert not downgraded_inspector.has_table("ingestion_runs")
    assert downgraded_inspector.has_table("raw_jobs")
    assert downgraded_inspector.has_table("clean_jobs")

    engine.dispose()


LEGACY_REPRESENTATION = "provider-execution-v1"


def test_retiring_the_legacy_execution_representation_keeps_existing_rows_readable():
    """A run recorded before the request-attempt tables keeps its execution trace.

    The legacy trace is one raw_artifacts row per run, and the evidence tables are
    append-only, so the migration cannot delete or rewrite it even in principle.
    What it does is stop new runs from writing one, which means a reader has to be
    able to still read the old one: that is what this proves, on a database that
    held such a row before the upgrade.
    """
    engine = create_engine(SCRATCH_DSN, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text("DROP TABLE IF EXISTS collection_request_executions, "
                 "collection_request_bodies, field_provenance, normalization_results, "
                 "duplicate_deliveries, raw_observations, raw_artifacts, "
                 "collection_runs, collection_plans, ingestion_runs, clean_jobs, raw_jobs CASCADE")
        )
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.execute(
            text("DROP FUNCTION IF EXISTS reject_ingestion_evidence_mutation() CASCADE")
        )

    os.environ["ALEMBIC_DATABASE_URL"] = SCRATCH_DSN
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "e51a8c07d942")

    legacy = {
        "record": "provider-execution",
        "request_digest": "d" * 64,
        "execution": {"submit": {"http_status": 202}, "observed_at": "2026-09-27T08:44:34+00:00"},
    }
    with engine.begin() as conn:
        plan_id = conn.execute(text(
            "INSERT INTO collection_plans (source_id, plan_version, declared_scope, declared_caps, "
            "requested_fields, declared_completion_rule, declared_endpoint_set, "
            "retrieval_precision, authorization_revision, configuration_digest, created_at) "
            "VALUES ('fixture', 'legacy-v1', '{}', '{}', '{}', 'terminal', '{}', 'second', "
            "'synthetic:fixture', 'digest', now()) RETURNING id")).scalar_one()
        run_id = conn.execute(text(
            "INSERT INTO collection_runs (plan_id, idempotency_key, run_kind, started_at, "
            "finished_at, outcome, coverage_result, declared_record_cap, observed_record_count, "
            "declared_scope_digest, request_count, failure_category, configuration_digest, "
            "input_digest, created_at) VALUES (:plan, 'legacy-run', 'manual', now(), now(), "
            "'incomplete', 'unknown', 10, 0, 'scope', 1, 'terminal_not_observed', 'config', "
            "'input', now()) RETURNING id"), {"plan": plan_id}).scalar_one()
        artifact_id = conn.execute(text(
            "INSERT INTO raw_artifacts (collection_run_id, content_digest, representation_version, "
            "media_type, byte_length, storage_locator, representation, acquired_at, "
            "retention_disposition, retention_until, authorization_revision, created_at) "
            "VALUES (:run, 'legacy-digest', :version, 'application/json', 1, 'in-row', "
            "CAST(:representation AS jsonb), now(), 'retained_full', now() + interval '1 day', "
            "'synthetic:fixture', now()) RETURNING id"),
            {"run": run_id, "version": LEGACY_REPRESENTATION,
             "representation": json.dumps(legacy)}).scalar_one()

    command.upgrade(alembic_cfg, "head")

    with engine.connect() as conn:
        stored = conn.execute(text(
            "SELECT representation_version, representation FROM raw_artifacts WHERE id = :id"),
            {"id": artifact_id}).one()
    assert stored[0] == LEGACY_REPRESENTATION
    assert stored[1] == legacy
    # The row is still on its run, so the trace of an old run is still reachable
    # from the run that produced it, and the new tables coexist with it.
    with engine.begin() as conn:
        assert conn.execute(text(
            "SELECT COUNT(*) FROM collection_request_bodies WHERE collection_run_id = :run"),
            {"run": run_id}).scalar_one() == 0
        assert conn.execute(text(
            "SELECT COUNT(*) FROM collection_request_executions")).scalar_one() == 0
        # And it is still append-only, exactly as it was before the upgrade.
        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(text("UPDATE raw_artifacts SET content_digest = 'x' WHERE id = :id"),
                             {"id": artifact_id})

    command.downgrade(alembic_cfg, "e51a8c07d942")
    assert inspect(engine).has_table("raw_artifacts")
    assert not inspect(engine).has_table("collection_request_bodies")
    engine.dispose()


def test_the_database_refuses_the_states_the_writer_would_never_write():
    """Each rule of the request records, checked where it is actually enforced.

    The writer states these rules in Python and the database states them again in
    SQL. This proves the second statement is real, so a row cannot be put into the
    evidence by anything that did not go through the writer.
    """
    engine = create_engine(SCRATCH_DSN, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text("DROP TABLE IF EXISTS collection_request_executions, "
                 "collection_request_bodies, field_provenance, normalization_results, "
                 "duplicate_deliveries, raw_observations, raw_artifacts, "
                 "collection_runs, collection_plans, ingestion_runs, clean_jobs, raw_jobs CASCADE")
        )
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.execute(
            text("DROP FUNCTION IF EXISTS reject_ingestion_evidence_mutation() CASCADE")
        )
    os.environ["ALEMBIC_DATABASE_URL"] = SCRATCH_DSN
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")

    with engine.begin() as conn:
        plan_id = conn.execute(text(
            "INSERT INTO collection_plans (source_id, plan_version, declared_scope, "
            "declared_caps, requested_fields, declared_completion_rule, declared_endpoint_set, "
            "retrieval_precision, authorization_revision, configuration_digest, created_at) "
            "VALUES ('fixture', 'constraints-v1', '{}', '{}', '{}', 'terminal', "
            "'{\"submit\": \"https://provider.test/v3/scrape\"}', 'second', "
            "'synthetic:fixture', 'digest', now()) RETURNING id")).scalar_one()
        run_id = conn.execute(text(
            "INSERT INTO collection_runs (plan_id, idempotency_key, run_kind, started_at, "
            "finished_at, outcome, coverage_result, declared_record_cap, observed_record_count, "
            "declared_scope_digest, request_count, failure_category, configuration_digest, "
            "input_digest, created_at) VALUES (:plan, 'constraint-run', 'manual', now(), now(), "
            "'incomplete', 'unknown', 10, 0, 'scope', 1, 'terminal_not_observed', 'config', "
            "'input', now()) RETURNING id"), {"plan": plan_id}).scalar_one()

    def insert_body(**overrides) -> int:
        # The overrides are SQL fragments rather than bound values, because the rules
        # under test are about what the column can hold: a literal SQL null and a
        # literal JSON null are two different states and only one is storable.
        literals = {
            "method": "'POST'", "endpoint": "'https://provider.test/v3/scrape'",
            "endpoint_name": "'submit'", "query_parameters": "'{}'::jsonb",
            "body": "'{}'::jsonb", "credential_env": "'BRIGHTDATA_API_KEY'",
            "request_ordinal": "1", "attempt_number": "1",
        }
        literals.update({key: value for key, value in overrides.items() if key in literals})
        with engine.begin() as conn:
            return conn.execute(text(
                "INSERT INTO collection_request_bodies (collection_run_id, "
                f"{', '.join(literals)}, adapter_id, body_digest, declared_caps, "
                "requested_fields, sent_at, created_at) VALUES "
                f"(:run, {', '.join(literals.values())}, 'fixture-adapter-v1', 'digest', "
                "'{}'::jsonb, '{}'::jsonb, now(), now()) RETURNING id"),
                {"run": run_id}).scalar_one()

    def refused(expected, **overrides):
        with pytest.raises(DBAPIError, match=expected):
            insert_body(**overrides)

    # A body is absent only for a method that carries none by definition, and a
    # stored JSON null is not the absence of a body.
    refused("ck_collection_request_bodies_body", body="NULL")
    refused("ck_collection_request_bodies_body", method="'GET'", body="'null'::jsonb")
    # A credential is a named location, never a value.
    refused("ck_collection_request_bodies_credential", credential_env="'brightdata_api_key'")
    # A position and a retry count are counted from 1.
    refused("ck_collection_request_bodies_position", request_ordinal="0")
    refused("ck_collection_request_bodies_position", attempt_number="0")

    body_id = insert_body()

    def insert_execution(body_id=body_id, ordinal="1", attempt="1", **overrides) -> None:
        literals = {
            "phase": "'submit'", "http_status": "202", "transport_error": "NULL",
            "response_digest": "'digest'", "execution_digest": "'digest'",
            "observed_facts": "'{}'::jsonb", "observed_at": "now()",
            "waited_before_seconds": "0",
            "retention_until": "now() + interval '1 day'",
            "authorization_revision": "'synthetic:fixture'",
            # A None is the SQL null, which is the state most of these rules are
            # about, so it is spelled rather than bound.
            **{key: ("NULL" if value is None else value)
               for key, value in overrides.items()
               if key in ("phase", "http_status", "transport_error", "response_digest",
                          "execution_digest", "observed_facts", "observed_at",
                          "waited_before_seconds", "retention_until",
                          "authorization_revision")},
        }
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO collection_request_executions (collection_run_id, request_body_id, "
                "request_ordinal, attempt_number, phase, http_status, transport_error, "
                "response_digest, execution_digest, observed_facts, observed_at, "
                "waited_before_seconds, retention_until, authorization_revision, created_at) "
                f"VALUES (:run, {body_id}, {ordinal}, {attempt}, "
                f"{', '.join(literals.values())}, now())"),
                {"run": run_id})

    insert_execution()
    # One request has one answer, and a second row for it is refused.
    with pytest.raises(DBAPIError, match="request_body_id"):
        insert_execution()
    # The repeated position cannot name a position its request never had: a second
    # request at ordinal 2 cannot be answered by a row claiming ordinal 1.
    other_body_id = insert_body(request_ordinal="'2'")
    with pytest.raises(DBAPIError, match="collection_request_executions_request_body_id_collection"):
        insert_execution(body_id=other_body_id)
    # A status is present exactly when no transport error is recorded, and no
    # provider answers below 100.
    def fresh_execution(**overrides) -> None:
        """An execution for a request of its own, so one rule is tested at a time."""
        # The position advances before the insert, so a row the database refused still
        # leaves its position used.
        fresh_execution.ordinal += 1
        insert_execution(body_id=insert_body(
            request_ordinal=f"'{fresh_execution.ordinal}'"),
            ordinal=str(fresh_execution.ordinal), **overrides)

    fresh_execution.ordinal = 3
    # A status is present exactly when no transport error is recorded, and no provider
    # answers below 100. A transport failure with no status is the one legal spelling
    # of "nothing came back", and it is stored.
    for overrides, expected in (
        ({"http_status": "202", "transport_error": "'ConnectError'"},
         "ck_collection_request_executions_delivery"),
        ({"http_status": "0"}, "ck_collection_request_executions_status"),
        ({"http_status": None}, "ck_collection_request_executions_delivery"),
    ):
        with pytest.raises(DBAPIError, match=expected):
            fresh_execution(**overrides)
    fresh_execution(http_status=None, transport_error="'ConnectError'")
    # A wait is a nonnegative number of seconds.
    with pytest.raises(DBAPIError, match="ck_collection_request_executions_wait"):
        fresh_execution(waited_before_seconds="-1")
    # The provider's account of a request states how long it may be kept.
    with pytest.raises(DBAPIError, match="not-null constraint"):
        fresh_execution(retention_until="NULL")
    with pytest.raises(DBAPIError, match="ck_collection_request_executions_retention"):
        fresh_execution(authorization_revision="''")
    # And a well-formed one is accepted, so the rules above are refusals and not a
    # table that accepts nothing.
    fresh_execution()    # The retired representation cannot be written again, and what is stored stays
    # append-only.
    with pytest.raises(DBAPIError, match="ck_raw_artifacts_retired_execution"):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO raw_artifacts (collection_run_id, content_digest, "
                "representation_version, media_type, byte_length, storage_locator, "
                "representation, acquired_at, retention_disposition, retention_until, "
                "authorization_revision, created_at) VALUES (:run, 'digest', "
                "'provider-execution-v1', 'application/json', 2, 'in-row', '{}'::jsonb, now(), "
                "'retained_full', now() + interval '1 day', 'synthetic:fixture', now())"),
                {"run": run_id})
    for statement in (
        "UPDATE collection_request_bodies SET endpoint = 'https://elsewhere.test/' WHERE id = :id",
        "DELETE FROM collection_request_bodies WHERE id = :id",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(text(statement), {"id": body_id})
    engine.dispose()
