# Listing expiry comes from the truthful source expiry field

> **Status:** Active · **Decided:** 2026-07-09

## Context

Open-status questions need a date the source actually maintains.

## Decision

`listing_expires_on` maps from the source expiry field, making open/closed questions answerable
without inventing recency.

## Consequences

Expiry-based answers and filters are grounded; no synthetic recency exists anywhere in the corpus.
