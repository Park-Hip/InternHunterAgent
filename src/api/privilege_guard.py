"""Verify the agent read role's privileges, and fail loudly when they are wrong.

A PostgreSQL ``GRANT`` belongs to the table object, so rebuilding ``clean_jobs`` - by the
evaluation fixture loader, or by a migration that recreates the table - silently drops the
``SELECT`` the read-only agent role was given. The role still exists, still authenticates,
still has ``CONNECT`` and ``USAGE``, and then cannot read anything. That failure arrives
as the first user request, looking like a configuration mistake.

This module turns it into a boot failure instead. It is the second half of the serving
guard: ``assert_serving_schema`` checks the columns the agent reads, and this checks the
role's entire effective privilege set from the PostgreSQL catalogs. The only privilege it
may hold anywhere is column-level ``SELECT`` on the 16 visible columns of
``public.clean_jobs`` (#722, ADR-0063). Anything else - a table-level grant, a grant on a
hidden column, a write, or any privilege on another relation such as ``raw_jobs`` or the
checkpoint tables - refuses boot.

The old version probed the 16 visible columns, the five hidden ones, and one write. That
proved narrow facts and let a grant on any other relation boot. The census below asks the
catalog for everything and compares the complete set, so a stray grant has nowhere to hide.
It also fails closed when the agent DSN names another database: there is no "nothing to
check" deployment, because the role the agent uses is always the role this guard inspects.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from src.core.column_contract import VISIBLE_COLUMN_NAMES
from src.core.db import agent_session_factory
from src.core.logger import logger


class AgentPrivilegeError(RuntimeError):
    """The agent read role holds a privilege outside the serving contract. Refuses to serve."""


#: One row per effective privilege the agent role holds on a non-system relation.
#:
#: ``has_*_privilege`` resolves inherited and PUBLIC grants, so the census reflects what
#: the role can actually do. Column checks run separately because a table-level grant
#: implies every column; that makes a table grant show up here as 21 column rows, which
#: the expected set rejects just as clearly as the table row itself.
#:
#: ``MAINTAIN`` exists only on PostgreSQL 17+. The lateral row is filtered by server
#: version before ``has_table_privilege`` is called with it, so the same statement runs on
#: 16 (the local and CI version) without "unrecognized privilege type".
_PRIVILEGE_CENSUS = """
WITH relations AS (
    SELECT n.nspname AS schema_name,
           c.relname AS relation_name,
           c.oid AS relation_oid,
           c.relkind
    FROM pg_catalog.pg_class AS c
    JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND n.nspname NOT LIKE 'pg_toast%'
      AND n.nspname NOT LIKE 'pg_temp_%'
      AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
),
relation_privileges AS (
    SELECT 'relation' AS scope,
           r.schema_name,
           r.relation_name,
           NULL::text AS column_name,
           p.privilege
    FROM relations AS r
    CROSS JOIN LATERAL (
        SELECT unnest(
            ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE',
                  'REFERENCES', 'TRIGGER']
        ) AS privilege
        UNION ALL
        SELECT 'MAINTAIN'
        WHERE current_setting('server_version_num')::int >= 170000
    ) AS p
    WHERE r.relkind <> 'S'
      AND pg_catalog.has_table_privilege(
          current_user,
          pg_catalog.format('%I.%I', r.schema_name, r.relation_name),
          p.privilege
      )
),
sequence_privileges AS (
    SELECT 'relation' AS scope,
           r.schema_name,
           r.relation_name,
           NULL::text AS column_name,
           p.privilege
    FROM relations AS r
    CROSS JOIN (VALUES ('SELECT'), ('UPDATE'), ('USAGE')) AS p(privilege)
    WHERE r.relkind = 'S'
      AND pg_catalog.has_sequence_privilege(
          current_user,
          pg_catalog.format('%I.%I', r.schema_name, r.relation_name),
          p.privilege
      )
),
column_privileges AS (
    SELECT 'column' AS scope,
           r.schema_name,
           r.relation_name,
           a.attname AS column_name,
           p.privilege
    FROM relations AS r
    JOIN pg_catalog.pg_attribute AS a
      ON a.attrelid = r.relation_oid
     AND a.attnum > 0
     AND NOT a.attisdropped
    CROSS JOIN (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('REFERENCES'))
        AS p(privilege)
    WHERE r.relkind IN ('r', 'p', 'v', 'm', 'f')
      AND pg_catalog.has_column_privilege(
          current_user,
          pg_catalog.format('%I.%I', r.schema_name, r.relation_name),
          a.attname,
          p.privilege
      )
)
SELECT scope, schema_name, relation_name, column_name, privilege
FROM relation_privileges
UNION ALL
SELECT scope, schema_name, relation_name, column_name, privilege
FROM sequence_privileges
UNION ALL
SELECT scope, schema_name, relation_name, column_name, privilege
FROM column_privileges
"""

Privilege = tuple[str, str, str, str | None, str]


def _expected_privileges() -> frozenset[Privilege]:
    """The complete privilege set the serving contract allows."""
    return frozenset(
        ("column", "public", "clean_jobs", column, "SELECT")
        for column in VISIBLE_COLUMN_NAMES
    )


def _describe(privileges: set[Privilege] | frozenset[Privilege]) -> list[str]:
    """Render privilege tuples compactly, with the column only when there is one."""
    return sorted(
        f"{schema}.{relation}"
        + (f".{column}" if column is not None else "")
        + f":{privilege}"
        for scope, schema, relation, column, privilege in privileges
    )


def assert_agent_privileges() -> None:
    """Refuse boot unless the agent role holds exactly the 16 column grants.

    Raises AgentPrivilegeError when the role cannot be reached, when the census
    fails, or when the effective privilege set differs from the contract in
    either direction. The message names the missing and unexpected grants and
    points at the re-grant procedure in ``docs/how-to/operate.md``.
    """
    try:
        with agent_session_factory() as session:
            actual = {
                (row[0], row[1], row[2], row[3], row[4])
                for row in session.execute(text(_PRIVILEGE_CENSUS))
            }
    except (OperationalError, DBAPIError) as exc:
        raise AgentPrivilegeError(
            f"failed to inspect the agent read role's privileges: {exc}. Re-apply the "
            "role sequence in docs/how-to/operate.md; a table rebuild drops the grant."
        ) from exc

    expected = _expected_privileges()
    missing = expected - actual
    unexpected = actual - expected

    if missing or unexpected:
        logger.error(
            "api.agent_privilege_drift",
            missing=_describe(missing),
            unexpected=_describe(unexpected),
        )
        raise AgentPrivilegeError(
            "the agent read role's privileges do not match the serving contract: "
            f"missing={_describe(missing)} unexpected={_describe(unexpected)}. "
            "Grant SELECT on exactly the 16 visible columns of public.clean_jobs and "
            "nothing else; see docs/how-to/operate.md."
        )

    logger.info("api.agent_privileges_ok", columns=len(expected), extra_privileges=0)
