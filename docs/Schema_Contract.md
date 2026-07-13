# Schema Contract

## Purpose

This document records the frozen v1 deployed schema and API contract for InternHunterAgent.
Downstream prompt tuning, the T0011.5 eval baseline, and the deferred prompt-v2 pass pin to
this contract so before/after comparisons are reproducible. This is the "schemas fixed to
the deployed version" Phase 0 precondition from `research/pre-deploy-refinement-plan.md`.

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

- `source` and `external_id`: ingestion bookkeeping.
- `posted_date`: deliberately left `NULL`, superseded by `created_on` for freshness
  questions, and kept unreferenced rather than repurposed.

## Frozen Eval Fixture

The `internhunter_eval` database built from `evals/fixtures/seed_eval_db.sql` is the frozen
data fixture for the v1 golden dataset. The fixture contains 22 rows. Reproducible prompt
comparison requires both the schema contract and the fixture data to stay stable unless a
ticket explicitly declares a recalibration.

## Future `is_active`

`is_active` is the single known future agent-visible column planned for T0014. It is an
additive change gated behind scheduled-ingestion work and a targeted recalibration delta.
It is not a reason to delay or weaken this v1 freeze.

## Enforcement

`tests/agents/runtime/test_prompts.py` enforces this contract by checking the visible
columns and hidden-column exclusions across the prompt surfaces.
