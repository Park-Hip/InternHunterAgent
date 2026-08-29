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

Added by T0019.3 (2026-07-18) as hidden lifecycle bookkeeping — written by
`upsert_clean_jobs` / `expire_stale_clean_jobs`, never surfaced to the agent:

- `is_active`: `boolean not null default true`. Flipped to `false` by the time-based
  expiry pass; never a `DELETE`. Agent exposure is deferred — see the `is_active` section
  below.
- `first_seen_at`: `timestamptz not null default now()`, insert-only, never refreshed.
- `last_seen_at`: `timestamptz not null default now()`, refreshed on every upsert conflict.

`tests/agents/runtime/test_prompts.py` asserts all three never appear in `schema_context`.

## Frozen Eval Fixture

The `internhunter_eval` database built from `evals/fixtures/seed_eval_db.sql` is the frozen
data fixture for the v1 golden dataset. The fixture contains 22 rows. Reproducible prompt
comparison requires both the schema contract and the fixture data to stay stable unless a
ticket explicitly declares a recalibration.

## Future `is_active` — column shipped, exposure still deferred

**The column now exists; only its agent visibility is deferred.** T0019.3 (2026-07-18) added
`is_active` to `clean_jobs` as a **hidden** lifecycle column — physically present, written by
`upsert_clean_jobs` and `expire_stale_clean_jobs`, but deliberately absent from
`NormalizedJob`, `config/prompts.yaml`, and this contract's visible set. Keep the two
questions apart: *does the column exist* (yes, since T0019.3) versus *can the agent see it*
(no).

Exposure remains the single known future agent-visible addition. Its required gate is T0011.5
baseline calibration, then a prompt-v2 few-shot pass and targeted recalibration delta. T0019 cut
the exposure from its own scope precisely because the
calibration evidence needed to justify an honesty hedge does not yet exist. It is an
additive change and not a reason to delay or weaken this v1 freeze.

**Visible vs. physical column count.** This contract freezes **16 agent-visible** columns;
`clean_jobs` physically has **22** after T0019.3. The gap is 3 pre-existing hidden columns
(`source` and `external_id` bookkeeping, plus `posted_date`, per the notes above) plus the 3
T0019.3 lifecycle columns (`is_active`, `first_seen_at`, `last_seen_at`) — both sets
enumerated under [Hidden DDL Columns](#hidden-ddl-columns) above. A physical column count
that exceeds 16 is expected and is not a contract breach — the enforcement test below checks
the *visible* set and the hidden-column exclusions, not the table width.

These same 6 are the columns T0019.10 removed from `fetch_job_details`'s projection: before
that ticket it ran `SELECT *`, so the hidden set reached the agent verbatim despite this
contract.

## Enforcement

`tests/agents/runtime/test_prompts.py` enforces this contract by checking the visible
columns and hidden-column exclusions across the prompt surfaces.

## Schema evolution

The schema grew from an original four-column sample into the real job-posting shape along a
deliberate cheap-growth path.

- **Adding a column is free in code.** The SQL validator allowlists the *table*, not its columns,
  and the executor and formatter are key-driven, so a new column reaches the answer with no code
  change. Only the schema description the model reads and, where relevant, the honesty rules need an
  edit.
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

### Expand–migrate–contract procedure

Use this procedure any time a shared schema column requires an incompatible type or semantic change.
It is a documentation-only contract until a future ticket declares a concrete migration.
Every destructive boundary includes an explicit rollback condition.

#### Phase 1 — Assess compatibility

1. Enumerate every consumer of the affected column: ORM model fields, SQL query projections,
   prompt surfaces (`config/prompts.yaml`), API schemas (`src/api/schemas.py`), fixtures
   (`evals/fixtures/seed_eval_db.sql`), and evaluation baselines.
2. Confirm the change is genuinely breaking — additive columns use the free-growth path above;
   this procedure applies only to incompatible changes (type rename, semantic restruct, column
   removal, or join/table restructuring).
3. Write the proposed change as a ticket with the full consumer list and rollback plan before any
code touches the branch.

Rollback condition: if any consumer cannot be updated in lockstep, abort and split the change into
smaller ordered tickets.

#### Phase 2 — Expand (schema-level compatible superset)

1. Create a new Alembic migration that adds the new column (or new table) alongside the existing one.
   The new column must accept all current data without loss — for a `tech_stack` array migration,
   the new column would be a `text[]` or `jsonb` while the old comma-separated `text` column remains.
2. Do **not** drop or alter the existing column in this migration.
3. Update `models.py` to map both columns. The old column retains its frozen position in the agent-
   visible contract; the new column is mapped but not yet exposed to the agent.
4. Update ingestion writers to populate both columns on insert and on upsert conflict.
5. Commit and deploy. No agent-visible behavior changes yet.

Rollback condition: the existing column still holds all data; reverting the deployment restores the
previous state automatically.

#### Phase 3 — Deploy compatible writers and readers

1. Ship the ingestion writer update so both columns are populated from the next run forward.
2. Deploy the updated API so new requests observe the dual-column state but the agent-visible
   contract surface remains unchanged.
3. Verify `assert_clean_jobs_schema()` passes with both columns present.

Rollback condition: revert the deployment; the old code still reads and writes the original column.

#### Phase 4 — Backfill real data

1. Run a backfill script (or Alembic migration `downgrade` + `upgrade` with transform logic) that
   migrates existing rows from the old column into the new column.
2. The backfill must be truthful — no synthetic or guessed values. For `tech_stack`, split each
   comma-separated string into array elements; missing values become empty arrays, not `NULL`.
3. Run the backfill against a staging Neon branch first; confirm row counts match and no data is
   lost.

Rollback condition: the old column still contains the original data. If the backfill fails or
produces incorrect results, drop the new column and restart after fixing the script.

#### Phase 5 — Validate data and consumer contract

1. Run the full evaluation suite against the backfilled data with the old agent-visible contract still
   in effect. The observable API behaviour must not change.
2. Confirm `tests/agents/runtime/test_prompts.py` still passes — the hidden-column exclusion test
   must still reject the new column from prompt surfaces.
3. Record the backfill checksum (row count, spot-check values) in the ticket for traceability.

Rollback condition: if validation fails, the new column is abandoned and the old column continues
serving. Re-open the ticket with corrected backfill logic.

#### Phase 6 — Switch (coordinated contract update)

1. Prepare a single coordinated change set covering:
   - `models.py`: unmapping the old column, promoting the new column to the agent-visible position.
   - `config/prompts.yaml`: updating `schema_context`, `system_prompt`, and `sql_generation` to
     reference the new column name and type.
   - `src/api/schemas.py`: updating any field types that depend on the column.
   - `evals/fixtures/seed_eval_db.sql`: seeding the new column format in fixture data.
   - Evaluation baselines: recalibrating T0011.5 and any few-shot references.
2. All pieces ship in one PR so there is no window where the agent reads stale column names or the
   API returns incompatible types.
3. Run `assert_clean_jobs_schema()` after the switch — the ORM-derived column set must match the
   prompt-enumerated set exactly.

Rollback condition: revert the PR. The old column remains populated by the writer deployed in Phase
3 and the previous contract is restored.

#### Phase 7 — Observe

1. Monitor ingestion runs for one full cycle to confirm both columns remain in sync on upsert.
2. Check Langfuse traces for any SQL-generation regressions related to the changed column.
3. Run the targeted evaluation pass to confirm answer quality is within tolerance.

Rollback condition: if regressions exceed tolerance, revert the switch (Phase 6) and re-evaluate
the backfill or prompt changes before retrying.

#### Phase 8 — Contract later (staged contraction)

1. Once observation confirms stability, schedule a separate follow-on migration to remove the old
   column. This is deliberately a different migration from Phase 6 so it can be reviewed and
   approved independently.
2. Before dropping the column, confirm no remaining queries, prompts, or fixtures reference it.
3. The contraction migration is a maintainer-approved action only — it must not land via automated
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
