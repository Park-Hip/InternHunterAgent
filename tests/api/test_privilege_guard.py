"""The boot-time privilege check, and the failure it is here to prevent.

A ``GRANT`` belongs to the table object, so rebuilding ``clean_jobs`` drops the read-only
agent role's grant while leaving the role able to authenticate and connect. The check's
whole value is that it runs before a user request does, so these tests deliberately
break the privileges and then assert the boot path refuses.

The read-only role is provisioned here, exactly as ``docs/how-to/operate.md`` documents,
because the role does not exist on a fresh database.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text
from src.api.privilege_guard import AgentPrivilegeError, assert_agent_privileges
from evals.fixtures.loader import (
    fixture_database_endpoint,
    fixture_database_reachable,
    fixture_database_url,
    load_fixture,
)

ROLE = "iha_privilege_probe"
PASSWORD = "privilege_probe_password"

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


def grant(
    engine,
    *,
    table_level: bool = False,
    hidden: tuple[str, ...] = (),
    writable: bool = False,
) -> None:
    """Provision the probe role in the serving shape, or in a drifted one.

    The default is what ``docs/how-to/operate.md`` documents after #722:
    column-level ``SELECT`` on the 16 visible columns and no table-level
    ``SELECT``. ``table_level`` and ``hidden`` exist so the tests can prove the
    boot guard refuses each way that shape can drift.
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
        conn.execute(text(f"REVOKE ALL PRIVILEGES ON clean_jobs FROM {ROLE}"))
        conn.execute(
            text(
                f"REVOKE SELECT ({', '.join(HIDDEN_COLUMNS)})"
                f" ON clean_jobs FROM {ROLE}"
            )
        )
        if table_level:
            conn.execute(text(f"GRANT SELECT ON clean_jobs TO {ROLE}"))
        else:
            columns = ", ".join(VISIBLE_COLUMNS + hidden)
            conn.execute(text(f"GRANT SELECT ({columns}) ON clean_jobs TO {ROLE}"))
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            # GRANT takes TO and REVOKE takes FROM; both name the grantee.
            if writable:
                conn.execute(text(f"GRANT {privilege} ON clean_jobs TO {ROLE}"))
            else:
                conn.execute(text(f"REVOKE {privilege} ON clean_jobs FROM {ROLE}"))


def revoke_read(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"REVOKE ALL PRIVILEGES ON clean_jobs FROM {ROLE}"))
        conn.execute(
            text(
                f"REVOKE SELECT ({', '.join(VISIBLE_COLUMNS + HIDDEN_COLUMNS)})"
                f" ON clean_jobs FROM {ROLE}"
            )
        )


@pytest.fixture
def agent_dsn(monkeypatch, engine):
    """Point the agent DSN at a role whose privileges the test controls."""
    from sqlalchemy.engine import make_url

    from src.core.config import settings

    # The production topology is one database with two roles, so the test needs
    # both DSNs on the fixture database: the writer as the owner, the reader as
    # the role under test.
    url = make_url(fixture_database_url()).set(username=ROLE, password=PASSWORD)
    original_agent = settings.AGENT_DATABASE_URL
    original_serving = settings.DATABASE_URL
    settings.__dict__["AGENT_DATABASE_URL"] = url.render_as_string(hide_password=False)
    settings.__dict__["DATABASE_URL"] = fixture_database_url()

    # Provisioned on the way in as well as on the way out, so a test that revokes
    # cannot leak into the next one.
    grant(engine)

    # The guard uses module-level proxies that cache both the engine and the
    # session factory, so both need clearing for this DSN to be the one it uses.
    from src.core import db as db_module

    original_agent_engine = db_module.__dict__.get("_agent_engine")
    original_agent_session_factory = db_module.__dict__.get("_agent_session_factory")
    db_module.__dict__["_agent_engine"] = None
    db_module.__dict__["_agent_session_factory"] = None
    try:
        yield
    finally:
        settings.__dict__["AGENT_DATABASE_URL"] = original_agent
        settings.__dict__["DATABASE_URL"] = original_serving
        db_module.__dict__["_agent_engine"] = original_agent_engine
        db_module.__dict__["_agent_session_factory"] = original_agent_session_factory
        grant(engine)


class TestTheCheck:
    def test_a_read_only_agent_role_passes(self, engine, agent_dsn) -> None:
        grant(engine, writable=False)
        assert assert_agent_privileges() is True

    def test_a_lost_read_grant_fails_the_boot(self, engine, agent_dsn) -> None:
        grant(engine, writable=False)
        revoke_read(engine)
        with pytest.raises(AgentPrivilegeError, match="cannot read clean_jobs"):
            assert_agent_privileges()

    def test_a_hidden_column_grant_fails_the_boot(self, engine, agent_dsn) -> None:
        """A column grant on one hidden column is the leak this check exists for."""
        grant(engine, hidden=("source",))
        with pytest.raises(AgentPrivilegeError, match="can read a hidden column"):
            assert_agent_privileges()

    def test_a_table_level_grant_fails_the_boot(self, engine, agent_dsn) -> None:
        """Table-level SELECT is the drift that lets SELECT * return 21 columns."""
        grant(engine, table_level=True)
        with pytest.raises(AgentPrivilegeError, match="can read a hidden column"):
            assert_agent_privileges()

    def test_a_writable_agent_role_fails_the_boot(self, engine, agent_dsn) -> None:
        grant(engine, writable=True)
        with pytest.raises(AgentPrivilegeError, match="can write clean_jobs"):
            assert_agent_privileges()

    def test_an_agent_dsn_on_another_database_is_skipped_not_blocked(
        self, engine, agent_dsn, monkeypatch
    ) -> None:
        """A deployment whose agent role lives elsewhere is not blocked by this check.

        It is told the check was skipped, because silently passing a check that did not
        run is how a guard becomes decoration.
        """
        from src.core.config import settings

        settings.__dict__["AGENT_DATABASE_URL"] = (
            "postgresql+psycopg://nobody:nobody@localhost:5432/elsewhere"
        )
        assert assert_agent_privileges() is False

    def test_a_role_that_does_not_exist_fails_rather_than_skips(
        self, agent_dsn
    ) -> None:
        """Point the DSN at a role no run ever creates, rather than dropping the probe.

        ``DROP ROLE`` is cluster-wide, so dropping the shared probe role fails when a
        parallel worktree leaves it a grant in another database on the container. A
        never-created name proves the same thing - an absent role fails the boot
        instead of skipping - without depending on cluster state.
        """
        from sqlalchemy.engine import make_url

        from src.core.config import settings

        absent_role = f"iha_privilege_absent_{uuid.uuid4().hex}"
        settings.__dict__["AGENT_DATABASE_URL"] = make_url(fixture_database_url()).set(
            username=absent_role, password=PASSWORD
        ).render_as_string(hide_password=False)
        with pytest.raises(AgentPrivilegeError):
            assert_agent_privileges()

    def test_the_write_probe_cannot_change_anything(self, engine, agent_dsn) -> None:
        """The probe is a `WHERE false` update, so even a wrong role changes nothing."""
        grant(engine, writable=True)
        before = engine.connect().execute(text("SELECT count(*) FROM clean_jobs")).scalar()
        with pytest.raises(AgentPrivilegeError):
            assert_agent_privileges()
        after = engine.connect().execute(text("SELECT count(*) FROM clean_jobs")).scalar()
        assert before == after == 24
