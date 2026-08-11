# Schema Contract

## Purpose

This document records the frozen v1 deployed schema and API contract for InternHunterAgent.
Downstream prompt tuning, the T0011.5 eval baseline, and the deferred prompt-v2 pass pin to
this contract so before/after comparisons are reproducible. This is the "schemas fixed to
the deployed version" Phase 0 precondition from `research/archive/pre-deploy-refinement-plan.md`.

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

Exposure remains the single known future agent-visible addition. The gate is **no longer
T0014**: it is now T0011.5 baseline calibration → a prompt-v2 few-shot pass → a targeted
recalibration delta. T0019 cut the exposure from its own scope precisely because the
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
