# An OFFSET page requires a total order

> **Status:** Active · **Decided:** 2026-10-20

## Context

[#721](https://github.com/Park-Hip/InternHunterAgent/issues/721) preserved a trailing `OFFSET` as a page start.
That only returns two different slices when the statement has a deterministic order.
The SQL generator is not required to emit `ORDER BY`: rule 2 selects `id` first, and ordering appears only in the date and paging rules.
PostgreSQL promises no row order without `ORDER BY`, so page 2 can repeat or skip rows even though the offset is correct.
The prompt asks the model to restate the earlier ordering, but a prompt instruction is not a code guarantee (#727).

An `ORDER BY` alone is not enough either.
`created_on` and every other non-key column can tie, and PostgreSQL may order tied rows differently between the two calls, so the page boundary still moves.
Only a key that is unique and non-null gives a total order.

## Decision

The executor refuses an offset page unless the statement's top-level `ORDER BY` includes `id`, the primary key.
`has_id_tiebreak` in `src/services/query/sql_validator.py` finds the outermost `ORDER BY` and checks its sort keys; an `ORDER BY` inside a subquery or window function does not count.
`execute_bounded_select` raises `UnstableOrderError` before opening a session when `offset > 0` and the check fails.
The tool maps that to the existing `rejected` failure kind, so no SQL runs and the model receives an actionable detail:

    a page with OFFSET needs a stable order: include id in the ORDER BY,
    for example ORDER BY created_on DESC NULLS LAST, id

The SQL-generation prompt's rule 10 makes that shape the normal one: it ends every list of postings with `id` as the last `ORDER BY` key and orders by `id` when the user states no order, and the "newest" rule orders by `created_on DESC NULLS LAST, then id`.
Rule 9 keeps that tiebreaker on a later page.

## Baseline check

The #708 baseline compares match sets, not row order: `evals/sql_check.py` counts ids with `Counter`, and the only case that reads the first row (023) has no tie on `created_on` in the pinned snapshot.
Adding the `id` tiebreaker to a list, or to "newest", therefore cannot change a baseline result; it only makes the order total.

## Alternatives rejected

- **Require any top-level `ORDER BY` and reject only when it is missing.**
  It fixes the unordered case the issue reports but leaves ties on `created_on` able to move the page boundary, so it cannot claim a deterministic order.
- **Have the tool add `ORDER BY id` when no order exists.**
  It needs a rewrite of model-authored SQL, and the clause is invalid for aggregates, `DISTINCT`, grouped results, and set operations.
  A rewrite also hides from the model that the statement it wrote was not pageable.
- **Rely on the prompt alone.**
  This is the behavior #727 was opened to replace: the model can omit the clause or drop the tiebreaker and nothing fails visibly.

## Consequences

- A page request without `id` in its order fails as `rejected` and the model can rewrite it.
  A failed rewrite reaches the reader as a visible tool error, not as overlapping pages.
- The first page of a list has no offset, so the code check does not cover it; rule 10 makes it ordered by `id` for the same total order.
  The evaluation measures whether the model follows it, and the next page's check catches a dropped `id` before it runs.
- `id` is a visible column and rule 2 already makes it the first column of every list, so the required tiebreaker is always selected.
- The check is a shape scan, not a SQL parser.
  It accepts `id` as a bare or qualified sort key and conservatively rejects computed forms such as `lower(id)` or ordinal `ORDER BY 1`; the model can simplify the key and retry.

## Rollback

Revert the code and prompt change. No migration, stored state, or external contract is involved.
