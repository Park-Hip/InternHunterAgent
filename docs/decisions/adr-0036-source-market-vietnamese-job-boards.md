# The source market is Vietnamese job boards, not global ATS aggregators

> **Status:** Active · **Decided:** 2026-06

## Context

The product targets Vietnam AI/Data roles; global ATS APIs do not cover that market well.

## Decision

Ingestion targets Vietnamese job boards; VietnamWorks is the selected initial source (see ADR-0034).
Global ATS aggregation is out of scope.

## Consequences

Schema, cleaning, and city/role normalization are built for Vietnamese sources; additional boards
are future adapters without table reshape.
