# Ingestion Milestone Plan — Validation of the §4.2 Decisions & Ticket Breakdown

> **Status:** Design validation / pre-ticket record (2026-07-16). This document **validates**
> the seven ingestion-redesign decisions locked on 2026-07-03 in
> [`deployment-research-plan.md`](deployment-research-plan.md) §4.2 against four assumptions
> that have inverted since — it does not re-derive them. It disposes each inversion
> (hold / amend / re-sequence), fixes the milestone shape, and carries the ticket breakdown
> (proposed **T0019**) ready to graduate into `docs/Tickets.md`. No implementation here;
> illustrative fragments only.
>
> **Graduated 2026-07-16.** §3's breakdown is now **T0019 (Milestone 19, T0019.1–.8)** in
> [`docs/Tickets.md`](../docs/Tickets.md) — that file is the source of truth for scope and
> sequencing from here. This document stays as the *rationale* record: why each §4.2 decision
> held or was amended (§1), the named rejections (§4), and the unverified assumptions the
> tickets are designed to measure (§5). Read §1 before scoping a sub-ticket; do not re-derive it.
>
> **Read first:** `deployment-research-plan.md` §4/§4.1/§4.2 (the locked decisions),
> §1a/§3/§9/§10/§11/§12; `docs/Known_Issues.md` § Config/startup/deployment and
> § Agent runtime & prompts; `docs/Schema_Contract.md`.

---

## 0. TL;DR

- **The core §4.2 design survives contact — and is strengthened by it.** Accumulate-never-wipe
  (#1) and time-based `is_active` expiry (#2) were chosen because they make a partial or failed
  run harmless. That property is exactly what makes writing to a **live production database**
  tolerable, so the deploy-ordering flip (inversion A) amends the milestone's *scope and
  sequencing*, not its load semantics.
- **One hard re-sequencing rule falls out of A:** the `TRUNCATE` removal (T0019.3) must land
  before *any* ingestion run — manual or scheduled — touches Neon. The current
  `clean_store.replace_clean_jobs` run against prod would wipe and rebuild the live table from
  whatever came through.
- **The honesty decision (#3) is split, not shipped whole** (inversion B). The lifecycle
  *mechanics* (`is_active`, `first_seen_at`, `last_seen_at`, the expiry pass) ship now as
  **hidden DDL columns** — deterministic data-layer work with no honesty dependency. The
  *agent exposure* (adding `is_active` to `schema_context` + the hedge nudge) is **deferred
  behind its own unmet gate**: T0011.5 baseline → prompt-v2 few-shot pass → targeted
  recalibration delta. The 16-column frozen contract is untouched this milestone — no prompt,
  golden, or eval changes at all.
- **The Neon cost math (inversion C) holds for the cron but adds one load-bearing
  verification:** if the checkpointer's idle pool connections hold Neon awake, the windowed
  keep-alive ping (~487 Render-hours/month) would drag Neon to ~122 CU-h — **over its
  100 CU-h/month cap**. The keep-alive ticket's first step is the §1a 24-hour CU watch, with a
  written decision rule for the failure case.
- **Both hard gates (inversion D) are sequenced as blockers:** robots.txt/ToS (T0019.1,
  do-first, hard-blocks the scheduler ticket only) and schema drift (Alembic **plus** a cheap
  ingestion pre-flight contract assertion — Alembic alone does not detect out-of-band drift,
  which is exactly what bit on 2026-07-15).
- **GitHub Actions at $0 is confirmed:** the repo is **public** (verified via
  `gh repo view` → `"visibility": "PUBLIC"`, 2026-07-16). The 60-day auto-disable still
  applies; the cron ticket includes the keepalive action.

---

## 1. Verdicts on the four inversions

### 1A. The deploy ordering flipped (web API deployed first) — #1/#2 **hold**, #6 **amended**

§4.2 #6 said "this milestone is ingestion-only; the web-API deploy is a separate later
milestone." T0018.4 (2026-07-16) inverted that: ingestion now writes to the live Neon database
behind https://internhunteragent.onrender.com. Re-examining the §4.1/§4.2 safety analysis under
the live-DB assumption:

**What survives unchanged — the load semantics.** The §4.1 hazard table was about a *silent
cron nobody watches*; the live-DB flip raises the stakes of the same hazards, it does not
create different ones for the load path:

- *Partial run:* with accumulate + time-based expiry, a partial run only fails to refresh
  `last_seen_at` on the missed rows. Nothing shrinks, nothing is deleted; only
  `expire_after_days` **consecutive** misses expire a posting. "A partial run is harmless"
  was proven against the offline DB by construction, and the construction is
  deployment-agnostic. **#1 and #2 hold verbatim.**
- *Reader-visible intermediate state:* with the `TRUNCATE` gone, the entire `clean_jobs`
  refresh is **one multi-row `INSERT … ON CONFLICT DO UPDATE` statement** (the upsert already
  written in `clean_store.py`), which Postgres executes atomically. A visitor querying
  mid-run sees either the old rows or the new rows, never a half-applied batch. This is a
  point the offline-era analysis never needed to make; it comes for free. (The §4.2 #7
  deferral of a single `raw_jobs`+`clean_jobs` transaction stays deferred — a rare desync
  between the two tables heals on the next idempotent nightly run and is invisible to the
  agent, which reads only `clean_jobs`.)

**What the flip actually changes — three amendments:**

1. **Sequencing becomes a safety rule, not a preference.** Today's code still runs
   `TRUNCATE clean_jobs` before the upsert (`clean_store.py`), so running the *current*
   pipeline against Neon — even once, manually, "to test" — rebuilds the live table from the
   in-memory batch and re-opens the §4.1 row-2 shrink hazard against real visitors.
   **Rule: no ingestion run against the production DSN until T0019.3 lands.** (Local Docker
   Postgres runs stay fine.)
2. **A hazard §4.2 never contemplated: upserting garbage over good rows.** Offline, a
   transform regression is caught before deploy; live, it *overwrites* good rows in place
   (upsert refreshes every fetched row). Two MVP-priced mitigations, both inside what §4.1/§9
   already sanction ("sharp-drop yield assertions" + dead-man's switch):
   - a **pre-write yield floor** — abort the run *before* the `clean_jobs` write if the fetch
     yield is suspiciously small (config `ingestion.safety.min_yield`); the same run withholds
     the dead-man ping so an alert fires. This moves the sanctioned yield assertion from
     "after, alert" to "before, abort" — strictly cheaper than discovering it in prod.
   - a documented **rollback runbook: rebuild `clean_jobs` from `raw_jobs`** via
     `to_normalized_job` + the upsert — the exact recovery already performed live on
     2026-07-15 during the schema-drift fix. Accumulating `raw_jobs` (#1, #4) is what makes
     this possible; it is the milestone's rollback path.
   - **Rejected: a staging DB / Neon branch + verify + promote flow.** For a ~50–100-row
     corpus this is a second environment, a promotion mechanism, and extra CU-hours to protect
     against a failure mode the yield floor + raw-rebuild already covers. Over-engineering
     under CLAUDE.md's MVP rule. *(Should the corpus or the blast radius ever grow 10×, a Neon
     branch is the natural first upgrade — noted, not built.)*
3. **"Ingestion should write somewhere else entirely?" — No.** The question was examined and
   closed: writing to a second DB and swapping means either the serving path learns about two
   databases (layer-isolation damage) or a promotion step is invented (amendment 2's rejected
   option). The whole point of #1/#2 was to make in-place writes safe; use it.

**#6's other half also inverts constructively:** the milestone is no longer "ingestion-only."
It inherits the three ops items every doc already re-pointed here: the **windowed keep-alive
ping** (§1a, decided 2026-07-16, not applied), the **healthchecks.io dead-man's switch +
UptimeRobot ping** (§9A deferral), and the **schema-drift assertion/migration**
(`Known_Issues.md` HIGH, re-pointed from T0018.4). The scheduler reconciliation against
Full_Design §2 (external/out-of-band, not in-request) is unaffected by the flip and lands with
the cron ticket as §4.1 already prescribed.

**Verdict: #1, #2 hold; #5 holds; #6 amended as above; #7 deferrals all stay.**

### 1B. The honesty gate on `is_active` was never satisfied — #3 **split and re-sequenced**

§4.2 #3 ships the hedge as a prompt nudge *"which is exactly why the Evaluation milestone
(T0011) must confirm the model honors it before this ships."* That confirmation never
happened: T0011.5 is **blocked** on maintainer credentials, and the evidence that exists is
adverse — the hidden-salary honesty rule is violated **2/2** with the exact prohibited
phrasing, and freshness fabricates **1/3** (`Known_Issues.md` § Agent runtime & prompts).
The base rate for "the model honors an honesty nudge" is measurably poor.

**Recommendation: split the decision along the line it already contains.**

- **Ship now:** the lifecycle *mechanics* — `is_active`, `first_seen_at`, `last_seen_at`
  columns, the upsert touching them, and the time-based expiry pass. This is deterministic
  data-layer work with **zero dependency on model behavior**. The columns ship as **hidden
  DDL columns**, exactly the established pattern `Schema_Contract.md` § Hidden DDL Columns
  already documents for `source`, `external_id`, and `posted_date`: present in the table,
  absent from every prompt surface, enforced by the existing prompt-freeze guard tests.
- **Defer:** the agent *exposure* — adding `is_active` to `schema_context` and the always-on
  hedge — as its own future ticket, gated on: **(1)** T0011.5 v1 baseline run, **(2)** the
  prompt-v2 few-shot pass that the repo's own doctrine names as the sanctioned fix path for
  behavior items (`pre-deploy-refinement-plan.md` §3/§7 Phase 3), and **(3)** the targeted
  recalibration delta (a handful of `is_active`/staleness goldens) that `Schema_Contract.md`
  and `pre-deploy-refinement-plan.md` §1c already pre-planned.

**Why this and not the other three options:**

- *Ship the hedge anyway (nudge)?* The gate §4.2 itself set is unmet, and the adverse evidence
  means the likely outcome is a hedge that silently doesn't fire — worse than no hedge,
  because the design doc would claim an honesty property the product doesn't have.
- *Ship with deterministic enforcement?* Deterministic *what*, concretely, is the problem:
  a hide-inactive view is **explicitly ruled out by #3** (erases the corpus for aggregates);
  injecting `WHERE is_active` or post-processing answers crosses the tool boundary the repo
  has already defended once — the id-first nudge was deliberately **not** "fixed" by
  force-injecting `id` into model SQL (`Known_Issues.md` T0009.11), and this would be the
  same violation with more surface.
- *Don't ship `is_active` at all?* Throws away the deterministic half for a gate that only
  binds the behavioral half, and forfeits the lifecycle data (`first_seen_at` backfill,
  expiry state) that gets *more* expensive to reconstruct the longer accumulation runs
  without it.

**Reconciliation with the "no prompt-tinkering" doctrine (2026-07-02 note):** this
recommendation makes **zero prompt changes** in this milestone. The hedge arrives only through
the measured path the doctrine prescribes: baseline → designed prompt-v2 (few-shot, the
documented lever for exactly these failures) → re-measure. No contradiction to justify.

**Interim honesty posture, stated plainly:** until exposure lands, the agent serves the
accumulated corpus with expired postings present and **unqualified** — the same epistemic
state as today's demo, which serves a 100%-stale snapshot behind the UI disclaimer. Nightly
refresh strictly *improves* data honesty even before the hedge exists. One thing does become
false under refresh, though: the static `api.demo.data_snapshot_date` the disclaimer renders.
That gets a small deterministic fix (T0019.8): derive the disclaimer date from ingestion state
(`MAX(last_seen_at)` on `clean_jobs`, fallback to the config value). This is UI/`/ready`-level,
never agent-visible, so it does not repeat the `posted_date` fabrication trap — the model
still cannot be asked about freshness it cannot see.

**Verdict: #3 amended — mechanics now (hidden), exposure re-sequenced behind T0011.5 +
prompt-v2 + recalibration delta. The 16-column freeze is untouched this milestone.**

### 1C. Neon changes the cost math — decisions **hold**, one verification becomes load-bearing

Worked numbers (all inputs from §1a/§3/§10 and `Known_Issues.md`; CU rate 0.25):

| Consumer | Compute demand | CU-hours/month | Against the 100 CU-h cap |
|---|---|---|---|
| Nightly cron (T0019.6) | wakes Neon ~5–10 min/day for the write | **≲ 1.3** | negligible |
| Demo traffic (status quo) | seconds/day of tiny queries | ≪ 1 | negligible |
| Keep-alive ping → `/health` (no DB) | none *directly* | 0 | fine **if** Neon suspends while Render idles |
| **Keep-alive if idle pool connections hold Neon awake** | Neon awake whenever Render is awake: 16 h/day window ≈ 487 h × 0.25 CU | **≈ 122** | **over cap** |

So the cron itself is a rounding error and the `/health`-not-`/ready` rule from §1a already
protects the direct path. The entire risk concentrates in the **open question `Known_Issues.md`
and §1a both flag**: whether the LangGraph checkpointer's idle psycopg pool connections alone
prevent Neon's 5-minute suspend. If they do, the windowed keep-alive — designed to protect
Render's 750 instance-hours — **breaks Neon's free tier instead**, regardless of endpoint.

**Consequence for the milestone:** the keep-alive ticket (T0019.7) is structured as
*enable → verify → decide*, not fire-and-forget. Step 1 enables the windowed ping; step 2 is
the §1a verification (watch Neon's compute-hours for ~24 h); step 3 applies a pre-written
decision rule if the pool holds Neon awake — in preference order: **(a)** configure the
checkpointer pool to shed idle connections (psycopg pool `min_size=0` / idle-lifetime — a
config-level change; Neon resumes in ~300–500 ms, acceptable per §3), **(b)** shrink the ping
window, **(c)** escape hatch Render Starter $7/mo (< the $10 ceiling) and drop the ping. This
cannot be resolved from a desk — it is in "assumptions I could not verify" (§5).

**Interaction check, cron × window:** `0 2 * * *` UTC = 09:00 ICT falls *inside* the
07:00–23:00 ICT ping window, so the cron adds no marginal Render wake-time; and the cron
reaches Neon directly (GitHub runner → Neon DSN), not through Render, so it costs zero Render
instance-hours either way.

**GitHub Actions cost basis — verified, not assumed:** the repo is **public**
(`gh repo view --json visibility` → `PUBLIC`, checked 2026-07-16), so scheduled minutes are
$0/unlimited. The 60-day auto-disable applies regardless of visibility; the cron ticket
includes the keepalive-workflow action per §4's findings. (Had it been private: 2,000 free
min/month ≫ ~300 used — the conclusion would not change.)

**Verdict: no §4.2 decision changes; T0019.7 gains the verification step and decision rule.**

### 1D. Two hard gates — both **re-sequenced as blockers**, one gains a second mechanism

**D1 — Schema drift (`Known_Issues.md` HIGH · OPEN).** Does Alembic (#4) subsume it? **Only
half of it.** Alembic fixes the *forward path*: schema changes become migrations, and the
lifecycle columns land via `alembic upgrade head` instead of a `CREATE TABLE IF NOT EXISTS`
that silently no-ops. But Alembic does not *detect* a database that drifted **out-of-band** —
and the 2026-07-15 outage was exactly that (a pre-T0013 DB nobody migrated). T0018.4 loaded
Neon from an already-reconciled dump, which sidestepped drift without adding any assertion.
Since this milestone is the first thing that will **write** to the live table on a schedule,
it gets both mechanisms:

- **Alembic** (T0019.2): baseline the current schema, then migrate the lifecycle columns
  (T0019.3). `reset_db.sql` demoted to local-dev-only, as #4 already decided.
- **A pre-flight contract assertion in the ingestion CLI** (T0019.5): one
  `information_schema.columns` query comparing the live `clean_jobs` columns against the
  expected set (16 frozen + hidden bookkeeping + lifecycle), **failing loudly before any
  write**. This directly protects the unattended nightly writer — the exact spot where the
  2026-07-15 class of bug would otherwise strike silently at 02:00 UTC.
- An API-side startup assertion (protecting the *read* path) is noted as a follow-up for the
  register, not built here — the serving path has run against this schema since T0013 and is
  not what this milestone changes.

**D2 — robots.txt / ToS for `ms.vietnamworks.com` (§11).** Still unverified; §4.1 row 5
declared it a hard gate before the first scheduled run, and §11's 2026-07-16 decision
explicitly re-enters it here. Sequenced as **T0019.1, do-first, doc-only**:

- Fetch `https://ms.vietnamworks.com/robots.txt`; check the `/job-search/` path; archive the
  fetched copy under `research/experiments/`. Review the VietnamWorks ToS for
  automated-access clauses. Record the outcome in §11 with date.
- **Gating scope:** it hard-blocks **T0019.6 (the scheduler) only**. The code tickets
  (.2–.5) proceed regardless — they are refactors tested against canned `httpx` responses and
  a local DB, requiring no fetch from VietnamWorks.
- **If the answer comes back unfavorable** (robots disallows the path, or ToS explicitly
  prohibits automated access): the cron does not ship. The milestone degrades to
  "lifecycle-ready pipeline + ops hardening" — T0019.2/.3/.5/.7/.8 still land (they are
  independently valuable: migrations, drift assertion, keep-alive, truthful disclaimer), the
  demo stays on the manually-loaded corpus, and the source question re-opens as a new research
  item (the recorded fallback direction is the ITviec cloudscraper experiment from
  `job-site-comparison.md` — **not** pursued in this milestone; multi-source stays deferred
  per #7). A daily unattended job against a forbidding host is a standing violation and is
  not shipped "quietly."

**Verdict: #4 holds and is joined by a pre-flight assertion; the §11 gate holds and is
sequenced first.**

---

## 2. Recommended milestone shape

**Ships (proposed milestone T0019 — Ingestion Deploy Readiness, live-DB):**

1. The §11 robots/ToS gate resolution (do-first).
2. Alembic baseline + lifecycle-columns migration (`is_active`, `first_seen_at`,
   `last_seen_at` — **hidden**, prompt surfaces untouched).
3. Accumulate load semantics: `TRUNCATE` dropped, the already-written upsert live, time-based
   expiry pass, `expire_after_days` in `config/settings.yaml`.
4. Source resilience: per-page try/continue + retry/backoff (§4.2 #5, unchanged).
5. Unattended-run safety: pre-flight schema assertion, pre-write yield floor, structured run
   summary, healthchecks.io dead-man ping.
6. The GitHub Actions nightly cron (`0 2 * * *` UTC), gated on 1 + 2–5.
7. The windowed keep-alive ping + the Neon idle-pool verification (ops/config).
8. A truthful, ingestion-derived disclaimer date on `/ready`.

**Explicitly does not ship, and why the cut falls there:**

- **`is_active` agent exposure + honesty hedge** — gate unmet, evidence adverse; deferred
  behind T0011.5 → prompt-v2 → recalibration delta (§1B). This is the single biggest scope
  cut and it removes *all* prompt/golden/eval work from the milestone.
- **Everything in §4.2 #7, unchanged:** rebuild-clean-from-`raw_jobs` phase split, source
  orchestrator/registry (multi-source), `content_hash` delta, single-transaction
  `raw_jobs`+`clean_jobs` write. No inversion moved any of them; the live-DB flip arguably
  *strengthens* the single-transaction deferral (the clean write is statement-atomic on its
  own, §1A).
- **Staging DB / Neon branch promotion** — rejected in §1A.
- **CI merge gate and `main` reconciliation** — adjacent, separately tracked
  (`pre-deploy-refinement-plan.md` §6i; `Repo_Current_State.md`).
- **Observability beyond the dead-man's switch + yield assertions** — §9/§4.1's sanctioned
  set is the ceiling; no UptimeRobot-style uptime alerting is added beyond what T0019.7's
  external scheduler needs to exist anyway.

**Config additions this milestone (all in `config/settings.yaml` per CLAUDE.md; illustrative):**

```yaml
ingestion:
  lifecycle:
    expire_after_days: 7      # consecutive missed days before is_active=false; never deleted
  safety:
    min_yield: 20             # abort the run (and withhold the dead-man ping) below this fetch count
```

*(Rationale for the defaults: at daily cadence, 7 consecutive misses is a full week of the
posting being absent from search — comfortably beyond any transient keyword/page flakiness the
retry logic smooths; `min_yield: 20` sits far below the measured ~50-per-run steady state but
far above a broken run's near-zero. Both are config, not code, and tunable without a ticket.)*

**Illustrative DDL delta (lands as an Alembic migration, not raw SQL):**

```sql
ALTER TABLE clean_jobs
  ADD COLUMN is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
  ADD COLUMN first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now();
-- backfill for pre-existing snapshot rows: truthful values from raw_jobs.fetched_at
```

---

## 3. Ticket breakdown (proposed T0019.1–T0019.8)

> Format matches `docs/Tickets.md` house style. Sequencing: **.1 first**; .2 → .3 → .5 → .6 is
> the dependency spine; .4, .7, .8 float. Blocked-on markers are explicit per ticket.

### T0019.1: robots.txt / ToS verification for `ms.vietnamworks.com` — **do first; gates T0019.6**
**Objective:** Resolve the §11 hard gate before any scheduled run exists: verify whether the
undocumented `ms.vietnamworks.com/job-search` API host permits automated access
(`deployment-research-plan.md` §11; `data-ingestion-stage.md` §0.1/§4). Doc-only; no code.
**In Scope:**
* Fetch `https://ms.vietnamworks.com/robots.txt` (and `www.vietnamworks.com/robots.txt` for
  context); determine whether the `/job-search/` path is disallowed; archive the fetched
  files under `research/experiments/` with the fetch date.
* Read the VietnamWorks Terms of Service for clauses on automated access / scraping / API use;
  quote the relevant clauses (or their absence) in the decision record.
* Record a dated **Decision** in `deployment-research-plan.md` §11: *favorable* (schedule
  permitted, note any crawl-delay to honor) or *unfavorable* (T0019.6 parked; milestone
  degrades per `research/ingestion-milestone-plan.md` §1D; source fallback re-opens as a new
  research item).
* Manual check: robots.txt copy exists in `research/experiments/`; §11 carries the dated
  decision and quotes; T0019.6's blocked-on status is updated to match.
**Out of Scope:**
* Any code change; any alternative-source spike (ITviec/cloudscraper stays a recorded
  fallback direction only); re-litigating the §11 legal-posture research.

### T0019.2: Alembic adoption — baseline migration + env wiring
**Objective:** Adopt Alembic per §4.2 #4: an accumulating `raw_jobs` holds postings that have
dropped out of search and are no longer re-fetchable, so the deployed data is irreplaceable
and `reset_db.sql` stops being a migration strategy.
**In Scope:**
* Add `alembic` as a dependency (sanctioned by §4.2 #4); `alembic init` with `env.py` reading
  `DATABASE_URL` (SQLAlchemy `postgresql+psycopg://` form, **direct non-pooled endpoint** for
  migrations per §3's decision) and targeting the existing `models.py` metadata.
* Baseline migration capturing the current deployed schema (the frozen 16-column contract +
  hidden columns + `raw_jobs`), stamped against both the local Docker DB and Neon so
  `alembic upgrade head` is a no-op on a current DB.
* Demote `scripts/reset_db.sql` to local-dev-only: a header comment + a note in
  `Repo_Current_State.md` § Available scripts ("destructive, local dev only — prod schema
  changes go through Alembic").
* Tests: migration round-trip against a scratch local DB (upgrade from empty → schema matches
  `models.py` metadata).
* Manual check: `uv run alembic upgrade head` against the local Docker DB is a clean no-op on
  an already-initialised DB and builds the full schema on an empty one; `alembic current`
  shows the baseline revision; the app boots and answers a query against the migrated DB.
**Out of Scope:**
* The lifecycle columns themselves (T0019.3); running anything against Neon before the
  maintainer applies it deliberately; autogenerate-driven workflows beyond the baseline
  (hand-written migrations are fine at this scale).

### T0019.3: Accumulate load semantics + hidden lifecycle columns — **blocked on T0019.2**
**Objective:** Land §4.2 #1/#2: drop the `TRUNCATE` so the already-written
`ON CONFLICT (source, external_id) DO UPDATE` upsert becomes live code, and add the
time-based `is_active` soft-expiry — as **hidden** columns (no prompt surface changes; §1B).
**In Scope:**
* Alembic migration adding `is_active BOOLEAN NOT NULL DEFAULT TRUE`,
  `first_seen_at TIMESTAMPTZ NOT NULL`, `last_seen_at TIMESTAMPTZ NOT NULL` to `clean_jobs`
  (+ the ORM fields in `models.py`); **backfill** existing rows' `first_seen_at`/
  `last_seen_at` from their `raw_jobs.fetched_at` (truthful, available for all 50 snapshot rows).
* `clean_store.py`: remove the `TRUNCATE`; upsert sets `last_seen_at = now()` and
  `is_active = true` on conflict, leaves `first_seen_at` untouched (insert-only value).
  Rename `replace_clean_jobs` → `upsert_clean_jobs` (the old name states the retired semantics).
* Expiry pass in the loader after the upsert:
  `UPDATE clean_jobs SET is_active = false WHERE last_seen_at < now() - make_interval(days => :expire_after_days)`
  — time-based only, **never** "not seen this run", never `DELETE`. `expire_after_days` read
  from `config/settings.yaml` (`ingestion.lifecycle.expire_after_days`, default 7).
* Guard tests: prompt surfaces (`schema_context`, `system_prompt`, `sql_generation`) do **not**
  mention `is_active`/`first_seen_at`/`last_seen_at` (extend the existing
  `tests/agents/runtime/test_prompts.py` hidden-column enforcement); upsert refreshes
  `last_seen_at` and preserves `first_seen_at`; a row older than the window flips to
  `is_active = false` and is never deleted; a re-seen expired row flips back to active.
* Manual check (local DB): run ingestion twice — row count never shrinks between runs;
  `SELECT COUNT(*) FROM clean_jobs WHERE is_active = false` is 0 after a fresh double-run;
  manually age one row's `last_seen_at` by 8 days, re-run, confirm it expires and its data
  still selects; confirm the agent's answers are unchanged (columns invisible).
**Out of Scope:**
* Agent exposure of `is_active` / the hedge (deferred behind T0011.5 + prompt-v2 +
  recalibration — §1B); exposing `first_seen_at`/`last_seen_at` in any form (the
  `posted_date` fabrication trap); rebuild-from-`raw_jobs` phase split, `content_hash` delta,
  single-transaction write (§4.2 #7); any `Schema_Contract.md` change (the frozen surface is
  untouched).

### T0019.4: Source resilience — per-page try/continue + retry/backoff
**Objective:** Land §4.2 #5: one transient 429/5xx currently aborts the whole run via
`_post`'s `raise_for_status()` (§4.1 row 1). With time-based expiry this is *completeness*,
not correctness — salvage the good pages.
**In Scope:**
* In `VietnamWorksSource._collect`: wrap each page `_post` in try/except; retry with backoff
  (attempts + base delay from config, e.g. `ingestion.api.retry_attempts: 2`,
  `retry_backoff_seconds: 2.0`), then skip-and-log (`structlog` warning with query/page) and
  continue to the next page/query.
* Run summary gains `pages_failed` (feeds T0019.5's assertions).
* Tests with a canned `httpx.Client`: a mid-run 500 skips that page and keeps later pages'
  postings; exhausted retries don't raise out of `fetch()`; the politeness delay still applies
  between attempts.
* Manual check (local, no live fetch needed): inject a failing page via the test client
  pattern and confirm the run completes with the remaining postings loaded and a
  `pages_failed` count in the summary log line.
**Out of Scope:**
* Per-source isolation / orchestrator (multi-source, deferred §4.2 #7); changing keywords,
  pagination, or the politeness delay; any live scraping (T0019.1 gates production fetches;
  local tests use canned responses).

### T0019.5: Unattended-run safety — pre-flight assertion, yield floor, dead-man ping — **blocked on T0019.3 (+ .4 for `pages_failed`)**
**Objective:** Make the pipeline safe to run with nobody watching a live DB: fail loudly
*before* writing when the world looks wrong, and alert when a run is missed or suspicious
(§4.1, §9C; `Known_Issues.md` schema-drift HIGH).
**In Scope:**
* **Pre-flight schema assertion** at CLI start: query `information_schema.columns` for
  `clean_jobs` and compare against the expected column set (frozen 16 + hidden bookkeeping +
  lifecycle); on mismatch, log the diff and **exit non-zero before any write** — the
  detection half of the drift gate (Alembic is the correction half, §1D).
* **Pre-write yield floor:** if fetched count < `ingestion.safety.min_yield` (config,
  default 20), abort before the `clean_jobs` write (raw landing of what *was* fetched is
  harmless and may proceed), exit non-zero.
* **Dead-man ping:** at successful end (all assertions passed), `curl`-equivalent POST to a
  healthchecks.io check URL read from env (`HEALTHCHECKS_URL`; absent → skipped with a log
  line, so local runs don't need it). A failed/aborted run *withholds* the ping → the
  healthchecks.io `period=24h, grace=2h` window alerts (§9C).
* **Structured run summary** as the final log line: fetched / raw_upserted / clean_upserted /
  expired_count / pages_failed / skipped — the §9C health-check numbers in one greppable line.
* Tests: assertion failure exits non-zero before any write (mock session asserts no execute);
  under-floor yield skips the clean write; ping fires only on the all-green path.
* Manual check (local): run against a correct DB → green + summary line; rename a column in a
  scratch DB → run exits non-zero naming the diff, table untouched; set `min_yield` above the
  fixture yield → clean write skipped, non-zero exit.
**Out of Scope:**
* API-side startup assertion (read-path; follow-up register item); UptimeRobot uptime
  monitoring (T0019.7 owns external-scheduler machinery; §9's ceiling holds); alerting
  channels beyond healthchecks.io's built-in email.

### T0019.6: GitHub Actions nightly ingestion cron — **hard-blocked on T0019.1 (favorable) + T0019.2–.5**
**Objective:** Land §4.2 #6/§4.1's decision: the external, out-of-band scheduler invoking the
offline ingestion CLI against Neon — reconciled against Full_Design §2 by amending the
exclusion to in-request background execution (the documented §4.1 reconciliation), not
deleting it.
**In Scope:**
* Workflow: `on: schedule: cron: '0 2 * * *'` (02:00 UTC = 09:00 ICT) + `workflow_dispatch`
  for manual runs; checkout + `uv sync --frozen`; run the ingestion CLI
  (`uv run python -m src.services.ingestion.loader`); a `concurrency` group so overlapping
  runs never double-write; job timeout well under the expected <10-min runtime.
* Secrets (GitHub Actions secrets, per §5): `DATABASE_URL` (Neon **direct** DSN) and
  `HEALTHCHECKS_URL`. No `GROQ_API_KEY` — ingestion is deterministic, no LLM (a live-tested
  §8 decision that stays).
* Keepalive action (marketplace `keepalive-workflow`) against the 60-day scheduled-workflow
  auto-disable (§4 findings; applies despite the repo being public).
* The Full_Design §2 amendment: scope the "no schedulers" exclusion explicitly to
  *in-request* background execution and permit the out-of-band scheduled ingestion trigger,
  cross-referencing §3's ingestion-layer law (serving path never imports ingestion — which
  this preserves: the cron runs on GitHub's runner, not in the API process).
* Manual check: trigger `workflow_dispatch` once, watch the Actions log show the run summary
  line; confirm healthchecks.io received the ping; `SELECT COUNT(*)` on Neon grew or held
  (never shrank); the live demo still answers; next morning, confirm the scheduled run fired
  (Actions history) — noting GitHub's documented schedule drift under load is tolerable at
  daily cadence.
**Out of Scope:**
* Any CI/pytest merge gate (separate backlog item §6i — this workflow is ingestion-only);
  Render Cron (not free, §4); running the workflow before T0019.1's favorable answer is
  recorded — **if §11 comes back unfavorable this ticket is parked, not adapted**.

### T0019.7: Windowed keep-alive ping + Neon idle-pool verification — ops/config; independent
**Objective:** Apply the §1a decision (2026-07-16, decided-not-applied): external scheduler
pinging `GET /api/v1/health` every 10–14 min on a ~07:00–23:00 ICT window — and resolve the
open question that decides whether the whole scheme is free-tier-viable (§1C).
**In Scope:**
* Configure cron-job.org (or UptimeRobot) per §1a: `GET /api/v1/health`, 10–14-min interval,
  07:00–23:00 ICT window. **Never `/ready`** (it runs `SELECT 1` → holds Neon awake).
* **Verification (the load-bearing step):** watch Neon's compute-hours for ~24 h after
  enabling. Determine whether the checkpointer's idle pool connections alone keep Neon from
  suspending while Render is awake.
* **Pre-written decision rule** if they do (≈122 CU-h/month > 100 cap, §1C): (a) first,
  configure the checkpointer's psycopg pool to shed idle connections (`min_size=0` /
  idle-lifetime — settings-level change to `src/core/checkpointer.py` construction, params in
  `config/settings.yaml`), re-verify; (b) else shrink the window; (c) else Render Starter
  $7/mo and drop the ping (inside the $10 ceiling). Record the outcome in
  `deployment-research-plan.md` §1a and close the `Known_Issues.md` open question either way.
* Manual check: during the window, the demo loads without the ~60 s blank-tab cold start;
  after 23:00 ICT + 15 min idle, Render spins down (status quo overnight); Render dashboard
  instance-hours tracking ≈ 16 h/day; Neon dashboard CU-hours consistent with suspension
  between pings (or the decision rule applied and its outcome recorded).
**Out of Scope:**
* 24/7 pinging (the 750-h cliff, `Known_Issues.md` HIGH); pinging `/ready`; GitHub Actions as
  the ping scheduler (drift + 60-day disable, §1a); paid monitoring.

### T0019.8: Truthful refresh date on `/ready` — **blocked on T0019.3**
**Objective:** Keep the UI disclaimer honest once data refreshes nightly: the static
`api.demo.data_snapshot_date` becomes false the first time the cron runs (§1B).
**In Scope:**
* `/api/v1/ready` derives the disclaimer date from data state —
  `SELECT MAX(last_seen_at)::date FROM clean_jobs` — falling back to the existing config value
  when NULL/unavailable. Plain SQL in the existing readiness path; **no ingestion-layer
  import** (layer isolation holds — it reads a table, not the ingestion package).
* Response shape unchanged (same field the UI already reads); UI untouched.
* Tests: date reflects the max `last_seen_at`; fallback fires on empty table; `/ready` still
  503s on DB failure and stays outside the rate limiter.
* Manual check: hit `/ready`, see the current data date; run a local ingestion, hit it again,
  see the date advance; UI disclaimer line renders the new date.
**Out of Scope:**
* Exposing any freshness value to the *agent* (the fabrication trap stands); changing the
  disclaimer wording or the UI; removing the config fallback.

---

## 4. Trade-offs made visible (named rejections, one line each)

| Rejected option | Why |
|---|---|
| Staging DB / Neon branch + verify + promote | Second environment + promotion flow to protect ~50–100 rows already covered by yield floor + raw-rebuild runbook; over-engineering (§1A). |
| Ship the `is_active` hedge as a nudge now | Its own ship-gate (T0011.5) is unmet and the measured nudge-adherence base rate is adverse (2/2, 1/3 failures) (§1B). |
| Deterministic hedge enforcement (view / SQL injection / post-processing) | View ruled out by §4.2 #3 itself; injection crosses the tool boundary the repo already defended on the id-first nudge (§1B). |
| Fix the honesty items with more prompt wording this milestone | Contradicts the 2026-07-02 doctrine; the sanctioned path is baseline → designed prompt-v2 → re-measure (§1B). |
| Drop `is_active` mechanics entirely until the gate clears | Forfeits deterministic lifecycle data that gets costlier to reconstruct the longer accumulation runs without it (§1B). |
| Expose `last_seen_at` as a freshness proxy | Repeats the `posted_date` fabrication trap; §4.2 #2 already rules it out — kept internal. |
| Write ingestion to a separate DB and swap | Either two DBs leak into the serving path or a promotion step is reinvented; #1/#2 exist to make in-place writes safe (§1A). |
| Alembic alone as the schema-drift answer | Migrations don't detect out-of-band drift — the 2026-07-15 incident class; the pre-flight assertion is the missing detection half (§1D). |
| GitHub Actions as the keep-alive scheduler | UTC-only, 60-day auto-disable, 10+-min schedule drift vs a 15-min idle window (§1a) — cron ≠ ping. |
| Render Cron for ingestion | $1/mo floor, not free (§4). |
| Single-transaction `raw_jobs`+`clean_jobs` write, content_hash delta, orchestrator, rebuild-from-raw | §4.2 #7 deferrals; no inversion moved them, and the clean write is already statement-atomic (§1A). |

## 5. Assumptions I could not verify (need live verification; not asserted)

1. **`ms.vietnamworks.com/robots.txt` content and the ToS position** — the entire point of
   T0019.1; nothing here presumes the answer.
2. **Whether the checkpointer's idle pool connections hold Neon awake** — the §1a/§1C open
   question; T0019.7 is structured around measuring it, and the ~122 CU-h figure is arithmetic
   on documented rates, not an observation.
3. **The VietnamWorks API's current shape and yield** — the 5/5-reliable, ~50–112-posting
   numbers are from the 06/2026 spike; an undocumented API can have changed since. The
   pre-flight/yield-floor design assumes only "roughly similar," but the first T0019.6 manual
   run is the real test.
4. **Quota/limit values as of today** — Neon 100 CU-h & suspend behavior, Render 750 h &
   15-min spin-down, GitHub Actions terms, healthchecks.io free tier: all taken from the
   dated findings in `deployment-research-plan.md`, not re-checked live.
5. **GitHub Actions schedule drift magnitude** — "routinely 10+ min under load" is from §1a's
   research; tolerable at daily cadence either way, but not re-measured.
6. **That the live Neon schema exactly matches the reconciled dump** — T0018.4 loaded it from
   an already-reconciled sandbox, so it *should*; T0019.5's pre-flight assertion is the
   mechanism that turns this from an assumption into a checked invariant.
7. **Backfill data availability** — `first_seen_at` backfill assumes all 50 Neon `clean_jobs`
   rows have matching `raw_jobs.fetched_at` values (the dump loaded both tables, 50+50 rows,
   per `Repo_Current_State.md`); T0019.3's manual check should confirm the join is total
   before relying on it.
