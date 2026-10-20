# Schema reference

> **Eviction:** A contract entry leaves when an Alembic migration changes the schema and its
> agent-visible mapping is updated with that migration.

## Purpose

This document records the frozen v1 deployed schema and API contract for InternHunterAgent.
Downstream prompt tuning, the T0011.5 eval baseline, and the deferred prompt-v2 pass pin to
this contract so before/after comparisons are reproducible. This is the "schemas fixed to
the deployed version" Phase 0 precondition from the pre-deploy refinement plan
(preserved on git tag docs-history-pre-redesign).

## Agent-Visible Columns

The v1 agent-visible `clean_jobs` contract has 16 columns:

- `id`
- `title`
- `company`
- `role`
- `description`
- `tech_stack`
- `location`
- `source_url`
- `job_level`
- `listing_expires_on`
- `created_on`
- `is_internship`
- `salary_min`
- `salary_max`
- `salary_currency`
- `is_salary_negotiable`

These columns are enumerated in three prompt surfaces that must stay consistent:

- `config/prompts.yaml` -> `prompts.system_prompt`, the "Available fields" line.
- `config/prompts.yaml` -> `prompts.schema_context`, the `clean_jobs` column list.
- `config/prompts.yaml` -> `prompts.sql_generation`, the "Reference only real columns" line.

The single application-side source is `src/core/column_contract.py`.
The serving schema guard, the privilege guard, the SQL validator, `fetch_job_details`, the evaluation fixture loader, and the prompt-column audit read it there.
The prompt YAML and the ORM keep their own declarations on purpose: they describe the model's vocabulary and the writer's table.
`tests/test_prompt_consistency.py` keeps the contract, the ORM, and the prompt in agreement.

## API Contract

The `/api/v1` request and response contract is already versioned and frozen in
`src/api/schemas.py`.

`QueryRequest` fields:

- `query: str`
- `user_id: str | None = None`
- `session_id: str | None = None`

`QueryResponse` fields:

- `answer: str`
- `session_id: str | None = None`
- `trace_id: str | None = None`
- `trace_url: str | None = None`

## Hidden DDL Columns

The physical `clean_jobs` table still has columns that are deliberately hidden from the
agent:

- `source` and `external_id`: ingestion bookkeeping. Together they are the durable
  cross-run handle for a posting (`id` is only stable within a conversation).
- `posted_date`: deliberately left `NULL`, superseded by `created_on` for freshness
  questions, and kept unreferenced rather than repurposed.

Added by T0019.3 (2026-07-18) as hidden lifecycle bookkeeping - written by
`upsert_clean_jobs`, never surfaced to the agent:

- `first_seen_at`: `timestamptz not null default now()`, insert-only, never refreshed.
- `last_seen_at`: `timestamptz not null default now()`, refreshed on every upsert conflict.

`tests/test_prompt_consistency.py` asserts none of the hidden columns appear in `schema_context`.
The application-side list of hidden names lives in `src/core/column_contract.py`; the SQL validator's explicit-name check, the fixture loader's revoke list, and the prompt audit read it from there.
The `#722` grant migration keeps its own frozen literals, because an applied migration cannot change its meaning later.

## Frozen Eval Fixture

The `internhunter_eval` database built from `evals/fixtures/seed_eval_db.sql` is the frozen
data fixture for the v1 golden dataset. The fixture contains 24 rows. Reproducible prompt
comparison requires both the schema contract and the fixture data to stay stable unless a
ticket explicitly declares a recalibration.

The loader builds and seeds as the fixture owner and then provisions a separate
`internhunter_eval_reader` role with column-level `SELECT` on the 16 contract columns
(#730). The evaluation tool, executor, and SQL scoring read through that role, so the
fixture exercises the same boundary production enforces through `internhunter_agent`.
Re-running the loader rebuilds the schema and re-applies the reader grants.

## Removed `is_active`

The `is_active` column was dropped by ADR-0059, along with the time-based expiry pass that wrote it, so the agent's population is every posting ever collected.
Lifecycle questions stay unsupported by the v1 contract, and any future "recently listed" need is derived at query time from `last_seen_at` under a new decision.

**Visible vs. physical column count.** This contract freezes **16 agent-visible** columns;
`clean_jobs` physically has **21** after ADR-0059. The gap is 3 pre-existing hidden columns
(`source` and `external_id` bookkeeping, plus `posted_date`, per the notes above) plus the 2
remaining lifecycle columns (`first_seen_at`, `last_seen_at`) - both sets enumerated under
[Hidden DDL Columns](#hidden-ddl-columns) above. A physical column count that exceeds 16 is
expected and is not a contract breach. The boot schema guard checks the *visible* names and
types, and the privilege guard checks that the agent role holds no grant beyond them.

These same 5 are the columns T0019.10 removed from `fetch_job_details`'s projection: before
that ticket it ran `SELECT *`, so the hidden set reached the agent verbatim despite this
contract.

## Enforcement

`tests/test_prompt_consistency.py` enforces the visible set across the prompt surfaces, the
ORM, and `src/core/column_contract.py`.
`tests/api/test_schema_guard.py` pins the additive-column tolerance and the type check.
`tests/api/test_privilege_guard.py` pins the complete grant set, and
`tests/services/query/test_executor_bounds.py` proves PostgreSQL refuses a star or whole-row
read through the agent role.

## Schema evolution

The schema grew from an original four-column sample into the real job-posting shape along a
deliberate cheap-growth path.

- **Adding a physical column is hidden by default.** The agent role holds column-level `SELECT` on
  the 16 contract columns only (#722, ADR-0063), so a new column does not reach an answer until a
  migration grants it. The serving schema guard checks the 16 visible names and types and ignores
  extra physical columns, so applying the migration before the code deploy no longer refuses boot.
  Making the column visible is a contract change; see
  [Adding a physical column](#adding-a-physical-column).
- **Adding tables, joins, or renames is the boundary** where this stops being free, because it
  crosses the validator's single-table allowlist. Staying single-table is the design choice that
  keeps evolution cheap.
- **Multi-value fields.** `tech_stack` is a comma-separated string. The path for a richer dataset is
  a Postgres array or JSON column, adopted only when the data demands it.
- **Migrations arrived when both deferral conditions fired.** A migration tool was intentionally not
  adopted until the schema stopped being a fixed sample *and* deployed data became irreplaceable.
  Real ingestion met the first; a live hosted database plus an accumulating raw landing table, which
  holds postings that have dropped out of search and cannot be re-fetched, met the second.
- **Migrations are only half the problem.** A create-if-not-exists silently no-ops on a table whose
  columns drifted out-of-band, which a migration tool does not detect. That is why ingestion carries
  a separate pre-flight column assertion; see [how-to/operate.md](../how-to/operate.md).
- **Breaking-schema changes require a coordinated procedure.** When a column type or semantic contract
  must change incompatibly (for example `tech_stack` from comma-separated text to a PostgreSQL array),
  the agent-visible contract, prompts, fixtures, and evaluations all pivot together. The procedure
  below prevents ad-hoc deployments and keeps the frozen agent-visible contract intact through every
  phase. See [Expand–migrate–contract procedure](#expandmigratecontract-procedure).

### Adding a physical column

The serving path tolerates a column it does not know.
Since ADR-0063 the agent role holds column-level `SELECT` on the 16 visible columns only, so a
new physical column is invisible until a migration grants it.
At boot the schema guard checks that the 16 visible columns exist with their expected PostgreSQL
types and logs any extra physical column as `api.schema_extra_columns`; it does not refuse boot.
The privilege guard then confirms the agent role holds no privilege on the new column, or on any
other relation.

Change in one pull request:

1. Add the Alembic revision (nullable or with a default) and update `CleanJob` and
   `NormalizedJob` in `models.py`, the normalizer, and both dicts in `upsert_clean_jobs`.
2. If the column stays hidden, add it to `HIDDEN_COLUMNS` in `src/core/column_contract.py`.
   No grant, prompt, or fixture change follows.
   The SQL validator and the prompt audit then reject its name explicitly, while the grant
   remains the boundary for a star or whole-row read.
3. If the column should become visible, add it to `VISIBLE_COLUMNS` in the same module, add a
   migration that grants `SELECT` on it to `internhunter_agent`, and update the prompt surfaces,
   `evals/fixtures/seed_eval_db.sql`, and this reference.
   `fetch_job_details` and both guards follow the contract automatically.

Ordering across deploys is asymmetric, and the tolerance is deliberate:

- **A hidden addition** is safe in any order for serving: apply the migration, restart, and boot
  succeeds because the extra column is ignored and un-granted.
  Ingestion still compares the physical table with the ORM exactly (`assert_clean_jobs_schema`),
  so apply the migration with the ORM deploy for ingestion, or let a nightly run abort at
  `schema_check` rather than write a partial row.
- **A visible addition** is a contract change, not a free additive one.
  The privilege guard demands exactly the declared grant set in both directions, so a grant that
  lands before the code release refuses boot just as a code release that lands before the grant
  does.
  Ship the contract, prompt, fixture, and grant migration in one release, then choose a
  maintenance window: apply the grant migration and bring up the release that declares the column.
  Do not restart the previous release in that window; its guard does not know the new grant and
  will also refuse boot.
  That is expected, not a reason to grant more.
- **A new grant is never tolerated.**
  If a migration grants the agent role anything beyond the current contract, or anything on
  another relation, the next boot refuses until the matching contract release is live.
  That is the enforcement that makes the hidden-by-default rule real.

Verify with `uv run pytest tests/api/test_schema_guard.py tests/api/test_privilege_guard.py tests/test_prompt_consistency.py`.

### Expand–migrate–contract procedure

Use this procedure any time a shared schema column requires an incompatible type or semantic change.
It is a documentation-only contract until a future ticket declares a concrete migration.
Every destructive boundary includes an explicit rollback condition.

#### Phase 1 - Assess compatibility

1. Enumerate every consumer of the affected column: ORM model fields, SQL query projections,
   prompt surfaces (`config/prompts.yaml`), API schemas (`src/api/schemas.py`), fixtures
   (`evals/fixtures/seed_eval_db.sql`), and evaluation baselines.
2. Confirm the change is genuinely breaking - additive columns use the free-growth path above;
   this procedure applies only to incompatible changes (type rename, semantic restruct, column
   removal, or join/table restructuring).
3. Write the proposed change as a ticket with the full consumer list and rollback plan before any
code touches the branch.

Rollback condition: if any consumer cannot be updated in lockstep, abort and split the change into
smaller ordered tickets.

#### Phase 2 - Expand (schema-level compatible superset)

1. Create a new Alembic migration that adds the new column (or new table) alongside the existing one.
   The new column must accept all current data without loss - for a `tech_stack` array migration,
   the new column would be a `text[]` or `jsonb` while the old comma-separated `text` column remains.
2. Do **not** drop or alter the existing column in this migration.
3. Update `models.py` to map both columns. The old column retains its frozen position in the agent-
   visible contract; the new column is mapped but not yet exposed to the agent.
4. Update ingestion writers to populate both columns on insert and on upsert conflict.
5. Commit and deploy. No agent-visible behavior changes yet.

Rollback condition: the existing column still holds all data; reverting the deployment restores the
previous state automatically.

#### Phase 3 - Deploy compatible writers and readers

1. Ship the ingestion writer update so both columns are populated from the next run forward.
2. Deploy the updated API so new requests observe the dual-column state but the agent-visible
   contract surface remains unchanged.
3. Verify `assert_clean_jobs_schema()` passes with both columns present.

Rollback condition: revert the deployment; the old code still reads and writes the original column.

#### Phase 4 - Backfill real data

1. Run a backfill script (or Alembic migration `downgrade` + `upgrade` with transform logic) that
   migrates existing rows from the old column into the new column.
2. The backfill must be truthful - no synthetic or guessed values. For `tech_stack`, split each
   comma-separated string into array elements; missing values become empty arrays, not `NULL`.
3. Run the backfill against a staging Neon branch first; confirm row counts match and no data is
   lost.

Rollback condition: the old column still contains the original data. If the backfill fails or
produces incorrect results, drop the new column and restart after fixing the script.

#### Phase 5 - Validate data and consumer contract

1. Run the full evaluation suite against the backfilled data with the old agent-visible contract still
   in effect. The observable API behaviour must not change.
2. Confirm `tests/test_prompt_consistency.py` still passes - the hidden-column exclusion test
   must still reject the new column from prompt surfaces.
3. Record the backfill checksum (row count, spot-check values) in the ticket for traceability.

Rollback condition: if validation fails, the new column is abandoned and the old column continues
serving. Re-open the ticket with corrected backfill logic.

#### Phase 6 - Switch (coordinated contract update)

1. Prepare a single coordinated change set covering:
   - `models.py`: unmapping the old column, promoting the new column to the agent-visible position.
   - `src/core/column_contract.py`: moving the column from `HIDDEN_COLUMNS` to `VISIBLE_COLUMNS` (or replacing it).
   - `config/prompts.yaml`: updating `schema_context`, `system_prompt`, and `sql_generation` to
     reference the new column name and type.
   - `src/api/schemas.py`: updating any field types that depend on the column.
   - `evals/fixtures/seed_eval_db.sql`: seeding the new column format in fixture data.
   - A grant migration that gives `internhunter_agent` `SELECT` on the new column.
   - Evaluation baselines: recalibrating T0011.5 and any few-shot references.
2. All pieces ship in one PR so there is no window where the agent reads stale column names or the
   API returns incompatible types. Apply the grant migration and restart the new release as the
   coordinated cutover described in [Adding a physical column](#adding-a-physical-column).
3. Run `tests/test_prompt_consistency.py`, `tests/api/test_schema_guard.py`, and
   `tests/api/test_privilege_guard.py` after the switch - the contract, the ORM, and the prompts
   must name one set, and the agent role must hold exactly that grant set.

Rollback condition: revert the PR. The old column remains populated by the writer deployed in Phase
3 and the previous contract is restored.

#### Phase 7 - Observe

1. Monitor ingestion runs for one full cycle to confirm both columns remain in sync on upsert.
2. Check Langfuse traces for any SQL-generation regressions related to the changed column.
3. Run the targeted evaluation pass to confirm answer quality is within tolerance.

Rollback condition: if regressions exceed tolerance, revert the switch (Phase 6) and re-evaluate
the backfill or prompt changes before retrying.

#### Phase 8 - Contract later (staged contraction)

1. Once observation confirms stability, schedule a separate follow-on migration to remove the old
   column. This is deliberately a different migration from Phase 6 so it can be reviewed and
   approved independently.
2. Before dropping the column, confirm no remaining queries, prompts, or fixtures reference it.
3. The contraction migration is a maintainer-approved action only - it must not land via automated
   CI without explicit sign-off.

Rollback condition: the old column still exists until the contraction migration is applied.
Reverting the contraction migration restores the dual-column state; data is never lost.

#### Coordination checklist

Every breaking schema migration must complete these coordination points before the switch phase:

| Surface | Owner | Must update |
|---|---|---|
| `src/services/ingestion/models.py` | Engineering | ORM mappings for old and new columns |
| Alembic migration | Engineering | Schema DDL; downgrade path tested |
| `config/prompts.yaml` | Engineering + agent | `schema_context`, `system_prompt`, `sql_generation` |
| `src/api/schemas.py` | Engineering | Pydantic field types |
| `evals/fixtures/seed_eval_db.sql` | Evaluation | Fixture data in new format |
| Evaluation baselines | Evaluation | T0011.5 calibration and few-shot references |
| Production migration approval | Maintainer | Explicit sign-off before contraction |

#### Worked example: `tech_stack` text → PostgreSQL array

1. **Assess**: `tech_stack` is a comma-separated `text` column used in `schema_context`, in SQL
   queries, and in fixture data. Changing it to `text[]` breaks every consumer.
2. **Expand**: add `tech_stack_arr text[]` alongside the existing `tech_stack text`. Ingestion
   writes both. Old column unchanged.
3. **Deploy**: ship writer update; API and agent observe nothing new.
4. **Backfill**: run a script that splits each `tech_stack` string into `tech_stack_arr` elements.
   Verify against a staging Neon branch.
5. **Validate**: run evals with the old contract still active. Confirm no regressions.
6. **Switch**: one coordinated PR updates `models.py`, `prompts.yaml`, `schemas.py`, and the
   fixture. The agent now sees `tech_stack_arr` as the array column.
7. **Observe**: monitor one ingestion cycle and Langfuse traces for regressions.
8. **Contract later**: schedule a separate migration to drop `tech_stack text` after explicit
   maintainer approval.

At no phase do old and new deployments disagree on schema. No destructive operation occurs before
validation and rollback conditions are in place. Agent contract updates are called out explicitly
in the switch phase.
