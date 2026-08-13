# Offline Pipelines Design

> **Last verified:** 2026-08-12.
> This document owns the offline ingestion and evaluation pipelines.
> It retains sections 7-8 so historical citations continue to resolve after the serving-path split.

> **Eviction:** A pipeline detail leaves when its implementation is retired or responsibility moves
> to a different owner document.

## 7. Data Ingestion Pipeline (offline)

*Status: implemented*

Ingestion is **offline batch tooling** under `src/services/ingestion/`, isolated from the request
pipeline — it is never imported by the API, service, runtime, tools, or tracing layers (the layer
law is in `Full_Design_Document.md` §3). It runs as a manual, re-runnable CLI, not on a schedule.
The deep research behind every decision here is `research/archive/data-ingestion-stage.md` (§0.1,
the ✅
reliable & schedulable VietnamWorks experiment) and `research/job-site-comparison.md`; do not
re-derive it.

> **Status: live-DB operation built (T0019.1–.5, .7, .8); scheduling not yet landed (T0019.6).** The
> nightly cron's workflow file exists in the working tree but is **not committed** and its
> documentation was lost to a concurrent-session collision (see the T0019.7 completion report) —
> treat T0019.6 as open, not done, until it is committed with a completion report and its two human
> gates are cleared. Everything in §7 describes the pipeline as built and stays accurate. T0019
> changed three things about *how it runs*, none of which reshape the dataflow or tables above: (a)
> ✅ load semantics are now **accumulate-never-wipe** — the `TRUNCATE` in `clean_store.py` is dropped
> and the `(source, external_id)` upsert below is live code (`upsert_clean_jobs`), joined by hidden
> `is_active`/`first_seen_at`/`last_seen_at` lifecycle columns and a time-based expiry pass
> (**T0019.3**); (b) ⏳ an **external, out-of-band GitHub Actions cron** is intended to invoke the
> same CLI nightly against the live Neon DB (**T0019.6**, hard-gated on a robots.txt/ToS check,
> **T0019.1**, whose favorable verdict the maintainer **ratified on 2026-08-13** — the gate is
> cleared; see the cron activation runbook §1). The cron's `schedule:` trigger is **dormant**
> because PR #33 commented it out on `main`. Note that reaching `main` does not merely permit a
> schedule, it starts one: GitHub fires `schedule:` from the default branch automatically, which is
> how this workflow ran un-gated for 19 nights. Coverage and detail-visibility follow-ups are scoped
> as **T0019.9** and **T0019.10** (`docs/Tickets.md`); neither is implemented. This does **not**
> relax the §7 layer law or the `Full_Design_Document.md` §2 no-schedulers exclusion — the cron runs
> on GitHub's runner, never in the API process, and §2's exclusion is amended to name what it always
> meant: *in-request* background execution; (c) unattended-run safety — pre-flight schema assertion,
> pre-write yield floor, dead-man's-switch ping (**T0019.5**). Scope and sequencing:
> `docs/Tickets.md` T0019. Rationale: `research/archive/ingestion-milestone-plan.md`.
>
> ✅ **Production-DSN freeze lifted (2026-07-19, T0019.3).** The former rule here — *"do not run this
> CLI against the production DSN"* — is lifted. `clean_store.replace_clean_jobs` has been
> renamed `upsert_clean_jobs` and its `TRUNCATE` is gone, so a run against Neon accumulates via the
> `(source, external_id)` upsert instead of rebuilding the live table. `Repo_Current_State.md`
> carries the same lift.

**Design intent: source-agnostic.** v1 ingests **VietnamWorks only**, but the schema, cleaning, and
interfaces are built so a future board is just a new adapter + normalizer with **no table reshape**.
Only two components ever know a source's specifics — the **adapter** (fetch) and the **normalizer**
(payload → common shape). Everything downstream is shared.

**Dataflow.**

```
JobSource (VietnamWorksSource) --RawPosting--> raw_jobs (verbatim landing, upsert on (source, external_id))
   -> Normalizer (source-specific: payload -> NormalizedJob)
   -> Transform (SHARED, deterministic, no LLM, no network):
        HTML->text · is_internship · tech_stack keyword finder · role taxonomy · location city-alias map
   -> Loader: upsert into clean_jobs on (source, external_id)
```

**Tables.**

- **`raw_jobs`** — verbatim landing: `id`, `source`, `external_id`, `source_url`, `raw_payload`
  (JSONB), `content_hash`, `fetched_at`; unique `(source, external_id)`. Never lossy. Lives in the
  application `DATABASE_URL` Postgres alongside `clean_jobs` (never Langfuse's Postgres).
- **`clean_jobs`** (enriched, agent-facing) — the original `title`, `company`, `description`,
  `tech_stack` plus `role`, `source`, `external_id`, `source_url`, `posted_date`, `is_internship`,
  `job_level`, `location`, and structured salary (`salary_min`, `salary_max`, `salary_currency`,
  `is_salary_negotiable`). `title` stays the raw posting title; `role` and `location` hold canonical
  normalized values. **`description` is a single merged free-text blob** (job description +
  requirements + benefits) — there are deliberately **no `requirement`/`benefits` columns**, because
  that is the common shape across all boards (most return one blob; VietnamWorks'
  separately-provided `jobRequirement`/`benefits` are concatenated back in its normalizer, and
  survive verbatim in `raw_jobs`). Unique `(source, external_id)`.

**Deterministic cleaning** (all pure, unit-tested, no LLM — keeps ingestion testable and aligned
with the project's "no over-engineering" rule; LLM extraction is a deferred future enhancement):

- **`tech_stack`** — a keyword finder matches the source skills array + the description text against
  a curated **technology dictionary** (`config/settings.yaml`), keeps technologies only
  (role/category labels dropped), dedups, emits the comma-separated string the SQL agent already
  expects.
- **`role`** — a **role taxonomy** maps the messy title into a fixed canonical set (AI Engineer,
  Data Scientist, Data Engineer, Data Analyst, ML Engineer, Software Developer), using
  keyword/pattern rules with the source `jobFunction` as a tiebreaker; unmatched titles fall to
  `Other` (never dropped).
- **`location`** — a **city alias map** collapses messy location text to a unified city/province
  (`Ha Noi`/`Hanoi` → `Hanoi`; `HCM`/`TPHCM`/`Ho Chi Minh`/`hcm` → `Ho Chi Minh City`); multi-city →
  comma-separated canonical set; street address discarded.
- **`description`** — source text is merged into **one free-text blob** (HTML stripped).
  VietnamWorks arrives pre-split, so its normalizer concatenates `jobDescription` + `jobRequirement`
  + benefit values back together; the other boards already return a single blob. This keeps one
  shape across all sources and one field for the agent to read.
- **salary** — mapped into **structured** fields rather than a display string, so the agent can
  range-filter and sort (the core "pay ≥ X" query): `salary_min`, `salary_max` (numeric, nullable),
  `salary_currency` (e.g. USD/VND — required whenever a number is present, since VietnamWorks mixes
  currencies), and `is_salary_negotiable` (bool). VietnamWorks maps
  `salaryMin`/`salaryMax`/`salaryCurrency` directly and sets `is_salary_negotiable = not
  isSalaryVisible`; a future string-only board parses its salary string deterministically, else
  leaves min/max NULL with `is_salary_negotiable = true`.

**Identity & idempotency.** Upsert on `(source, external_id)` with a `content_hash` for change
detection; re-running refreshes rather than duplicating. The fixtures are replaced; a tunable
`max_jobs` cap (~50) bounds a run.

**Configuration.** Everything tunable lives in `config/settings.yaml` `ingestion.*`: API URL,
AI/Data keyword queries, `jobFunction` ids, cap, delay, User-Agent, the technology dictionary, the
role taxonomy, and the city alias map. Internal records (`RawPosting`, `NormalizedJob`) and the
table models live in `models.py`, per project convention.

**Agent-layer impact.** Because the new `clean_jobs` columns are agent-visible, T0009 also updates
`prompts.schema_context`, the SQL-generation prompt, and the T0008 honesty rules (notably: salary is
numeric and currency-scoped — filter within a `salary_currency` — and may be NULL /
`is_salary_negotiable = true` → "may be missing or negotiable for some postings", not "not in the
data"). This is the column-cheap schema growth §4 describes, applied.

### 7.1 Unattended-run safety

*Status: implemented (T0019.5).*

Once the CLI runs unattended on a schedule (T0019.6) against the live DB, "it failed and someone
noticed" stops being a reliable control. `src/services/ingestion/safety.py` supplies three checks,
and `loader.py::run_ingestion` orders them so that **every abort happens before the write it
protects**:

- **`assert_clean_jobs_schema()` — pre-flight, before anything is fetched.** Queries live
  `information_schema.columns` for `clean_jobs` and compares against `{c.name for c in
  CleanJob.__table__.columns}`. The expected set is **derived from the ORM, never hand-maintained**
  — that is the whole point, since a hand-copied column list is exactly the artifact that drifts. It
  reports both directions (missing *and* unexpected) and treats an empty column set as "table
  absent" with its own message rather than listing every column as missing. It runs **first in
  `run_ingestion`** — before the source is constructed — so a drifted schema costs zero fetches and
  zero writes. This is the *detection* half of the schema-drift problem; Alembic (§4) is the
  *correction* half. Migrations cannot detect a database altered out-of-band, which is the incident
  that motivated both (`Known_Issues.md`, schema-drift entry).
- **`assert_min_yield(fetched, min_yield)` — after the raw upsert, before the clean upsert.** Raises
  when a run returns implausibly few postings (`ingestion.safety.min_yield`). The placement is
  deliberate and load-bearing in two ways: `raw_jobs` is written *first*, so a bad run still
  preserves its evidence for diagnosis; and the abort lands *before both* the clean upsert **and**
  the expiry pass — which matters, because `expire_stale_clean_jobs` ages rows on `last_seen_at`.
  Aborting after a skipped clean write but before expiry would let a single bad fetch mark the
  entire healthy corpus inactive.
- **`send_dead_man_ping(url)` — last, and only on a fully green run.** POSTs to a healthchecks.io
  URL (`HEALTHCHECKS_URL`, optional). It never raises: an unset URL logs `ingestion.ping_skipped`
  and returns `False` (the normal local path, not an error), and any HTTP failure logs
  `ingestion.ping_failed` and returns `False`. **The signal is the withheld ping, not a sent alert**
  — the monitor alerts on *silence*, which is what makes it a dead man's switch rather than one more
  thing that can fail quietly.

The library/process split is kept clean: `run_ingestion` stays library code and lets
`IngestionSafetyError` propagate; `main()` owns the process contract, catching it, logging
`ingestion.aborted`, and exiting non-zero. Nothing in this module imports or is imported by the
request path.

**Deferred.** Other boards, anti-bot scrapers, ~~a scheduler/cron~~ (*scoped 2026-07-16 as T0019.6 —
see the status note at the top of §7*), LLM extraction, parsing a salary *string* into numbers (not
needed for VietnamWorks, which supplies the numbers directly), translating source text to a single
language, and cross-board dedup are out of scope (see `Tickets.md` T0009 Out of Scope and
`research/job-site-comparison.md`).

---

## 8. Evaluation Harness (offline)

*Status: implemented (T0011–T0012) — **Evaluation v1 (Phase 1)**.*

This is the **first version** of the project's evaluation phase: a deliberately-scoped offline
harness whose deliverable is the **v1 baseline** — the first measured snapshot of agent behavior
against a pinned fixture and golden set. It is intentionally minimal (offline only, no CI gate, no
online/production scoring, no chart/DAG metrics — those are later phases, §8.7). Everything
downstream that cites "the baseline" means this v1 baseline, and the T0011.5 report records it as
such (dated, tied to the fixture + golden version it was measured against). A later re-measure
produces a v2 baseline; the two are only comparable because the fixture is version-pinned (§8.3).

The evaluation harness is **offline quality tooling**, isolated from the request pipeline exactly
like §7 ingestion — it is never imported by the API, service, runtime, tools, or tracing layers, and
it runs on demand (`deepeval test run`), never on a schedule and (for now) never as a CI gate. Its
job is to establish a **measurable baseline** of the agent's task-correctness and its `MVP_Spec.md`
§3 honesty bar *before* any stage whose design depends on measured model behavior is built (the
`is_active` honesty hedge in Ingestion Deploy Readiness — renumbered **`Tickets.md` T0019**, scoped
2026-07-16).

> **This dependency did its job — by blocking (2026-07-16).** The T0011.5 baseline never ran (still
> blocked on maintainer credentials), so the gate the hedge's design set for itself is unmet, and
> the evidence that does exist is adverse (`Known_Issues.md` § Agent runtime & prompts:
> hidden-salary honesty violated 2/2, freshness fabricates 1/3). T0019 therefore **cut the hedge
> from its scope** rather than shipping it unmeasured: the `is_active` lifecycle *mechanics* ship as
> hidden DDL columns (no prompt surface, no eval dependency), and the *agent exposure* is deferred
> behind T0011.5 → prompt-v2 few-shot pass → a targeted recalibration delta. The harness's stated
> purpose — measure before building on measured behavior — is what produced that split
> (`research/archive/ingestion-milestone-plan.md` §1B). The full grounding — DeepEval mechanics, the
> 2026
> version-pinned facts, and the InternHunter-specific findings — is
> `research/archive/deepeval-sql-agent-eval-planning.md`; **read its §11 first.** Do not re-derive
> it here.

### 8.1 What it measures — three seams

The agent is not one LLM call. `query_clean_jobs` takes a **natural-language question**, and a
*separate, nested* `generate_sql` model call (`src/agents/tools/query_clean_jobs.py`) turns it into
SQL that deterministic code then validates and runs. So a single agent run has three distinct
decision points, and the harness scores each:

| Seam | What the model decides | Metric attaches to |
|---|---|---|
| 1. Routing | which tool + the NL question passed to it | the agent tool-call span |
| 2. NL→SQL | the SQL string (**invisible** to the ReAct trace) | the nested `generate_sql` LLM span |
| 3. Synthesis | the final user-facing answer | the final output |

Seam 2 is the point the generic research (§3) calls "most failure-prone," and it is **not** on the
tool call — it is inside the nested `generate_sql`. Capturing it is a tracing concern, so per the
`Full_Design_Document.md` §2 tracing-boundary law it must **not** be met by hard-coding a DeepEval
`@observe` inside the tools layer. Instead the harness threads its DeepEval `CallbackHandler` in
through **runtime config** — the same injection seam Langfuse tracing already uses (§2.5) — so the
nested call surfaces as its own span without eval concerns leaking into tool code. Whether
`generate_sql` needs a small config-propagation parameter to receive that callback is the one **open
implementation question** carried into T0011.

### 8.2 Metric stack (Phase 1)

Deterministic checks for everything exact; LLM-judge checks for everything semantic (research §3):

- **Seam 1 — Routing.** `ToolCorrectnessMetric` (deterministic — was `query_clean_jobs` /
  `get_job_details` / `get_current_time` the right choice, in the right order?) plus a light
  referenceless `ArgumentCorrectnessMetric` on the **NL question** the agent passed.
- **Seam 2 — NL→SQL.** `ArgumentCorrectnessMetric` plus a schema-aware `GEval` ("does this SQL
  respect the `clean_jobs` schema and answer the question?") on the `generate_sql` span.
  Referenceless — no expected SQL string is stored.
- **Seam 3 — Synthesis.** `TaskCompletionMetric` (did the user get what they asked?) plus
  **`FaithfulnessMetric`** with the tool's returned string as `retrieval_context` — this catches
  *fabrication* (invented freshness, hidden-salary claims not in the data) — plus a **`GEval`
  honesty** criterion for *omission* (the truncation caveat is emitted deterministically by
  `_build_answer`; the risk is the agent stripping it when it rewrites the answer for the user).

Thresholds are **calibrated after the first baseline run**, not pre-set (research §9): a threshold
above the baseline blocks every build; below it, nothing signals.

### 8.3 Golden dataset & the seeded eval database

- **~17 versioned goldens** (inside the 15–25 band), stored in-repo alongside the harness,
  automating the `T0008.3` manual honesty checklist plus **explicit probes** for the recorded
  model-behavior risks — freshness fabrication and hidden-salary phrasing (`Known_Issues.md`,
  agent-runtime section). Each golden carries: NL input, `expected_tools`, an optional *semantic*
  `expected_output`, and metadata (category, difficulty, honesty-probe flag). The expected SQL is
  deliberately **not** stored — the seam-2 metrics are referenceless. They span five categories: **A
  grounded retrieval** (count/list/truncation, asserting the fixture's pinned totals), **B
  multi-turn refinement** (stored as `ConversationalTestCase`s so the agent's own context-carry is
  what gets scored, not a pre-flattened turn), **C honesty probes** (freshness, cross-currency
  "highest paid", absent-tech, out-of-schema "remote", hidden salary, hidden seniority), **D
  safety/refusal** (unsafe/off-topic/injection — asserting `expected_tools=[]` **and** a refusal, so
  a model that queries the DB before refusing still fails), and **E resilience** (vague input,
  dangling pronoun with no prior turn). **6 of the ~17 are flagged `honesty_probe`** — the subset
  the T0011.5 go/rethink verdict on the `is_active` design rests on.
- **The harness runs against a small (~22-row), version-controlled seeded fixture database, not live
  `clean_jobs`.** This is what lets honesty goldens assert exact counts, truncation notices, and
  specific rows, and what makes before/after comparison valid (research §6: a golden's baseline is
  only meaningful against a fixed dataset version). The fixture is versioned with the goldens;
  changing it changes the baseline. Its free text (`title`/`company`/`description`) is drawn from
  the real captured postings in `research/experiments/vietnamworks_ai_data_sample.json` so answers
  read authentically, while the structured columns are *engineered* to a fixed distribution that
  pins every golden. The role split sums to exactly 22 — AI Engineer 5 and Data Scientist 4 (the two
  counts goldens assert), plus Data Engineer / ML Engineer / Data Analyst 4 each and 1 Other;
  overlaid pins are Python in 12 rows (7 of them Hanoi → the two-turn refinement), COBOL in 0, both
  USD and VND salaries present, and `posted_date`/`job_level` NULL on all 22. Internship-ness is one
  filterable attribute among many — the corpus (and the fixture, ~5 of 22 rows) is mostly
  non-internship AI/Data postings, matching the real live data (see `Known_Issues.md` scope-drift
  note).

### 8.4 Judge LLM

- The generic research (§5) recommended Llama-3-70b, which Groq **retired** (research §11.4). The
  primary judge for T0011 is its Groq replacement (`openai/gpt-oss-120b` or `qwen/qwen3.6-27b`),
  **pinned by a live JSON-reliability spike** — DeepEval hard-fails without schema-valid JSON, and
  `gpt-oss-120b` has reported structured-output regressions.
- **Confirmed fallback: Google Gemini free-tier** (adds a `GEMINI`/`GOOGLE_API_KEY` and a second LLM
  provider). Beyond de-risking the JSON problem, a Gemini judge **decouples judge load from Groq** —
  today the agent *and* a Groq judge would share one free-tier limit — which makes Gemini the
  natural *primary* if/when the CI gate lands. The judge is wrapped in a `DeepEvalBaseLLM`;
  `instructor`/LiteLLM coercion is adopted only if a Groq judge is kept and needs it. Eval quality
  is bounded by judge quality (research §5) — 70B-class is the floor.

### 8.5 Score writeback to Langfuse

A post-run step calls `langfuse.create_score(name=metric, value=score, trace_id=…, data_type=…)` on
the v4 (OTEL) client — `BOOLEAN` for honesty pass/fail, numeric for graded metrics — so eval scores
land on the same trace as the raw run and Langfuse stays the single pane of glass (it does **not**
replace Langfuse's role, per §2.5). Re-runs are idempotent via `score_id = f"{trace_id}-{metric}"`.
The one integration seam to verify in implementation is threading the Langfuse `trace_id` onto the
DeepEval test case (research §11.5).

### 8.6 How it runs, and its boundaries

- **On-demand, local-first.** T0011 delivers a runnable `deepeval test run` (pytest-integrated) plus
  the dataset, metrics, and writeback. It is **not** wired into CI — the first `.github/workflows/`
  PR gate is a deliberate **fast-follow ticket**, matching the deferred-deploy posture and avoiding
  standing up CI + Groq-in-CI rate-limit handling before it is needed.
- **Layer isolation.** The harness treats the agent as a black box via its public entrypoint plus
  the injected `CallbackHandler`; the only touch inside the agent boundary is the config seam that
  lets the `generate_sql` span be observed (§8.1), which carries no eval logic and is inert in
  production.
- **No online eval.** Production-trace scoring, `DAGMetric`, chart metrics, and production-sampled
  goldens are out of scope (research §§4, 8) — this milestone measures the offline baseline only.

### 8.7 Prerequisite & deferred

- **Prerequisite (not owned here):** the agent must run on a **non-retired model** for the baseline
  to mean anything — `config/settings.yaml` still pins the agent to `llama-3.3-70b-versatile`, which
  Groq shuts down 2026-08-16 (`Known_Issues.md`, F1). That migration is a **separate** follow-up,
  deliberately not folded into T0011.
- **Deferred:** the CI gate, online/production eval, `DAGMetric`, Phase-2 chart metrics,
  production-sampled goldens, and any judge-matrix / Confident-AI cloud. And, by design, **fixing**
  a measured behavior — T0011 *measures*; remediation is separate work.

---
