# Lifecycle data is hidden until honesty behavior is measured

> **Status:** Active · **Decided:** 2026-07-16

## Context

`is_active` mechanics exist in the data layer, but exposing them to the agent before honest
presentation of lifecycle facts is measured risks new fabrication modes.

## Decision

Ship lifecycle columns in ingestion; keep them out of the agent-visible contract until evaluation
evidence supports an honest presentation.

## Consequences

Adding lifecycle answers later is column-cheap (schema growth law); exposing early would be an
unmeasured honesty risk.
