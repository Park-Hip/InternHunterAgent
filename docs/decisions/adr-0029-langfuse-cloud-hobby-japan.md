# Langfuse Cloud Hobby in Japan provides tracing

> **Status:** Active · **Decided:** 2026-07-16

## Context

Self-hosting Langfuse adds a fourth workload plus ClickHouse maintenance for a small demo.

## Decision

Use Langfuse Cloud Hobby in the Japan region for tracing and evaluation score writeback.

## Consequences

No tracing infrastructure to operate; Hobby-plan ingestion limits shape how much evaluation capture
is run (see the operate how-to gotchas).
