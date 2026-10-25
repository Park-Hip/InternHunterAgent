"""The one application-side ``clean_jobs`` column contract.

ADR-0063 gives PostgreSQL ownership of the agent boundary: ``internhunter_agent``
holds column-level ``SELECT`` on the 16 visible columns and no table-level
``SELECT``. A new physical column is therefore invisible to the agent until a
migration grants it, which is why the serving schema guard tolerates columns it
does not know and the privilege guard demands exactly this grant set.

This module is the single source for that set in application code. The serving
schema guard, the privilege guard, the SQL validator's hidden-name filter,
``job_details``, the evaluation fixture loader, and the prompt-column audit all
read it here. The ORM and the prompt YAML keep their own declarations on
purpose: they describe the writer and the model's vocabulary, and a contract
change must still touch them explicitly. Alembic revisions keep frozen
literals, because an applied migration cannot change its meaning later.

Adding a visible column is a contract change, not just a migration: update this
module, the prompt surfaces, the ORM, ``fetch_job_details``, the fixture seed,
and the grant migration together. Adding a hidden column needs the ORM and a
migration; the next boot accepts it and the privilege guard confirms the agent
cannot see it. ``docs/reference/schema.md`` and ``docs/how-to/operate.md`` own
the operator-facing procedure.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping


@dataclass(frozen=True)
class CleanJobColumn:
    """One physical column and the PostgreSQL type the serving path expects."""

    name: str
    sql_type: str


#: Agent-visible columns, in the order the prompt and detail projection use.
VISIBLE_COLUMNS: Final[tuple[CleanJobColumn, ...]] = (
    CleanJobColumn("id", "bigint"),
    CleanJobColumn("title", "text"),
    CleanJobColumn("company", "text"),
    CleanJobColumn("role", "text"),
    CleanJobColumn("description", "text"),
    CleanJobColumn("tech_stack", "text"),
    CleanJobColumn("location", "text"),
    CleanJobColumn("source_url", "text"),
    CleanJobColumn("job_level", "text"),
    CleanJobColumn("listing_expires_on", "date"),
    CleanJobColumn("created_on", "date"),
    CleanJobColumn("is_internship", "boolean"),
    CleanJobColumn("salary_min", "numeric"),
    CleanJobColumn("salary_max", "numeric"),
    CleanJobColumn("salary_currency", "text"),
    CleanJobColumn("is_salary_negotiable", "boolean"),
)

#: Ingestion bookkeeping and lifecycle columns the agent must never read.
HIDDEN_COLUMNS: Final[tuple[CleanJobColumn, ...]] = (
    CleanJobColumn("source", "text"),
    CleanJobColumn("external_id", "text"),
    CleanJobColumn("posted_date", "date"),
    CleanJobColumn("first_seen_at", "timestamp with time zone"),
    CleanJobColumn("last_seen_at", "timestamp with time zone"),
)

#: Everything the contract knows about, visible first.
CONTRACT_COLUMNS: Final[tuple[CleanJobColumn, ...]] = VISIBLE_COLUMNS + HIDDEN_COLUMNS

VISIBLE_COLUMN_NAMES: Final[tuple[str, ...]] = tuple(
    column.name for column in VISIBLE_COLUMNS
)
HIDDEN_COLUMN_NAMES: Final[tuple[str, ...]] = tuple(
    column.name for column in HIDDEN_COLUMNS
)
CONTRACT_COLUMN_NAMES: Final[frozenset[str]] = frozenset(
    column.name for column in CONTRACT_COLUMNS
)

#: Expected ``information_schema.columns.data_type`` per visible column.
VISIBLE_COLUMN_TYPES: Final[Mapping[str, str]] = MappingProxyType(
    {column.name: column.sql_type for column in VISIBLE_COLUMNS}
)
