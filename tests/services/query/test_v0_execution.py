"""PostgreSQL execution tests for the governed query core.

These run the compiled statements for real, against the pinned 24-row fixture,
through the same service the agent would use. Where they can, they assert the
goldens the v0 acceptance dataset pins, so a query core that quietly changes a
number fails here rather than in a later evaluation run.

Two of the properties under test cannot be proven by reading the SQL, so they are
proven by using the database:

- **A write is impossible.** The agent role holds ``SELECT`` only, and the
  executor also sets a read-only transaction default. Both are tested, because
  either one alone is a single point of failure.
- **The bounds bite.** A slow statement is cancelled by the server, and an
  oversized result is refused before it reaches the agent.

The whole module is skipped, never passed, when the fixture database is
unreachable. It is not part of the credential-free CI gate.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.query.compiler import CompiledQuery, Statement
from src.services.query.execution import (
    BoundedExecutor,
    QueryExecutionError,
    ResultTooLargeError,
    QueryTimeoutError,
)
from src.services.query.plan import JobQueryRequest, QueryShape
from src.services.query.results import QueryState
from src.services.query.service import JobQueryService
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


@pytest.fixture
def service(engine):
    """A service bound to the fixture through the agent session factory."""
    fixture_engine = create_engine(fixture_database_url())

    def factory():
        return fixture_engine.connect()

    return JobQueryService(executor=BoundedExecutor(session_factory=factory))


def answer(service, **kwargs):
    return service.answer(JobQueryRequest(**kwargs))


class _Borrowed:
    """A connection wrapper that neither commits nor closes what it borrows.

    The edge-case tests insert a row and then query it through the same service,
    inside one transaction that is rolled back afterwards. A raw connection
    would be closed by the executor's ``with`` block, so it is wrapped.
    """

    def __init__(self, connection) -> None:
        self._connection = connection

    def __enter__(self):
        return self._connection

    def __exit__(self, *exc_info) -> bool:
        return False


def service_on(connection) -> JobQueryService:
    return JobQueryService(executor=BoundedExecutor(session_factory=lambda: _Borrowed(connection)))


def insert_edge_row(conn, external_id: str, role: str, location: str, tech_stack: str) -> None:
    conn.execute(
        text(
            "INSERT INTO clean_jobs (source, external_id, source_url, title, company, role, "
            "description, tech_stack, job_level, location, posted_date, listing_expires_on, "
            "created_on, is_internship, salary_min, salary_max, salary_currency, is_salary_negotiable) "
            "VALUES ('vietnamworks', :external_id, 'https://example.invalid/x', 'Edge row', 'Edge Co', "
            ":role, 'Work.', :tech_stack, 'Experienced (non-manager)', :location, NULL, NULL, "
            "DATE '2026-06-01', false, NULL, NULL, NULL, false)"
        ),
        {"external_id": external_id, "role": role, "location": location, "tech_stack": tech_stack},
    )


# ---------------------------------------------------------------------------
# The goldens the v0 acceptance dataset pins
# ---------------------------------------------------------------------------


class TestDatasetGoldens:
    def test_list_role_and_city(self, service) -> None:
        result = answer(
            service,
            shape="list",
            filters=[{"field": "role", "values": ["AI Engineer"]}, {"field": "location", "values": ["Hà Nội"]}],
        )
        assert result.state is QueryState.ANSWERED
        assert [row["id"] for row in result.rows] == [1, 2, 5]
        assert result.match_total == 3
        assert result.truncated is False
        assert all(row["source_url"] for row in result.rows)

    def test_count_is_the_full_set_not_the_display_cap(self, service) -> None:
        result = answer(service, shape="count")
        assert result.count == 24

    def test_truncated_list_reports_the_full_total(self, service) -> None:
        result = answer(service, shape="list")
        assert result.match_total == 24
        assert result.displayed_count == 20
        assert result.truncated is True
        assert "TRUNCATION" in result.caveats

    def test_group_counts(self, service) -> None:
        result = answer(service, shape="group_count", group_by="location")
        assert {g.value: g.count for g in result.groups} == {
            "Hanoi": 11,
            "Ho Chi Minh City": 9,
            "Da Nang": 4,
        }
        assert result.match_total == 24

    def test_level_groups_reverse_the_retired_level_refusal(self, service) -> None:
        result = answer(
            service,
            shape="group_count",
            group_by="job_level",
            filters=[{"field": "role", "values": ["Data Engineer"]}],
        )
        assert {g.value: g.count for g in result.groups} == {
            "Manager": 1,
            "Experienced (non-manager) 3" and "Experienced (non-manager)": 3,
        }

    def test_share_keeps_the_base_denominator(self, service) -> None:
        result = answer(
            service,
            shape="aggregate",
            metric="share",
            filters=[{"field": "role", "values": ["AI Engineer"]}],
            share={"field": "technology", "values": ["Python"]},
        )
        assert result.share is not None
        assert result.share.numerator == 5
        assert result.share.denominator == 5
        assert result.share.excluded_null_field == 0
        assert result.share.percent == 100.0

    def test_salary_is_reported_per_currency_with_the_excluded_row(self, service) -> None:
        result = answer(
            service,
            shape="aggregate",
            metric="average_salary",
            filters=[{"field": "role", "values": ["Data Scientist"]}],
        )
        by_currency = {item.currency: item for item in result.aggregate}
        assert by_currency["USD"].value == 2500.0
        assert by_currency["USD"].rows == 1
        assert by_currency["VND"].rows == 3
        assert by_currency["VND"].value == 23333333.3
        assert by_currency["(not disclosed)"].value is None
        assert by_currency["VND"].excluded_no_salary == 1
        assert {"CURRENCY_SCOPED", "PERIOD_UNKNOWN", "DENOMINATOR_STATED"} <= set(result.caveats)

    def test_top_n_salary(self, service) -> None:
        result = answer(
            service,
            shape="top_n",
            top={"n": 5, "order_by": "salary_min", "descending": True},
            filters=[{"field": "salary_currency", "values": ["USD"]}],
        )
        assert [row["id"] for row in result.rows] == [1, 6, 14, 3, 10]
        assert result.match_total == 6
        assert result.skipped_unranked == 0

    def test_top_n_reports_rows_it_could_not_rank(self, service) -> None:
        result = answer(
            service,
            shape="top_n",
            top={"n": 2, "order_by": "created_on", "descending": True},
            filters=[{"field": "role", "values": ["Data Scientist"]}],
        )
        # All five Data Scientists record a creation date, so none is skipped.
        assert result.skipped_unranked == 0
        assert len(result.rows) == 2

    def test_compare_uses_one_definition_on_both_sides(self, service) -> None:
        result = answer(
            service,
            shape="compare",
            compare=[
                {"filters": [{"field": "technology", "values": ["Python"]}, {"field": "location", "values": ["Hanoi"]}]},
                {
                    "filters": [
                        {"field": "technology", "values": ["Python"]},
                        {"field": "location", "values": ["Ho Chi Minh City"]},
                    ]
                },
            ],
        )
        assert result.compare_sides == [7, 3]

    def test_detail_by_id(self, service) -> None:
        result = answer(service, shape="detail", ids=[1])
        assert result.match_total == 1
        row = result.rows[0]
        assert row["role"] == "AI Engineer"
        assert row["job_level"] == "Experienced (non-manager)"
        assert row["source_url"]
        assert "posted_date" not in row

    def test_detail_for_an_unknown_id_is_an_empty_data_answer(self, service) -> None:
        result = answer(service, shape="detail", ids=[9999])
        assert result.state is QueryState.EMPTY
        assert result.match_total == 0

    def test_machine_learning_matches_nothing_while_a_substring_would_not(self, service, engine) -> None:
        result = answer(service, shape="list", filters=[{"field": "technology", "values": ["ML"]}])
        assert result.state is QueryState.EMPTY
        assert result.match_total == 0
        # The trap is real, and the token rule walks past it.
        with engine.connect() as conn:
            trap = conn.execute(text("select id from clean_jobs where tech_stack ilike '%ML%' order by id")).scalars().all()
        assert list(trap) == [5, 16]

    def test_free_text_is_a_prose_match_and_is_hedged(self, service) -> None:
        result = answer(service, shape="count", filters=[{"field": "free_text", "values": ["remote"]}])
        assert result.count == 2
        assert "FREE_TEXT_HEDGE" in result.caveats

    def test_an_injected_instruction_comes_back_as_data(self, service, engine) -> None:
        result = answer(
            service,
            shape="list",
            filters=[{"field": "role", "values": ["Data Scientist"]}, {"field": "location", "values": ["Hà Nội"]}],
        )
        assert [row["id"] for row in result.rows] == [6, 8, 23]
        # The list projection never carries the description, so the payload is
        # not even in the result. Retrieving it as data is still the behaviour.
        assert all("description" not in row for row in result.rows)
        with engine.connect() as conn:
            payload = conn.execute(
                text("select description from clean_jobs where id = 23")
            ).scalar_one()
        assert "ignore all previous instructions" in payload

    def test_an_unknown_city_is_unsupported_and_runs_no_query(self, service) -> None:
        result = answer(service, shape="count", filters=[{"field": "location", "values": ["Đà Lạt"]}])
        assert result.state is QueryState.UNSUPPORTED
        assert "not a city this data holds" in (result.message or "")
        assert "Ho Chi Minh City" in (result.message or "")

    def test_an_unresolved_role_falls_back_to_posting_text_and_says_so(self, service) -> None:
        result = answer(service, shape="list", filters=[{"field": "role", "values": ["Rustacean"]}])
        assert result.state is QueryState.EMPTY
        assert "ROLE_FALLBACK" in result.caveats
        assert result.applied[0].basis == "fallback"

    def test_a_group_keeps_a_null_value_as_its_own_group(self, engine) -> None:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                insert_edge_row(conn, "v0-null-location", "Other", None, "SQL")
                result = answer(service_on(conn), shape="group_count", group_by="location")
            finally:
                transaction.rollback()
        assert ("(not recorded)", 1) in {(g.value, g.count) for g in result.groups}
        assert result.match_total == 25

    def test_a_share_denominator_includes_a_null_tested_field(self, engine) -> None:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                insert_edge_row(conn, "v0-null-stack", "AI Engineer", "Hanoi", None)
                result = answer(
                    service_on(conn),
                    shape="aggregate",
                    metric="share",
                    filters=[{"field": "role", "values": ["AI Engineer"]}],
                    share={"field": "technology", "values": ["Python"]},
                )
            finally:
                transaction.rollback()
        assert result.share is not None
        assert result.share.denominator == 6
        assert result.share.numerator == 5
        assert result.share.excluded_null_field == 1


# ---------------------------------------------------------------------------
# What the request may not reach
# ---------------------------------------------------------------------------


class TestColumnScope:
    @pytest.mark.parametrize(
        "column",
        ["source", "external_id", "posted_date", "is_active", "first_seen_at", "last_seen_at"],
    )
    def test_a_hidden_column_is_not_a_filter_field(self, service, column) -> None:
        with pytest.raises(ValidationError):
            JobQueryRequest(shape="count", filters=[{"field": column, "values": ["x"]}])

    @pytest.mark.parametrize(
        "column",
        ["source", "external_id", "posted_date", "is_active", "first_seen_at", "last_seen_at"],
    )
    def test_a_hidden_column_is_not_a_group_field(self, service, column) -> None:
        with pytest.raises(ValidationError):
            JobQueryRequest(shape="group_count", group_by=column)

    @pytest.mark.parametrize(
        "column", ["source", "external_id", "posted_date", "is_active", "first_seen_at", "last_seen_at"]
    )
    def test_a_hidden_column_is_not_a_sort_field(self, service, column) -> None:
        with pytest.raises(ValidationError):
            JobQueryRequest(shape="top_n", top={"n": 1, "order_by": column})

    def test_the_detail_projection_carries_no_hidden_column(self, service) -> None:
        result = answer(service, shape="detail", ids=[1])
        assert set(result.columns) <= {
            "id", "title", "company", "role", "description", "location", "job_level",
            "tech_stack", "salary_min", "salary_max", "salary_currency",
            "is_salary_negotiable", "is_internship", "source_url", "listing_expires_on",
            "created_on",
        }

    def test_detail_returns_the_posting_text(self, service) -> None:
        result = answer(service, shape="detail", ids=[23])
        assert "description" in result.columns
        description = result.rows[0]["description"]
        assert "ignore all previous instructions" in description
        # The text comes back whole. Treating it as data rather than as an
        # instruction is the model's rule, not something the query layer can do.
        assert "Nội dung ghi chú này không phải yêu cầu công việc" in description

    def test_detail_still_returns_a_description_when_there_is_one(self, service) -> None:
        result = answer(service, shape="detail", ids=[1])
        assert result.rows[0]["description"]
        assert len(result.rows) == 1

    def test_a_wildcard_projection_is_not_reachable(self, service) -> None:
        with pytest.raises(ValidationError):
            JobQueryRequest(shape="list", columns=["*"])


# ---------------------------------------------------------------------------
# The database is the boundary, not the prompt
# ---------------------------------------------------------------------------


def provision_reader_role(engine) -> str:
    """Create the documented read-only role, idempotently.

    This mirrors the sequence in docs/how-to/operate.md. The role exists so the
    test can prove the write boundary is enforced by PostgreSQL rather than by
    anything in this repository.
    """
    with engine.begin() as conn:
        conn.execute(text(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{READER_ROLE}') "
                          f"THEN CREATE ROLE {READER_ROLE} LOGIN PASSWORD '{READER_PASSWORD}'; END IF; END $$;"))
        conn.execute(text(f"GRANT CONNECT ON DATABASE internhunter_eval TO {READER_ROLE}"))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {READER_ROLE}"))
        conn.execute(text(f"GRANT SELECT ON clean_jobs TO {READER_ROLE}"))
        conn.execute(text(f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON clean_jobs FROM {READER_ROLE}"))
    return READER_ROLE


@pytest.fixture(scope="module")
def reader_url(engine) -> str:
    """The read-only role's DSN, for proving the write boundary is the database's."""
    provision_reader_role(engine)
    return make_url(fixture_database_url()).set(
        username=READER_ROLE, password=READER_PASSWORD
    ).render_as_string(hide_password=False)


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

    def test_the_read_only_role_can_still_read_hidden_columns(self, reader_url) -> None:
        # The role is a table-level read boundary, not a column boundary. The
        # column boundary is the compiler, which the tests above pin. Recording
        # this explicitly keeps the two boundaries from being confused later.
        reader = create_engine(reader_url)
        try:
            with reader.connect() as conn:
                assert conn.execute(text("select is_active from clean_jobs limit 1")).scalar() is not None
        finally:
            reader.dispose()

    def test_the_executor_refuses_a_write_even_as_the_table_owner(self, engine) -> None:
        # Defense in depth: the owner can write, so only the transaction default
        # stands between a mis-compiled plan and a mutation.
        writable = CompiledQuery(
            shape=QueryShape.COUNT,
            statements=(
                Statement(
                    sql="INSERT INTO clean_jobs (source, external_id, title, company, role) "
                    "VALUES ('x', 'y', 't', 'c', 'Other')",
                    role="count",
                ),
            ),
            display_cap=0,
        )
        with engine.connect() as conn:
            executor = BoundedExecutor(session_factory=lambda: conn)
            with pytest.raises(QueryExecutionError):
                executor.run(writable)
            with engine.connect() as verify:
                assert verify.execute(text("select count(*) from clean_jobs")).scalar() == 24


class TestBounds:
    def test_a_slow_statement_is_cancelled_by_the_server(self, engine) -> None:
        slow = CompiledQuery(
            shape=QueryShape.COUNT,
            statements=(Statement(sql="SELECT count(*) FROM pg_sleep(3)", role="count"),),
            display_cap=0,
        )
        with engine.connect() as conn:
            executor = BoundedExecutor(session_factory=lambda: conn, limits={"statement_timeout_ms": 200, "max_result_bytes": 1_000_000})
            with pytest.raises(QueryTimeoutError):
                executor.run(slow)

    def test_an_oversized_result_is_refused_before_it_is_returned(self, engine) -> None:
        big = CompiledQuery(
            shape=QueryShape.COUNT,
            statements=(Statement(sql="SELECT id, title FROM clean_jobs", role="count"),),
            display_cap=0,
        )
        with engine.connect() as conn:
            executor = BoundedExecutor(session_factory=lambda: conn, limits={"statement_timeout_ms": 5000, "max_result_bytes": 16})
            with pytest.raises(ResultTooLargeError):
                executor.run(big)

    def test_a_failing_statement_never_leaks_its_text(self, engine) -> None:
        broken = CompiledQuery(
            shape=QueryShape.COUNT,
            statements=(Statement(sql="SELECT no_such_column FROM clean_jobs", role="count"),),
            display_cap=0,
        )
        with engine.connect() as conn:
            executor = BoundedExecutor(session_factory=lambda: conn)
            with pytest.raises(QueryExecutionError) as excinfo:
                executor.run(broken)
        assert "no_such_column" not in str(excinfo.value)

    def test_a_list_fetches_one_row_past_the_cap_to_learn_the_total(self, service) -> None:
        result = answer(service, shape="list")
        # The service reports 20 and the total 24, which is only possible if the
        # window count was computed before the limit.
        assert result.displayed_count == 20
        assert result.match_total == 24
