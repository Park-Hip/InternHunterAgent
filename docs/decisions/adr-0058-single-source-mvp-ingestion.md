# Ingestion is one authorized source feeding one serving table

> **Status:** Active · **Decided:** 2026-10-06

## Context

ADR-0055 and ADR-0056 committed ingestion to a provider-neutral evidence-first platform: nine
append-only evidence tables, declared collection plans, per-field provenance, a source registry,
a Bright Data adapter, and five named gates per source.
None of it runs in production. The evidence writer refuses every non-synthetic plan, no Bright
Data collection is authorized, and only tests write the evidence tables.
It accounts for about 2,160 of the ingestion module's 3,900 lines, and the live path imports it.
The product collects from VietnamWorks alone.

## Decision

MVP ingestion is a single-source batch: VietnamWorks to `raw_jobs` to `clean_jobs`, with one
`ingestion_runs` row per attempt.

1. The evidence layer is removed: the shadow evidence writer, collection plans, the nine evidence
   tables and their trigger function, and the `plans:` configuration block. The removed design
   stays recoverable from git tag `ingestion-evidence-archive`.
2. The Bright Data / LinkedIn adapter and normalizer are removed. No second source is in scope.
3. There is no source abstraction (registry or base class) until a second source is approved. The
   loader calls the VietnamWorks adapter and normalizer directly.
4. A record that cannot be normalized, or that fails a row-quality rule, is dropped and counted.
   The run aborts only when dropped records exceed `safety.max_rejected_ratio` of fetched
   records, set to 0.10.
5. `raw_jobs` mirrors the latest payload per `(source, external_id)`. It is not a history, and
   rebuilding `clean_jobs` from it restores only the latest state.
6. The VietnamWorks robots preflight, including its RFC 9309 parser, stays as decided in ADR-0034.
7. Collection from VietnamWorks is authorized by ADR-0034 alone. The ingestion gate register is
   retired.

## Consequences

ADR-0055 and ADR-0056 are superseded. The evidence-first blueprint is a historical record.
Adding a second source requires a new decision record and a small source interface at that time.
The evidence tables are dropped through an Alembic revision whose downgrade recreates them.
ADR-0010, ADR-0011, ADR-0021, and ADR-0034 remain active.