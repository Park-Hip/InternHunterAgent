"""PostgreSQL proofs for the v1 executor's bounds, against the pinned fixture.

Three properties cannot be proven by reading the SQL, so they are proven by
using the database:

- **A slow statement is cancelled by the server**, at the configured
  ``statement_timeout_ms``, for the read-only role the agent uses.
- **An oversized result is refused** before it is handed to the agent.
- **A write is impossible.** The agent role holds ``SELECT`` only, and the
  executor also marks its transaction read-only. Both are tested, because
  either one alone is a single point of failure.

The whole module is skipped, never passed, when the fixture database is
unreachable. It is not part of the credential-free CI gate.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.query.executor import (
    ExecutorError,
    QueryTimeoutError,
    ResultTooLargeError,
    UndefinedColumnError,
    execute_validated_sql,
)
from evals.fixtures.loader import (
    fixture_database_endpoint,
    fixture_database_reachable,
    fixture_database_url,
    load_fixture,
)

READER_ROLE = "iha_query_reader_test"
READER_PASSWORD = "reader_test_password"


@pytest.fixture(scope="module")
def engine():
    if not fixture_database_reachable():
        host, port = fixture_database_endpoint()
        pytest.skip(
            f"Fixture Postgres is not reachable at {host}:{port}. "
            "Start it with `docker compose up -d postgres`, load it with "
            "`uv run python -m evals.fixtures.loader`, and re-run. "
            "A skipped database check is not a pass."
        )
    try:
        load_fixture()
    except OperationalError as exc:
        pytest.skip(f"eval Postgres not reachable: {exc}")
    eng = create_engine(fixture_database_url())
    yield eng
    eng.dispose()


def provision_reader_role(engine) -> str:
    """Create the documented read-only role, idempotently.

    This mirrors the sequence in docs/how-to/operate.md. The role exists so the
    test can prove the write boundary is enforced by PostgreSQL rather than by
    anything in this repository.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{READER_ROLE}') "
                f"THEN CREATE ROLE {READER_ROLE} LOGIN PASSWORD '{READER_PASSWORD}'; END IF; END $$;"
            )
        )
        conn.execute(text(f"GRANT CONNECT ON DATABASE internhunter_eval TO {READER_ROLE}"))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {READER_ROLE}"))
        conn.execute(text(f"GRANT SELECT ON clean_jobs TO {READER_ROLE}"))
        conn.execute(text(f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON clean_jobs FROM {READER_ROLE}"))
    return READER_ROLE


@pytest.fixture(scope="module")
def reader_url(engine) -> str:
    """The read-only role's DSN, for proving the write boundary is the database's."""
    provision_reader_role(engine)
    return (
        make_url(fixture_database_url())
        .set(username=READER_ROLE, password=READER_PASSWORD)
        .render_as_string(hide_password=False)
    )


@pytest.fixture
def reader_engine(reader_url, monkeypatch):
    """Bind ``execute_validated_sql`` to the read-only role, as the agent uses it."""
    reader = create_engine(reader_url)
    monkeypatch.setattr("src.services.query.executor.agent_session_factory", reader.connect)
    try:
        yield reader
    finally:
        reader.dispose()


class TestLeastPrivilege:
    def test_the_reader_role_can_read(self, reader_url) -> None:
        reader = create_engine(reader_url)
        try:
            with reader.connect() as conn:
                assert conn.execute(text("select count(*) from clean_jobs")).scalar() == 24
        finally:
            reader.dispose()

    @pytest.mark.parametrize(
        "statement",
        [
            "INSERT INTO clean_jobs (source, external_id, title, company, role) "
            "VALUES ('x', 'y', 't', 'c', 'Other')",
            "UPDATE clean_jobs SET title = 'changed' WHERE id = 1",
            "DELETE FROM clean_jobs WHERE id = 1",
            "TRUNCATE clean_jobs",
        ],
    )
    def test_the_reader_role_cannot_write(self, reader_url, statement) -> None:
        reader = create_engine(reader_url)
        try:
            with reader.connect() as conn:
                with pytest.raises(DBAPIError):
                    conn.execute(text(statement))
        finally:
            reader.dispose()

    def test_the_executor_refuses_a_write_even_as_the_table_owner(
        self, engine, monkeypatch
    ) -> None:
        # Defense in depth: the owner can write, so only the transaction default
        # stands between a query that slipped past the validator and a mutation.
        monkeypatch.setattr("src.services.query.executor.agent_session_factory", engine.connect)

        with pytest.raises(ExecutorError):
            execute_validated_sql(
                "INSERT INTO clean_jobs (source, external_id, title, company, role) "
                "VALUES ('x', 'y', 't', 'c', 'Other')"
            )

        with engine.connect() as verify:
            assert verify.execute(text("select count(*) from clean_jobs")).scalar() == 24


class TestBounds:
    def test_a_slow_statement_is_cancelled_at_the_configured_timeout(
        self, reader_engine, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 300, "max_result_bytes": 1_000_000},
        )

        started = time.monotonic()
        with pytest.raises(QueryTimeoutError):
            execute_validated_sql("SELECT pg_sleep(3)")
        elapsed = time.monotonic() - started

        # Without the server-side timeout the statement would complete after 3s.
        assert elapsed < 2.5, f"pg_sleep(3) ran {elapsed:.1f}s; the timeout did not apply"

    def test_an_oversized_result_is_refused_before_it_is_returned(
        self, reader_engine, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 5000, "max_result_bytes": 16},
        )

        with pytest.raises(ResultTooLargeError):
            execute_validated_sql("SELECT id, title FROM clean_jobs")

    def test_a_result_within_the_budget_is_returned(self, reader_engine, monkeypatch) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 5000, "max_result_bytes": 262_144},
        )

        rows = execute_validated_sql("SELECT id FROM clean_jobs ORDER BY id")

        assert len(rows) == 24


class TestErrorMapping:
    def test_a_missing_column_maps_to_undefined_column_error(self, reader_engine) -> None:
        with pytest.raises(UndefinedColumnError):
            execute_validated_sql("SELECT no_such_column FROM clean_jobs")
