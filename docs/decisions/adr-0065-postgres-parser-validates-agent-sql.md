# The PostgreSQL parser validates and bounds agent SQL

> **Status:** Active · **Decided:** 2026-10-20

## Context

The query path vetted model-authored SQL with text scans.
A keyword denylist decided which functions were dangerous, a regular expression found the relation after `FROM`, another found a trailing `LIMIT`/`OFFSET`, and a column-name search refused five hidden columns ([#617](https://github.com/Park-Hip/InternHunterAgent/issues/617) row 5, [#736](https://github.com/Park-Hip/InternHunterAgent/issues/736)).
A text scan cannot tell a comment from `--` inside a string literal, a CTE from a table, or `LIMIT 2 + 1` from no bound at all, and it produced three concrete defects:

- A statement whose only reading of a forbidden table was inside a string literal or an alias could be refused, while a shape it did not model could be accepted.
- A CTE, a parenthesised `SELECT`, or a set-returning function such as `string_to_table` in `FROM` was refused or misread, so the documented "count a posting once per city it lists" question could not run.
- `FETCH FIRST`, `LIMIT ALL`, and a non-literal `LIMIT` were not recognised as the statement's own bound.
  The executor appended a second `LIMIT`, PostgreSQL reported a syntax error, and the tool surfaced `unavailable` instead of a reason the model could act on ([#721](https://github.com/Park-Hip/InternHunterAgent/issues/721), [#742](https://github.com/Park-Hip/InternHunterAgent/issues/742)).

The function check was also a denylist.
A function that was not named stayed available by default, including functions added by a later PostgreSQL release.

## Decision

Every agent-authored statement is parsed once with `pglast`, which bundles `libpg_query`, the PostgreSQL parser compiled as a library.
`src/services/query/statement.py` reads every fact from the tree and the guard, the row bound, and the offset-order check all use it.

The statement contract is:

- One statement, starting with `SELECT`, `WITH`, or a parenthesised `SELECT`.
  CTEs, subqueries, set operations, and set-returning functions in `FROM` are all part of a `SELECT` and are allowed.
- No SQL comments, detected as scanner tokens so `--` inside a string literal stays data.
- No `SELECT INTO`, no row-locking clause, and no data-modifying statement in a `WITH` clause.
- Every relation is `clean_jobs` or `public.clean_jobs`, or a CTE in scope.
  `clean_jobs` appears at most once per `FROM` clause, so a self-join cannot multiply the row set.
  A CTE name is local exactly where PostgreSQL makes it visible; without `RECURSIVE`, a CTE's reference to its own name is the real table and is checked as one.
- Every function is on an explicit allowlist grouped by role: aggregates, window functions, string, regular expression, date and time, math, array, and the set-returning helpers `string_to_table`, `unnest`, and `string_to_array`.
  Two string helpers, `like_escape` and `similar_to_escape`, are listed because PostgreSQL rewrites `LIKE ... ESCAPE` and `SIMILAR TO` into them, so the tree names a function the model did not write.
  Server identity functions (`version`, `current_user`, `current_database`, `inet_server_addr`, `current_setting`, and the rest of that family) and server-side calls (`pg_sleep`, large-object and file access, `dblink`, advisory locks) are refused with a reason that names them.
- No hidden ingestion or lifecycle column is named.
  Only the last field of a `ColumnRef` is a column, so a table alias or a CTE name that happens to match is not a read.
- Bounds are integer literals read from the tree.
  `LIMIT ALL` means no user bound, `FETCH FIRST n ROWS ONLY` is a limit, and `FETCH ... WITH TIES` is refused because a tie needs a unique order to be a row count.
  A non-literal or negative bound is refused with a named reason instead of being left for the executor to corrupt.
  The clause is removed from the text whether the statement is bare or fully parenthesised, so the executor's own clause is appended after the statement rather than inside it.
- The offset-order rule of [ADR-0064](adr-0064-offset-pages-require-a-total-order.md) reads the outermost `ORDER BY` from the tree instead of scanning text.

The parser decides shape and scope.
It does not take back the column boundary: the grant on the 16 declared columns stays the boundary ([ADR-0063](adr-0063-database-owns-agent-column-boundary.md)), so a star or a whole-row read passes the guard and is refused by PostgreSQL.

The split breakdown is the acceptance case for the shape rules:

    SELECT trim(one_city) AS city, count(*) AS count
    FROM clean_jobs, string_to_table(location, ',') AS one_city
    GROUP BY 1
    ORDER BY count DESC, city

`string_to_table` multiplies each posting into one row per listed city, so a posting that lists two cities is counted once under each.
`unnest(string_to_array(tech_stack, ','))` answers the same question for technologies.
Both run against the fixture as integration tests, and a posting with a two-city value is counted twice inside a transaction that is rolled back.

## Baseline check

Every case from the #617 row 5 probe set is a unit test: a CTE, a parenthesised `SELECT`, a lateral `string_to_table`, `unnest` over `string_to_array`, a set operation, a scalar subquery that reads `clean_jobs` in its own scope, `public.clean_jobs`, a comment inside a literal, the identity functions, a data-modifying CTE, `FOR UPDATE`, a self-join, hidden columns in a subquery, and each bound form.
The #708 baseline still scores 31 or better of 32; the guard cases it runs are unchanged except where a refused case now has an accurate reason.

## Alternatives rejected

- **Keep the text scans and add a special case for each defect.**
  Each fix needs its own recogniser for quoting, nesting, and clause order, and the next PostgreSQL form repeats the problem.
  The parser already knows every form, including the ones not thought of.
- **Parse for validation, then deparse and execute the normalized text.**
  Deparsing rewrites the model's statement, so an error message or a baseline result could describe SQL the model did not write, and a deparse round trip can change semantics.
  The tree is used for facts; the original text is what runs.
- **Strip a non-literal bound by rewriting the text.**
  A rewrite must decide precedence for arithmetic, casts, and subqueries, and it hides from the model that the statement it wrote is not bounded.
  A named refusal is honest and actionable.
- **Declare split breakdowns unsupported.**
  Counting a multi-value cell once per value is a documented question, and refusing it would make the guard the limit on what the product can answer rather than the shape of the data.

## Consequences

- `pglast` is a runtime dependency. It ships wheels with `libpg_query` bundled, so neither the image nor a developer machine needs a PostgreSQL build toolchain.
  The bundled grammar can be newer than the server's; syntax that only the newer grammar knows is accepted here and then refused by the database at execution. The server remains the final grammar.
- A refusal names the real cause: a syntax error carries PostgreSQL's own message, an unknown function is named, an identity function is distinguished from a dangerous one, and a bound states what is wrong with it.
  The model can rewrite the statement instead of guessing.
- The allowlist is a reviewed surface. A new function is unavailable until it is added in a change that also adds its case, which is the intended default for a trust boundary.
- A quoted identifier is case-sensitive, as it is in PostgreSQL. `"LO_IMPORT"` is not `lo_import` and is refused, and `"LOWER"` is not `lower`.
- An alias that happens to match a hidden column name is allowed; it is output naming, not a read of that column.
- The consequence "The check is a shape scan, not a SQL parser" in ADR-0064 is superseded by this record; its rule, that an OFFSET page requires a total order, still holds and is now checked on the parse tree.
- The offset-order check and the guard share one parse contract, so a statement cannot pass one and be misread by the other.

## Rollback

Revert the code and remove the `pglast` dependency.
The previous text scans can be restored from git.
No migration, stored state, or external contract is involved.
