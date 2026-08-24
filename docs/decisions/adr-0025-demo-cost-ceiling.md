# The demo has a 10 USD monthly cost ceiling

> **Status:** Active · **Decided:** 2026-07-16

## Context

A portfolio demo must not accrue unbounded hosting cost.

## Decision

Expected cost is zero on free tiers; Render Starter is the first sanctioned upgrade if cold starts
or capacity demand it, capped at 10 USD per month.

## Consequences

Upgrade paths (keep-alive windowing, Render Starter) are evaluated against this ceiling; see the
operate how-to.
