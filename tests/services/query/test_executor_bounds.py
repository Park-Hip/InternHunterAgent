"""PostgreSQL proofs for the bounded read, against the pinned fixture.

Five properties cannot be proven by reading the SQL, so they are proven by
using the database:

- **A slow statement is cancelled by the server**, at the configured
  ``statement_timeout_ms``, for the read-only role the agent uses.
- **An oversized result is refused** before it is handed to the agent, and that
  refusal happens before the companion count runs.
- **The companion count reports the real match total** for the same snapshot.
- **A later page starts at its offset**, and a page past the end returns no
  rows with the same whole-match total (#721).
- **A write is impossible.** The agent role holds ``SELECT`` only, and the
  bounded read also marks its transaction read-only. Both are tested, because
  either one alone is a single point of failure.

The write case goes through ``_bounded_session`` rather than
``execute_bounded_select``: the executor appends a trailing ``LIMIT``, so
handing it an ``INSERT`` would fail as a syntax error and prove nothing about
the read-only transaction.

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
    _bounded_session,
    execute_bounded_select,
)
from evals.fixtures.loader import (
    fixture_database_endpoint,
    fixture_database_reachable,
    fixture_database_url,
    load_fixture,
)

READER_ROLE = "iha_query_reader_test"
READER_PASSWORD = "reader_test_password"

FIXTURE_ROWS = 24

INSERT_STATEMENT = (
    "INSERT INTO clean_jobs (source, external_id, title, company, role) "
    "VALUES ('x', 'y', 't', 'c', 'Other')"
)


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
    """Bind the executor to the read-only role, as the agent uses it."""
    reader = create_engine(reader_url)
    monkeypatch.setattr("src.services.query.executor.agent_session_factory", reader.connect)
    try:
        yield reader
    finally:
        reader.dispose()


@pytest.fixture
def fixture_count(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM clean_jobs")).scalar()


class TestLeastPrivilege:
    def test_the_reader_role_can_read(self, reader_url) -> None:
        reader = create_engine(reader_url)
        try:
            with reader.connect() as conn:
                assert conn.execute(text("select count(*) from clean_jobs")).scalar() == FIXTURE_ROWS
        finally:
            reader.dispose()

    @pytest.mark.parametrize(
        "statement",
        [
            INSERT_STATEMENT,
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
        # Defense in depth: the owner can write, so only the read-only
        # transaction stands between a query that slipped past the validator
        # and a mutation.
        monkeypatch.setattr("src.services.query.executor.agent_session_factory", engine.connect)

        with pytest.raises(ExecutorError):
            with _bounded_session() as session:
                session.execute(text(INSERT_STATEMENT))

        with engine.connect() as verify:
            assert verify.execute(text("select count(*) from clean_jobs")).scalar() == FIXTURE_ROWS


class TestBounds:
    def test_a_slow_statement_is_cancelled_at_the_configured_timeout(
        self, reader_engine, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 300, "max_result_bytes": 1_000_000},
        )

        started = time.monotonic()
        with pytest.raises(QueryTimeoutError) as raised:
            execute_bounded_select("SELECT pg_sleep(3)", 1)
        elapsed = time.monotonic() - started

        # Without the server-side timeout the statement would complete after 3s.
        assert elapsed < 2.5, f"pg_sleep(3) ran {elapsed:.1f}s; the timeout did not apply"
        assert raised.value.timeout_ms == 300
        assert str(raised.value) == "statement exceeded the 300 ms limit"

    def test_an_oversized_result_is_refused_before_it_is_returned(
        self, reader_engine, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 5000, "max_result_bytes": 16},
        )

        # The window is full (the fixture has more rows than the limit), so the
        # refusal also proves the byte budget is checked before the count runs.
        with pytest.raises(ResultTooLargeError):
            execute_bounded_select("SELECT id, title FROM clean_jobs ORDER BY id", 20)

    def test_a_result_within_the_budget_reports_the_real_match_total(
        self, reader_engine, monkeypatch, fixture_count
    ) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 5000, "max_result_bytes": 262_144},
        )

        bounded = execute_bounded_select("SELECT id FROM clean_jobs ORDER BY id", 20)

        # No sentinel row and no extra row: exactly the 20 first matches, in order.
        assert bounded.rows == [[index] for index in range(1, 21)]
        assert bounded.total_rows == fixture_count == FIXTURE_ROWS

    def test_a_short_result_reports_its_own_size_as_the_total(
        self, reader_engine, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 5000, "max_result_bytes": 262_144},
        )

        bounded = execute_bounded_select(
            "SELECT id FROM clean_jobs WHERE id <= 3 ORDER BY id", 20
        )

        assert bounded.rows == [[1], [2], [3]]
        assert bounded.total_rows == 3

    def test_a_later_page_returns_its_slice_and_the_whole_match_total(
        self, reader_engine, monkeypatch, fixture_count
    ) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 5000, "max_result_bytes": 262_144},
        )

        bounded = execute_bounded_select(
            "SELECT id FROM clean_jobs ORDER BY id", 5, 20
        )

        # #721: the second page starts at row 21, not at row 1.
        assert bounded.rows == [[21], [22], [23], [24]]
        assert bounded.total_rows == fixture_count == FIXTURE_ROWS

    def test_a_page_past_the_end_is_empty_and_keeps_the_whole_match_total(
        self, reader_engine, monkeypatch, fixture_count
    ) -> None:
        monkeypatch.setattr(
            "src.services.query.executor.execution_limits",
            lambda: {"statement_timeout_ms": 5000, "max_result_bytes": 262_144},
        )

        bounded = execute_bounded_select(
            "SELECT id FROM clean_jobs ORDER BY id", 5, 200
        )

        # The page is empty, but the query still matches every fixture row. The
        # model can say "no more postings" instead of "nothing matched".
        assert bounded.rows == []
        assert bounded.total_rows == fixture_count == FIXTURE_ROWS


class TestErrorMapping:
    def test_a_missing_column_maps_to_undefined_column_error(self, reader_engine) -> None:
        with pytest.raises(UndefinedColumnError) as raised:
            execute_bounded_select("SELECT remote FROM clean_jobs", 20)

        assert raised.value.message_primary == 'column "remote" does not exist'
