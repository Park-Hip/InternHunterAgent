"""The boot-time privilege check, and the failure it is here to prevent.

A ``GRANT`` belongs to the table object, so rebuilding ``clean_jobs`` drops the read-only
agent role's grant while leaving the role able to authenticate and connect. The check's
whole value is that it runs before a user request does, so these tests deliberately
break the privileges and then assert the boot path refuses.

The guard now compares the role's complete catalog privilege set against the contract,
so the tests also prove that a grant on any other relation refuses boot and that a
different or unreachable agent database fails closed instead of skipping the check.

The read-only role is provisioned here, exactly as ``docs/how-to/operate.md`` documents,
because the role does not exist on a fresh database.
"""

from __future__ import annotations

import uuid

import pytest
from psycopg.errors import InsufficientPrivilege
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from evals.fixtures.loader import (
    fixture_database_endpoint,
    fixture_database_reachable,
    fixture_database_url,
    load_fixture,
)
from src.api.privilege_guard import AgentPrivilegeError, assert_agent_privileges
from src.api.schema_guard import assert_serving_schema
from src.core.column_contract import VISIBLE_COLUMN_NAMES

ROLE = "iha_privilege_probe"
PASSWORD = "privilege_probe_password"


@pytest.fixture(scope="module")
def engine():
    if not fixture_database_reachable():
        host, port = fixture_database_endpoint()
        pytest.skip(
            f"Fixture Postgres is not reachable at {host}:{port}; start it with "
            "`docker compose up -d postgres`. A skipped privilege check is not a pass."
        )
    load_fixture()
    eng = create_engine(fixture_database_url())
    yield eng
    eng.dispose()


def _clean_jobs_columns(conn) -> list[str]:
    return list(
        conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'clean_jobs' "
                "ORDER BY ordinal_position"
            )
        ).scalars()
    )


def _revoke_every_clean_jobs_privilege(conn) -> None:
    """Clear table-level and every column-level privilege on clean_jobs.

    A table-level ``REVOKE`` does not clear column grants, so both statements are
    needed. The column list is read from the catalog, which also clears a grant
    on a column a test added and has not dropped yet.
    """
    conn.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE clean_jobs FROM {ROLE}"))
    columns = ", ".join(f'"{column}"' for column in _clean_jobs_columns(conn))
    if columns:
        conn.execute(
            text(f"REVOKE ALL PRIVILEGES ({columns}) ON TABLE clean_jobs FROM {ROLE}")
        )


def _revoke_every_other_relation_privilege(conn) -> None:
    for relation in ("raw_jobs", "ingestion_runs"):
        conn.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {relation} FROM {ROLE}"))
    conn.execute(
        text(f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {ROLE}")
    )


def grant(
    engine,
    *,
    table_level: bool = False,
    hidden: tuple[str, ...] = (),
    extra_columns: tuple[str, ...] = (),
    writable: bool = False,
) -> None:
    """Provision the probe role in the serving shape, or in a drifted one.

    The default is what ``docs/how-to/operate.md`` documents after #722:
    column-level ``SELECT`` on the 16 visible columns and no table-level
    ``SELECT``. The flags exist so the tests can prove the boot guard refuses
    each way that shape can drift.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') "
                f"THEN CREATE ROLE {ROLE} LOGIN PASSWORD '{PASSWORD}'; END IF; END $$;"
            )
        )
        conn.execute(text(f"GRANT CONNECT ON DATABASE internhunter_eval TO {ROLE}"))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {ROLE}"))
        _revoke_every_clean_jobs_privilege(conn)
        _revoke_every_other_relation_privilege(conn)

        if table_level:
            conn.execute(text(f"GRANT SELECT ON clean_jobs TO {ROLE}"))
        else:
            granted = list(
                dict.fromkeys(
                    (*VISIBLE_COLUMN_NAMES, *hidden, *extra_columns)
                )
            )
            columns = ", ".join(granted)
            conn.execute(text(f"GRANT SELECT ({columns}) ON clean_jobs TO {ROLE}"))
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            # GRANT takes TO and REVOKE takes FROM; both name the grantee.
            if writable:
                conn.execute(text(f"GRANT {privilege} ON clean_jobs TO {ROLE}"))
            else:
                conn.execute(text(f"REVOKE {privilege} ON clean_jobs FROM {ROLE}"))


def revoke_read(engine) -> None:
    with engine.begin() as conn:
        _revoke_every_clean_jobs_privilege(conn)


@pytest.fixture
def agent_dsn(engine):
    """Point both DSNs at the fixture database, with the agent as the probe role."""
    from src.core.config import settings
    from src.core import db as db_module

    # The production topology is one database with two roles, so the test needs
    # both DSNs on the fixture database: the writer as the owner, the reader as
    # the role under test.
    url = make_url(fixture_database_url()).set(username=ROLE, password=PASSWORD)
    originals = {
        "AGENT_DATABASE_URL": settings.AGENT_DATABASE_URL,
        "DATABASE_URL": settings.DATABASE_URL,
    }
    settings.__dict__["AGENT_DATABASE_URL"] = url.render_as_string(hide_password=False)
    settings.__dict__["DATABASE_URL"] = fixture_database_url()

    # Both guards use module-level proxies that cache the engine and the session
    # factory, so all four caches need clearing for these DSNs to be used.
    cached = {
        name: db_module.__dict__.get(name)
        for name in (
            "_engine",
            "_session_factory",
            "_agent_engine",
            "_agent_session_factory",
        )
    }
    for name in cached:
        db_module.__dict__[name] = None

    # Provisioned on the way in as well as on the way out, so a test that revokes
    # cannot leak into the next one.
    grant(engine)
    try:
        yield
    finally:
        for name, original in cached.items():
            current = db_module.__dict__.get(name)
            if name in ("_engine", "_agent_engine") and current is not None:
                if current is not original:
                    current.dispose()
            db_module.__dict__[name] = original
        for name, value in originals.items():
            settings.__dict__[name] = value
        grant(engine)


def _reset_agent_engine_cache() -> None:
    """Drop the cached agent engine after a test repoints ``AGENT_DATABASE_URL``."""
    from src.core import db as db_module

    current = db_module.__dict__.get("_agent_engine")
    if current is not None:
        current.dispose()
    db_module.__dict__["_agent_engine"] = None
    db_module.__dict__["_agent_session_factory"] = None


def _agent_engine():
    return create_engine(
        make_url(fixture_database_url())
        .set(username=ROLE, password=PASSWORD)
        .render_as_string(hide_password=False)
    )


class TestTheCheck:
    def test_a_read_only_agent_role_passes(self, engine, agent_dsn) -> None:
        grant(engine)
        assert assert_agent_privileges() is None

    def test_a_lost_read_grant_fails_the_boot(self, engine, agent_dsn) -> None:
        revoke_read(engine)
        with pytest.raises(AgentPrivilegeError, match="missing"):
            assert_agent_privileges()

    def test_a_hidden_column_grant_fails_the_boot(self, engine, agent_dsn) -> None:
        """A column grant on one hidden column is the leak this check exists for."""
        grant(engine, hidden=("source",))
        with pytest.raises(AgentPrivilegeError, match="source"):
            assert_agent_privileges()

    def test_a_table_level_grant_fails_the_boot(self, engine, agent_dsn) -> None:
        """Table-level SELECT is the drift that lets SELECT * return 21 columns."""
        grant(engine, table_level=True)
        with pytest.raises(AgentPrivilegeError, match="clean_jobs"):
            assert_agent_privileges()

    def test_a_writable_agent_role_fails_the_boot(self, engine, agent_dsn) -> None:
        grant(engine, writable=True)
        with pytest.raises(AgentPrivilegeError, match="INSERT"):
            assert_agent_privileges()

    @pytest.mark.parametrize("relation", ["raw_jobs", "ingestion_runs"])
    def test_a_grant_on_another_relation_fails_the_boot(
        self, engine, agent_dsn, relation: str
    ) -> None:
        with engine.begin() as conn:
            conn.execute(text(f"GRANT SELECT ON {relation} TO {ROLE}"))

        with pytest.raises(AgentPrivilegeError, match=relation):
            assert_agent_privileges()

    def test_a_sequence_grant_fails_the_boot(self, engine, agent_dsn) -> None:
        """The census covers sequences too: a sequence is a relation in PostgreSQL."""
        with engine.connect() as conn:
            sequence = conn.execute(
                text("SELECT pg_get_serial_sequence('public.clean_jobs', 'id')")
            ).scalar_one()
        assert sequence is not None

        with engine.begin() as conn:
            conn.execute(text(f"GRANT USAGE ON SEQUENCE {sequence} TO {ROLE}"))

        with pytest.raises(AgentPrivilegeError, match="USAGE"):
            assert_agent_privileges()

    def test_an_extra_clean_jobs_column_boots_and_stays_unreadable(
        self, engine, agent_dsn
    ) -> None:
        """The acceptance case: an additive migration must not cause an outage.

        The schema guard ignores the new column, the privilege guard still sees
        exactly the 16 grants, and PostgreSQL refuses the new column to the role.
        """
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE clean_jobs ADD COLUMN work_mode text"))
        try:
            assert_serving_schema()
            assert_agent_privileges()

            agent = _agent_engine()
            try:
                with agent.connect() as conn:
                    with pytest.raises(DBAPIError) as raised:
                        conn.execute(text("SELECT work_mode FROM clean_jobs LIMIT 1"))
                assert isinstance(raised.value.orig, InsufficientPrivilege)
            finally:
                agent.dispose()
        finally:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE clean_jobs DROP COLUMN IF EXISTS work_mode"))

    def test_a_grant_on_the_extra_column_fails_the_boot(
        self, engine, agent_dsn
    ) -> None:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE clean_jobs ADD COLUMN work_mode text"))
        try:
            grant(engine, extra_columns=("work_mode",))
            with pytest.raises(AgentPrivilegeError, match="work_mode"):
                assert_agent_privileges()
        finally:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE clean_jobs DROP COLUMN IF EXISTS work_mode"))
            grant(engine)

    def test_an_agent_dsn_on_another_database_fails_closed(
        self, engine, agent_dsn
    ) -> None:
        """There is no "nothing to check" deployment: the check inspects the role's DB."""
        from src.core.config import settings

        settings.__dict__["AGENT_DATABASE_URL"] = (
            make_url(fixture_database_url())
            .set(database="postgres", username=ROLE, password=PASSWORD)
            .render_as_string(hide_password=False)
        )
        _reset_agent_engine_cache()

        with pytest.raises(AgentPrivilegeError):
            assert_agent_privileges()

    def test_an_unreachable_agent_database_fails_closed(
        self, engine, agent_dsn
    ) -> None:
        from src.core.config import settings

        settings.__dict__["AGENT_DATABASE_URL"] = (
            "postgresql+psycopg://nobody:nobody@127.0.0.1:1/internhunter_eval"
        )
        _reset_agent_engine_cache()

        with pytest.raises(AgentPrivilegeError, match="failed to inspect"):
            assert_agent_privileges()

    def test_a_role_that_does_not_exist_fails_rather_than_skips(
        self, engine, agent_dsn
    ) -> None:
        """Point the DSN at a role no run ever creates, rather than dropping the probe.

        ``DROP ROLE`` is cluster-wide, so dropping the shared probe role fails when a
        parallel worktree leaves it a grant in another database on the container. A
        never-created name proves the same thing - an absent role fails the boot
        instead of skipping - without depending on cluster state.
        """
        from src.core.config import settings

        absent_role = f"iha_privilege_absent_{uuid.uuid4().hex}"
        settings.__dict__["AGENT_DATABASE_URL"] = (
            make_url(fixture_database_url())
            .set(username=absent_role, password=PASSWORD)
            .render_as_string(hide_password=False)
        )
        _reset_agent_engine_cache()

        with pytest.raises(AgentPrivilegeError):
            assert_agent_privileges()
