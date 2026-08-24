# Created-on is preserved, while posted date is never synthesized

> **Status:** Active · **Decided:** 2026-07-09

## Context

The source exposes a churny timestamp that looks like a posting date but changes after
publication.
Ranking by it would present invented freshness as fact.

## Decision

Use the stable source `createdOn` as `created_on` and never synthesize or infer a posted date.

## Consequences

Freshness questions are answered honestly: the agent declines to rank by posting date and offers
listing expiry instead.
Any future posting-date feature needs a truthful source field first.
