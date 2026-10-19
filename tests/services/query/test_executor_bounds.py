"""PostgreSQL proofs for the bounded read, against the pinned fixture.

Four properties cannot be proven by reading the SQL, so they are proven by
using the database:

- **A slow statement is cancelled by the server**, at the configured
  ``statement_timeout_ms``, for the read-only role the agent uses.
- **An oversized result is refused** before it is handed to the agent, and that
  refusal happens before the companion count runs.
- **The companion count reports the real match total** for the same snapshot.
- **A write is impossible.** The agent role holds ``SELECT`` only, and the
  bounded read also marks its transaction read-only. Both are tested, because
  either one alone is a single point of failure.
- **A star, whole-row, or off-contract read is impossible.** The role holds
  column-level ``SELECT`` on the 16 contract columns and no table-level
  ``SELECT`` (#722), so the database, not the validator, refuses the forms a
  hidden-column token check cannot see.

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
    PermissionDeniedError,
    QueryTimeoutError,
    ResultTooLargeError,
    UndefinedColumnError,
    _bounded_session,
    execute_bounded_select,
)
from src.services.query.sql_validator import validate_sql
from evals.fixtures.loader import (
    fixture_database_endpoint,
    fixture_database_reachable,
    fixture_database_url,
    load_fixture,
)

READER_ROLE = "iha_query_reader_test"
READER_PASSWORD = "reader_test_password"

FIXTURE_ROWS = 24

# The 16 contract columns and the five hidden ones, in the same order as
# src/api/privilege_guard.py and the grant migration.
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

    This mirrors the sequence in docs/how-to/operate.md after #722. The role
    exists so the test can prove the write and column boundaries are enforced
    by PostgreSQL rather than by anything in this repository.
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
        conn.execute(text(f"REVOKE ALL PRIVILEGES ON clean_jobs FROM {READER_ROLE}"))
        conn.execute(
            text(
                f"REVOKE SELECT ({', '.join(HIDDEN_COLUMNS)})"
                f" ON clean_jobs FROM {READER_ROLE}"
            )
        )
        conn.execute(
            text(
                f"GRANT SELECT ({', '.join(VISIBLE_COLUMNS)})"
                f" ON clean_jobs TO {READER_ROLE}"
            )
        )
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


class TestErrorMapping:
    def test_a_missing_column_maps_to_undefined_column_error(self, reader_engine) -> None:
        with pytest.raises(UndefinedColumnError) as raised:
            execute_bounded_select("SELECT remote FROM clean_jobs", 20)

        assert raised.value.message_primary == 'column "remote" does not exist'


class TestTheColumnBoundary:
    """#722: the grant, not the validator, refuses star and whole-row reads.

    The validator rejects a hidden column by name; it cannot see through a
    star, an alias, a subquery, a CTE, or a whole-row reference. These cases
    pin that the database refuses all of them for the role the agent uses.
    """

    @pytest.mark.parametrize(
        "statement",
        [
            "SELECT * FROM clean_jobs",
            "SELECT c.* FROM clean_jobs AS c",
            "SELECT id FROM (SELECT * FROM clean_jobs) AS q",
            "WITH x AS (SELECT * FROM clean_jobs) SELECT id FROM x",
            "SELECT clean_jobs FROM clean_jobs",
            "SELECT to_jsonb(clean_jobs) FROM clean_jobs",
        ],
    )
    def test_a_star_or_whole_row_read_is_refused_by_the_grant(
        self, reader_engine, statement
    ) -> None:
        with pytest.raises(PermissionDeniedError):
            execute_bounded_select(statement, 20)

    def test_explicit_contract_columns_still_return_rows(self, reader_engine) -> None:
        columns = ", ".join(VISIBLE_COLUMNS)

        bounded = execute_bounded_select(
            f"SELECT {columns} FROM clean_jobs ORDER BY id", 1
        )

        assert list(bounded.columns) == list(VISIBLE_COLUMNS)
        assert len(bounded.rows) == 1
        assert len(bounded.rows[0]) == len(VISIBLE_COLUMNS)

    def test_a_star_over_a_projected_subquery_still_works(self, reader_engine) -> None:
        bounded = execute_bounded_select(
            "SELECT * FROM (SELECT id, title FROM clean_jobs ORDER BY id) AS q", 20
        )

        assert list(bounded.columns) == ["id", "title"]

    def test_the_validator_accepts_star_and_the_grant_refuses_it(
        self, reader_engine
    ) -> None:
        """The acceptance pin: the validator stays a SQL-shape filter, the grant
        is the column boundary, and the end-to-end result is a visible refusal."""
        validation = validate_sql("SELECT * FROM clean_jobs")

        assert validation.valid is True
        with pytest.raises(PermissionDeniedError):
            execute_bounded_select(validation.sql, 20)
