"""Verify the agent read role's privileges, and fail loudly when they are wrong.

A PostgreSQL ``GRANT`` belongs to the table object, so rebuilding ``clean_jobs`` - by the
evaluation fixture loader, or by a migration that recreates the table - silently drops the
``SELECT`` the read-only agent role was given. The role still exists, still authenticates,
still has ``CONNECT`` and ``USAGE``, and then cannot read anything. That failure arrives
as the first user request, looking like a configuration mistake.

This module turns it into a boot failure instead. It is the second half of the serving
guard: ``assert_serving_schema`` checks that the table is the expected shape, and this
checks that the role the agent reads through can read it and cannot write it.

One thing this deliberately does not assert: that the role cannot read a hidden column.
The documented grant is table-level, so a read-only role can read ``last_seen_at``. The
column boundary is the compiler, and pretending otherwise here would be a check that
passes for the wrong reason.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.engine import make_url

from src.core.config import settings
from src.core.db import agent_session_factory
from src.core.logger import logger


class AgentPrivilegeError(RuntimeError):
    """The agent read role cannot read the table, or can write it. Refuses to serve."""


_READ_PROBE = "SELECT id, title, company, role, description, tech_stack, job_level, location, source_url, listing_expires_on, created_on, is_internship, salary_min, salary_max, salary_currency, is_salary_negotiable FROM clean_jobs LIMIT 1"
# A write that changes nothing. The point is that the database refuses it, not that
# it would have succeeded: `WHERE false` means the probe is safe even if the guard
# is wrong about the role.
_WRITE_PROBE = "UPDATE clean_jobs SET company = company WHERE false"


def _same_database() -> bool:
    """Whether both DSNs name one database, which is the production topology."""
    try:
        agent = make_url(settings.AGENT_DATABASE_URL)
        serving = make_url(settings.DATABASE_URL)
    except Exception as exc:  # a malformed DSN is a configuration failure, not a skip
        raise AgentPrivilegeError(f"agent or serving DSN is unreadable: {exc}") from exc
    return (agent.host, agent.port or 5432, agent.database) == (
        serving.host,
        serving.port or 5432,
        serving.database,
    )


def assert_agent_privileges() -> bool:
    """Fail unless the agent read role can read the visible columns and cannot write.

    Returns ``True`` when the check ran and ``False`` when it could not, which is only
    when the agent DSN names a different database from the serving DSN. A deployment
    whose agent role is configured against another database is not blocked by a check
    that has nothing to check; it is told the check was skipped.
    """
    if not _same_database():
        logger.warning(
            "api.agent_privilege_check_skipped",
            reason="the agent DSN names a different database from the serving DSN",
        )
        return False

    try:
        with agent_session_factory() as session:
            session.execute(text(_READ_PROBE)).mappings().all()
            refused = _write_is_refused(session)
    except AgentPrivilegeError:
        raise
    except (OperationalError, DBAPIError) as exc:
        raise AgentPrivilegeError(
            f"the agent read role cannot read clean_jobs: {exc}. Re-apply the role "
            "sequence in docs/how-to/operate.md; a table rebuild drops the grant."
        ) from exc

    if not refused:
        raise AgentPrivilegeError(
            "the agent read role can write clean_jobs, which the serving contract forbids"
        )
    logger.info("api.agent_privileges_ok", read=True, write=False)
    return True


def _write_is_refused(session) -> bool:
    """Whether the database refused the write probe.

    A refused statement aborts its transaction, which is expected and is why the probe
    runs last.
    """
    try:
        session.execute(text(_WRITE_PROBE))
    except (OperationalError, DBAPIError):
        return True
    return False
