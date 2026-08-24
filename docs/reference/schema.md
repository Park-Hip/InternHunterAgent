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
