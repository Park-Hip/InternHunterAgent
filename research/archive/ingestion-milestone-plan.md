# Ingestion Milestone Plan: Decision Record (archived)

> Archived 2026-08-11. M19 shipped. Outcome owned by
> `docs/MVP_Technical_Design.md`, `docs/Operations.md`, and D-019 through D-024.
> Preserved for the reasoning and rejected alternatives; not implementation guidance.

## Decisions taken

- D-019: Keep-alive is windowed and must be measured against Neon compute use.
- D-020: Production ingestion needs a yield floor, rollback path, and schema assertion.
- D-021: Lifecycle data is hidden until honesty behavior is measured.
- D-024: Ingestion runs externally through GitHub Actions.

## 1. Verdicts on the four inversions

### 1A. The deploy ordering flipped (web API deployed first) - #1/#2 hold, #6 amended

**What survives unchanged - the load semantics.** The section 4.1 hazard table was about a
*silent cron nobody watches*; the live-DB flip raises the stakes of the same hazards, it does not
create different ones for the load path.

- *Partial run:* with accumulate + time-based expiry, a partial run only fails to refresh
  `last_seen_at` on the missed rows. Nothing shrinks, nothing is deleted; only
  `expire_after_days` **consecutive** misses expire a posting. "A partial run is harmless"
  was proven against the offline DB by construction, and the construction is
  deployment-agnostic. **#1 and #2 hold verbatim.**
- *Reader-visible intermediate state:* with the `TRUNCATE` gone, the entire `clean_jobs`
  refresh is **one multi-row `INSERT ... ON CONFLICT DO UPDATE` statement** (the upsert already
  written in `clean_store.py`), which Postgres executes atomically. A visitor querying
  mid-run sees either the old rows or the new rows, never a half-applied batch.

- **Rejected: a staging DB / Neon branch + verify + promote flow.** For a ~50-100-row
  corpus this is a second environment, a promotion mechanism, and extra CU-hours to protect
  against a failure mode the yield floor + raw-rebuild already covers. Over-engineering
  under CLAUDE.md's MVP rule.

**What the flip actually changes - three amendments:**

1. **Sequencing becomes a safety rule, not a preference.** Today's code still runs
   `TRUNCATE clean_jobs` before the upsert, so running the current pipeline against Neon - even
   once, manually, "to test" - rebuilds the live table from the in-memory batch.
   **Rule: no ingestion run against the production DSN until T0019.3 lands.**
2. A transform regression can overwrite good rows in place.
   The two MVP-priced mitigations are a **pre-write yield floor** that aborts a suspiciously
   small run before its `clean_jobs` write and a documented **rollback runbook** that rebuilds
   `clean_jobs` from `raw_jobs`.
3. Writing to a second DB and swapping was examined and closed.
   It either teaches the serving path about two databases or invents a promotion step.
   The point of the accumulating in-place write is to avoid both.

### 1B. The honesty gate on `is_active` was never satisfied - #3 split and re-sequenced

**Recommendation: split the decision along the line it already contains.**

- **Ship now:** the lifecycle *mechanics* - `is_active`, `first_seen_at`, `last_seen_at`
  columns, the upsert touching them, and the time-based expiry pass. This is deterministic
  data-layer work with **zero dependency on model behavior**.
- **Defer:** the agent *exposure* - adding `is_active` to `schema_context` and the always-on
  hedge - as its own future ticket, gated on: **(1)** T0011.5 v1 baseline run, **(2)** the
  prompt-v2 few-shot pass, and **(3)** the targeted recalibration delta.

**Why this and not the other three options:**

- Ship the hedge anyway as a nudge? The gate is unmet and the adverse evidence means the likely
  outcome is a hedge that silently does not fire.
- Ship with deterministic enforcement? A hide-inactive view erases the corpus for aggregates,
  while injecting a condition or post-processing answers crosses the tool boundary.
- Do not ship `is_active` at all? That throws away deterministic lifecycle data that gets more
  expensive to reconstruct as accumulation continues.

Until exposure lands, the agent serves the accumulated corpus with expired postings present and
unqualified.
Nightly refresh still improves data honesty before the hedge exists.

### 1C. Neon changes the cost math - decisions hold, one verification becomes load-bearing

So the cron itself is a rounding error and the `/health`-not-`/ready` rule from section 1a
already protects the direct path.
The entire risk concentrates in the open question of whether the LangGraph checkpointer's idle
psycopg pool connections alone prevent Neon's 5-minute suspend.
If they do, the windowed keep-alive - designed to protect Render's 750 instance-hours -
**breaks Neon's free tier instead**, regardless of endpoint.

**Consequence for the milestone:** the keep-alive ticket (T0019.7) is structured as
*enable -> verify -> decide*, not fire-and-forget.

The decision order is to shed idle connections, then shrink the ping window, then use Render
Starter and drop the ping if idle connections keep Neon awake.
The choice cannot be resolved from a desk; it needs a measured compute-hours watch.

### 1D. Two hard gates - both re-sequenced as blockers, one gains a second mechanism

Alembic fixes the *forward path*, but Alembic does not *detect* a database that drifted
**out-of-band**.
Since this milestone is the first thing that will **write** to the live table on a schedule,
it gets both mechanisms: Alembic and a pre-flight contract assertion in the ingestion CLI.

**D2 - robots.txt / ToS for `ms.vietnamworks.com` (section 11).** Still unverified; section 4.1
row 5 declared it a hard gate before the first scheduled run.

- It hard-blocks **T0019.6 (the scheduler) only**.
  The code tickets proceed regardless because they are tested against canned responses and a
  local database, requiring no VietnamWorks fetch.
- If automated access is forbidden, the cron does not ship.
  The milestone degrades to a lifecycle-ready pipeline and operations hardening, while the
  source question re-opens as research work.

## 3. Ticket breakdown (proposed T0019.1-T0019.8)

> **Graduated 2026-07-16.** Section 3's original breakdown is now **T0019 (Milestone 19)** in
> `docs/Tickets.md` - that file is the source of truth for scope and sequencing from here.

The dependency spine was the legal gate, Alembic baseline, accumulation semantics, safety
assertions, and the nightly scheduler.
Source resilience, the keep-alive verification, and the truthful readiness date were independent
work that could be scheduled around that spine.

The recommended sequence also made the legal review a hard gate only for unattended scheduling.
It did not block local, canned-response, or migration work that did not access the job board.
This avoids treating a source-policy decision as a reason to defer unrelated data-safety work.

The planned nightly cron runs at `0 2 * * *` UTC.
The windowed keep-alive has a different role from ingestion and cannot safely be substituted by
that daily schedule.
The readiness date is derived from ingestion state rather than a static demo snapshot setting.

## 4. Trade-offs made visible (named rejections, one line each)

| Rejected option | Why |
|---|---|
| Ship the `is_active` hedge as a nudge now | Its own ship-gate (T0011.5) is unmet and the measured nudge-adherence base rate is adverse (2/2, 1/3 failures) (section 1B). |
| Deterministic hedge enforcement (view / SQL injection / post-processing) | View ruled out by section 4.2 #3 itself; injection crosses the tool boundary the repo already defended on the id-first nudge (section 1B). |
| Write ingestion to a separate DB and swap | Either two DBs leak into the serving path or a promotion step is reinvented; #1/#2 exist to make in-place writes safe (section 1A). |
| Alembic alone as the schema-drift answer | Migrations don't detect out-of-band drift - the 2026-07-15 incident class; the pre-flight assertion is the missing detection half (section 1D). |
| Render Cron for ingestion | $1/mo floor, not free (section 4). |
| Single-transaction `raw_jobs`+`clean_jobs` write, content-hash delta, orchestrator, rebuild-from-raw | Deferrals; no inversion moved them, and the clean write is already statement-atomic (section 1A). |

The milestone preserves a small operational surface: a pre-flight schema assertion, a pre-write
yield floor, a structured run summary, and a dead-man's switch.
It does not add staging infrastructure, source orchestration, or a second serving path.

The accumulating upsert leaves `first_seen_at` untouched on existing rows, refreshes
`last_seen_at`, and restores `is_active` when an expired posting is seen again.
Expiry is time-based only and never deletes a record.

## 5. Assumptions I could not verify (need live verification; not asserted)

1. **`ms.vietnamworks.com/robots.txt` content and the ToS position** - the entire point of
   T0019.1; nothing here presumes the answer.
2. **Whether the checkpointer's idle pool connections hold Neon awake** - the section 1a/1C open
   question; T0019.7 is structured around measuring it.
3. **The VietnamWorks API's current shape and yield** - the 5/5-reliable, ~50-112-posting
   numbers are from the 06/2026 spike; an undocumented API can have changed since.
4. **Quota and limit values as of today** - Neon, Render, GitHub Actions, and healthchecks.io
   values are dated findings, not re-checked live facts.
5. **Backfill data availability** - `first_seen_at` backfill assumes existing `clean_jobs` rows
   have matching `raw_jobs.fetched_at` values.
6. **GitHub Actions schedule drift magnitude** - daily cadence tolerates drift, but a keep-alive
   ping needs a separate scheduler and measurement.

## Sources

- `research/archive/deployment-research-plan.md` sections 1a, 3, 4, 9, 10, and 11.
- `research/experiments/vietnamworks_tos_excerpt_2026-07-16.md`.

## Live-checked facts

- The repository was public when scheduled GitHub Actions use was assessed.
- The nightly ingestion job is independent of the Render keep-alive window.
- A direct `/health` request avoids a database readiness query.
- The live writer needs a schema assertion because a migration does not detect out-of-band drift.
- The yield floor protects the served corpus before an upsert overwrites good records.

The recovery path is documented before unattended execution is enabled.
It rebuilds the served projection from the durable raw-record store.
