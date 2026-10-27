"""The evaluation path reads through a column-granted, non-owner role (#730).

The fixture loader owns the schema as ``internhunter``. If the evaluation path
also connects as that owner, PostgreSQL bypasses the column grants and a star
query returns all 21 physical columns, so a green evaluation is not evidence
for the production privilege boundary.

These tests are the integration pin. They prove that ``load_fixture()``
provisions the reader role and re-applies its grants after a rebuild, that a
star or hidden-column read is refused by PostgreSQL through that role, and
that the tool maps the refusal to the same ``rejected`` failure production
returns. The module is skipped, never passed, when the fixture is unreachable.
"""

from __future__ import annotations

import asyncio

import pytest
from psycopg.errors import InsufficientPrivilege
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from evals.fixtures.loader import (
    fixture_database_endpoint,
    fixture_database_reachable,
    fixture_database_url,
    fixture_reader_database_url,
    load_fixture,
)
from evals.sql_check import ReaderRoleError, verify_reader_role
from src.core.column_contract import HIDDEN_COLUMN_NAMES, VISIBLE_COLUMN_NAMES


@pytest.fixture(scope="module")
def fixture() -> None:
    if not fixture_database_reachable():
        host, port = fixture_database_endpoint()
        pytest.skip(
            f"Fixture Postgres is not reachable at {host}:{port}. Start it with "
            "`docker compose up -d postgres`, load it with "
            "`uv run python -m evals.fixtures.loader`, and re-run. "
            "A skipped database check is not a pass."
        )
    # The rebuild is the operation under test as much as the query below: the
    # grants have to be re-applied after the schema is dropped and recreated.
    load_fixture()


@pytest.fixture
def reader_engine(fixture):
    engine = create_engine(fixture_reader_database_url())
    try:
        yield engine
    finally:
        engine.dispose()


def test_the_reader_role_has_only_the_contract_columns(reader_engine) -> None:
    visible = ", ".join(VISIBLE_COLUMN_NAMES)
    with reader_engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {visible} FROM clean_jobs ORDER BY id LIMIT 1")
        ).mappings().one()
        assert row["id"] == 1

        assert conn.execute(
            text(
                "SELECT has_table_privilege(current_user, "
                "'public.clean_jobs', 'SELECT')"
            )
        ).scalar_one() is False
        for column in HIDDEN_COLUMN_NAMES:
            assert conn.execute(
                text(
                    "SELECT has_column_privilege(current_user, "
                    "'public.clean_jobs', :column, 'SELECT')"
                ),
                {"column": column},
            ).scalar_one() is False


def test_the_reader_has_the_snapshot_revision(reader_engine) -> None:
    """Snapshot identity reads the revision through the same scoring role."""
    with reader_engine.connect() as conn:
        revision = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert revision


def test_scoring_accepts_only_the_reader_role(fixture) -> None:
    verify_reader_role(fixture_reader_database_url())

    with pytest.raises(ReaderRoleError):
        verify_reader_role(fixture_database_url())


def test_a_star_read_is_refused_by_postgresql(reader_engine) -> None:
    with reader_engine.connect() as conn:
        with pytest.raises(DBAPIError) as raised:
            conn.execute(text("SELECT * FROM clean_jobs LIMIT 1"))
    assert isinstance(raised.value.orig, InsufficientPrivilege)


def test_a_hidden_column_read_is_refused_by_postgresql(reader_engine) -> None:
    with reader_engine.connect() as conn:
        with pytest.raises(DBAPIError) as raised:
            conn.execute(text("SELECT source FROM clean_jobs LIMIT 1"))
    assert isinstance(raised.value.orig, InsufficientPrivilege)


def test_the_tool_maps_a_star_read_to_rejected(reader_engine, monkeypatch) -> None:
    """The evaluation path gets the same failure kind a served turn would."""
    from src.agents.tools import query_clean_jobs as tool
    from src.agents.tools.failures import ToolFailure

    async def star(_request: str) -> str:
        return "SELECT * FROM clean_jobs"

    monkeypatch.setattr(tool, "generate_sql", star)
    monkeypatch.setattr(
        "src.services.query.executor.agent_session_factory", reader_engine.connect
    )

    with pytest.raises(ToolFailure) as raised:
        asyncio.run(tool.run_query_clean_jobs("show me everything"))

    assert raised.value.kind == "rejected"
    assert "16 declared columns" in raised.value.detail
