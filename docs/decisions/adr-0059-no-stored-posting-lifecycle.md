# Posting lifecycle is not stored, and the agent counts every posting ever collected

> **Status:** Active · **Decided:** 2026-10-07

## Context

`clean_jobs.is_active` was set true on every upsert and false by a nightly expiry pass once
`last_seen_at` was more than seven days old. It was therefore a function of `last_seen_at` and the
run time, and carried nothing `last_seen_at` does not.
No reader used it: ADR-0021 keeps lifecycle data hidden from the agent, and the v0 contract marks
lifecycle questions unsupported. The run counter `expired_count` matched every stale row on every
run, so it never counted new expiries.

## Decision

1. `clean_jobs.is_active`, `ingestion_runs.expired_count`, the expiry pass, and the
   `lifecycle.expire_after_days` setting are removed.
2. The agent's population is every posting ever collected. Answers do not claim that a posting is
   open, as the v0 contract already requires.
3. If "recently listed" is ever needed, it is derived at query time from `last_seen_at`, anchored
   to `MAX(last_seen_at)` so a pause in ingestion does not hide the corpus, under a new decision.

## Consequences

`clean_jobs` has 21 columns. `first_seen_at` and `last_seen_at` remain hidden under ADR-0021,
which stays active.
Counts grow as nightly runs add postings, and the UI dateline keeps stating that results do not
confirm open positions.