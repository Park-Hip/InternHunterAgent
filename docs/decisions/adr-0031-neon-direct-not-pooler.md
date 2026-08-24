# Production Postgres uses Neon directly, not the pooler

> **Status:** Active · **Decided:** 2026-07-16

## Context

Neon's pooler trades prepared-statement support for connection scaling; low request volume does not
justify the trade-off.

## Decision

Migrations and the cron use Neon's direct, non-pooled host.

## Consequences

Alembic works unchanged against production; the operate how-to records the rule so a future pooled
URL does not creep in silently.
