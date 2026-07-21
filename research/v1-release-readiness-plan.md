# v1.0 Release Readiness Plan — Gap Analysis & M20–M22 Shape

> **Status:** Research / pre-design (2026-07-19). Scopes what stands between the current
> deployed state (https://internhunteragent.onrender.com, T0018.4 stack + T0019.1–.5/.7
> landed) and a **v1.0 release of the existing MVP** — fork A: *hardening*, not the
> `MVP_Spec.md` §6 future features. It audits the §4 Definition of Done and the §3 quality
> bar against recorded evidence, separates release-blockers from quality debt, and proposes
> a three-milestone shape (M20–M22) ready to graduate into `docs/Tickets.md` **after
> maintainer approval — this document deliberately does not touch `Tickets.md`**.
>
> **Decisions taken as fixed (not re-litigated here):** `main` reconciliation is the
> maintainer's call; T0019's sequencing is fixed as scoped 2026-07-16; `is_active` agent
> exposure stays gated behind T0011.5 → prompt-v2 → recalibration and is therefore
> **post-1.0 by construction**.
>
> **Read first:** `docs/MVP_Spec.md` §3–§4; `docs/Repo_Current_State.md`;
> `docs/Known_Issues.md`; `docs/Tickets.md` T0019 + Backlog;
> `pre-deploy-refinement-plan.md` §6; `ingestion-milestone-plan.md` §1/§5.

---

## 0. TL;DR

- **The §4 DoD is *mostly* met, not met.** Seven of eight bullets are observably true on
  the live deploy. Bullet 6 — *"refuses an unsafe or unanswerable request … instead of
  failing or guessing"* — is only half-true: unsafe requests are deterministically refused
  (SQL validator), but on *unanswerable* requests the model measurably guesses (freshness
  fabrication 1/3, hidden-salary prohibited phrasing 2/2), and the instrument that would
  quantify this (T0011.5 baseline) has never run. This is the single substantive DoD gap
  and the core of the §3 "trustworthy over impressive" bar.
- **The release artifact itself is the second gap.** The deployed code lives on a feature
  branch; `main` lags it (carries only through T0017.2); there is no CI merge gate; Render
  auto-deploys off the feature branch; T0019.6's workflow file sits **untracked** in the
  working tree with its documentation lost; and an uncommitted `MVP_Technical_Design.md`
  edit references ticket IDs (**T0019.9/.10**) that exist in no tracked document. A "v1.0"
  tag has nothing trustworthy to point at yet. **New fact raising the stakes (2026-07-19):**
  the workflow's own header comment records that GitHub only fires `schedule:` triggers
  from the **default branch** — so the nightly cron is dormant until the chain reaches
  `main`, making reconciliation a hard dependency of T0019.6 *running*, not just hygiene.
- **Proposed shape:** **M20 Release Integrity** (T0019 closeout + `main` reunification +
  CI gate) → **M21 Serving-Path Hardening & Honesty Baseline** (read-path assertion,
  `get_job_details` allowlist, error logging, T0011.5 baseline → prompt-v2 → re-measure)
  → **M22 v1.0 Release Cut** (DoD sweep, ToS posture applied, docs conformance, tag).
  M20 and M21 are largely parallel; both block M22.
- **Eight maintainer gates/decisions block progress** (§4 below) — most notably the `main`
  reconciliation call, T0011.5 credentials, the T0019.5 B–E live verification, and the
  release bar for DoD bullet 6.

---

## 1. Gap analysis — §4 DoD and the §3 quality bar

### 1a. DoD bullet-by-bullet verdict

Evidence is cited from `Repo_Current_State.md` (RCS), `Known_Issues.md` (KI), and
completion reports; "live" means observed against the deployed service.

| # | DoD bullet (`MVP_Spec.md` §4) | Verdict | Evidence |
|---|---|---|---|
| 1 | Job-data question → grounded answer | **Met** | Verified live end-to-end 2026-07-16 (T0018.4); `query_clean_jobs`/`get_job_details` ground every answer; no-fabrication rules in `config/prompts.yaml`. |
| 2 | Refine ≥2× in one conversation, context-aware | **Met** | M7 checkpointer memory; T0009.8 multi-turn manual verification; demo UI reuses the pinned session id across turns (T0018.3). *Caveat:* coherence is observationally verified, not eval-scored (`pre-deploy-refinement-plan.md` §5g) — debt, not a gap. |
| 3 | Two conversations stay independent | **Met** | `session_id → thread_id` isolation (T0007.2) + tests. |
| 4 | Session identity issued when absent, reusable | **Met** | T0018.1 mints UUID4 server-side on both endpoints; UI pins and reuses it. |
| 5 | Memory survives a service restart | **Met** | Postgres-backed `AsyncPostgresSaver` on Neon; state external to the process; Render redeploys/spin-downs since 2026-07-16 haven't reset sessions. *Caveat:* the §2 capability text also claims multi-**instance** safety — plausible by construction (shared Postgres) but never observed; prod runs `WEB_CONCURRENCY=1`. The DoD bullet itself only requires restart survival. |
| 6 | Refuses unsafe/unanswerable clearly, never guesses | **Partially met — refuted as "already met."** | *Unsafe:* met deterministically (read-only validator, single-table allowlist T0010.3, graceful typed errors T0010.1). *Unanswerable:* measured failures — freshness question fabricated a specific "most recent" job 1/3 (T0009.8, KI § Agent runtime); hidden-salary honesty rule violated 2/2 with the exact prohibited phrasing (T0009.8). The quantifying instrument (T0011.5 baseline + calibrated thresholds) is **blocked on maintainer credentials** and has never produced a number. |
| 7 | Every interaction traced, mappable to request | **Met** | Langfuse Cloud Hobby wired; `trace_url` populated (T0012.4); UI surfaces the trace link. *Caveat:* a DB failure inside `query_clean_jobs` is swallowed unlogged (KI, MED) — the *trace* exists but cannot explain that failure class, which grazes the §2 observability intent. |
| 8 | Starts cleanly with a single documented command | **Met with caveat** | `docker compose up -d` / Render Docker boot verified. Native Windows `uv run uvicorn` hangs on the `ProactorEventLoop`/psycopg incompatibility (KI, LOW) — a dev-ergonomics issue; the *documented* command works. |

**Conclusion: the "§4 DoD is already met" claim is refuted on bullet 6 and confirmed on
the other seven.** Bullet 6's gap is not "the model is sometimes wrong" (any LLM is); it is
that (a) the failure rate on the two probed honesty scenarios is *measured and adverse*,
and (b) the project's own doctrine (2026-07-02, KI § Agent runtime) forbids closing it by
prompt-tinkering — the sanctioned path is baseline → designed prompt-v2 few-shot →
re-measure, and that path has not been walked because T0011.5 never ran.

### 1b. Quality bar (§3) assessment

- **Trustworthy over impressive** — the bullet-6 gap above, plus one *structural* leak:
  `get_job_details` runs `SELECT *` and returns **every** column through natural language,
  including the deliberately hidden `source`, `external_id`, and — since T0019.3 — the
  lifecycle columns (KI § Query tooling, MED). Today all rows are `is_active=true` so the
  leak is cosmetic; **the moment the cron runs and rows expire, the agent can surface
  lifecycle state through one tool that the other tool (and the whole honesty design)
  deliberately hides**. That converts this from debt to a blocker-tier inconsistency for a
  release whose posture is "hidden columns are hidden."
- **Coherent across turns** — met at the observational level; unmeasured (§5g). Acceptable
  for v1.0; a conversational metric is post-1.0.
- **Resilient under imperfection** — largely met in code: typed error contract + graceful
  answer (T0010.1), empty-answer fallback (T0012.5), friendly busy path for 429/quota
  (T0016.2), mid-stream error degradation in the UI (T0018.3). Two dents: the ~60 s
  free-tier cold start makes the demo *look* dead (KI, MED — mitigation fully documented
  by T0019.7 but not yet enabled/measured), and the unlogged `ExecutorError` swallow means
  a real defect can hide behind the graceful message indefinitely (that is exactly how the
  2026-07-15 schema drift stayed invisible).

### 1c. Release-blockers (contradict the DoD/§3 or make the v1.0 claim untrue)

1. **DoD-6 honesty evidence gap.** T0011.5 v1 baseline (needs maintainer creds) →
   prompt-v2 few-shot pass (freshness refusal, hidden-salary phrasing, out-of-schema
   short-circuit) → re-measure against calibrated thresholds. This is fork-A hardening of
   *existing* behavior, squarely in scope. → **M21.**
2. **Release-artifact integrity.** `main` behind the deployed branch; no CI merge gate
   (§6i); Render auto-deploys off a feature branch; T0019.6's workflow untracked +
   docs lost; uncommitted `MVP_Technical_Design.md` edit citing phantom T0019.9/.10; the
   cron's default-branch requirement. A v1.0 tag needs one trusted, gated `main`. → **M20.**
3. **T0019.5 safety code has never run against a live Postgres** (KI, HIGH · OPEN — the
   documented accepted-at-merge gap). Manual checks B–E are the explicit gate before the
   cron is enabled against Neon. → maintainer execution, sequenced inside **M20**.
4. **`get_job_details` hidden-column leak** (§1b above). One explicit column list mirroring
   the `schema_context` allowlist. → **M21.**
5. **API-side read-path schema assertion absent** (KI, the unowned remnant of the HIGH
   drift incident). The serving path — the actual product — still runs unchecked against
   the schema; the write path got its assertion in T0019.5. Reuse
   `assert_clean_jobs_schema` (or a variant) at FastAPI startup. → **M21.**
6. **ToS republishing posture undecided while the demo is public** (KI, MED · DECISION).
   Not a cron question — the deployed snapshot raises it today. Cheapest partial step is
   (b) attribution + per-posting source URL, which is closest to what VietnamWorks ToS §7
   actually asks. → maintainer decision; implementation (if any) lands in **M22.**
7. **T0019.8 (truthful `/ready` disclaimer date) is still open.** The static
   `api.demo.data_snapshot_date` becomes *false* on the first cron run — a direct
   §3-trustworthiness regression if the cron activates first. Must land before (or with)
   cron activation. → **M20** (T0019 closeout).

### 1d. Quality debt (real, recorded, not blocking v1.0)

Grouped; every item already lives in `Known_Issues.md` — this list only *classifies* them
for the release. None contradict a DoD bullet.

- **Ops/cost:** ~60 s cold start (T0019.7 runbook ready; escape hatch $7/mo); Neon
  idle-pool question (same runbook); GitHub Actions 60-day auto-disable unmitigated (the
  named keepalive action is defunct — ToS-blocked; see the workflow header); Langfuse
  self-host secret checklist (moot unless self-hosting).
- **Checkpointer pool has no connection-health check** (KI, MED, found 2026-07-21): the
  raw psycopg `AsyncConnectionPool` in `src/core/checkpointer.py` holds idle Neon
  connections with no `check=` validator, and a live incident showed this is evidence
  the Neon idle-pool question above resolves unfavorably — idle pool connections do
  **not** keep Neon awake. Worse, a resulting `psycopg_pool.PoolTimeout` gets
  misclassified by `classify_provider_busy_error()` as Groq/provider pressure (its class
  name contains `"timeout"`), so a DB-side hiccup surfaces to users as "the demo is busy"
  — masking the real cause. Candidate fix: `check=AsyncConnectionPool.check_connection`.
  No ticket owns it yet.
- **Ingestion coverage:** `max_jobs: 50` below the measured ~50–112 yield + fixed query
  order starves later queries (KI, MED — the two combinable fixes are recorded);
  `pages_failed` produced but unconsumed; no within-run re-queue of failed pages;
  `init_db.sql` diverges from the Alembic head (eval-fixture path risk).
- **Model behavior (eval-milestone territory, post-baseline):** duplicate identical tool
  call; out-of-schema stall latency; salary-sort currency scoping; id-first nudge
  best-effort. These are measured *by* M21's baseline, fixed only where prompt-v2's
  designed pass covers them — not chased individually.
- **Dev/UI/harness ergonomics:** native Windows uvicorn hang; SSE parser rigidity; no
  client idle timeout; mid-stream error bubble untestable locally; 2 benign mypy errors;
  `evals/conftest.py` DATABASE_URL redirect; deepeval Windows UTF-8; GEval criteria in
  code not config; `thinking_budget: 0` decision pending its spot-check.
- **Deliberately deferred (§6m, unchanged):** checkpointer row TTL, pool tuning under
  concurrency, PII/trace retention policy, uptime monitoring beyond the sanctioned set.

---

## 2. Proposed milestone shape — M20–M22

Numbering is illustrative (next free milestone numbers); the maintainer assigns final IDs
in `Tickets.md`. Ticket-level splits are indicative, not scoped to house depth yet.

### M20 — Release Integrity (branch reunification + T0019 closeout + CI gate)

**Objective:** one trusted `main` that a CI gate protects and that both deploy paths
(Render web service, GitHub Actions cron) hang off — with T0019 actually finished, not
half-landed in a working tree.

**In scope (indicative tickets):**
- **T0019 closeout:** re-review, re-document, and commit `.github/workflows/ingestion.yml`
  (the T0019.6 redo — the file survived, its docs didn't); land **T0019.8** (truthful
  `/ready` date — already fully scoped, blocked-on satisfied); reconcile or revert the
  uncommitted `MVP_Technical_Design.md` edit and its phantom T0019.9/.10 references
  (maintainer decision D3).
- **`main` reconciliation execution** — per the maintainer's decision (D1); merge, don't
  rebase, matching the 2026-07-19 precedent. Includes flipping Render's deploy source to
  `main` and correcting the now-stale "main is stuck at T0009" lines (`Tickets.md`
  Backlog, memory notes).
- **CI merge gate** (`pre-deploy-refinement-plan.md` §6i): GitHub Actions PR workflow
  running `pytest` (standard suite — `eval`-marked stays excluded: needs creds + spends
  quota), `ruff check`, `mypy`. Branch protection on `main`.
- **Cron activation sequence** (maintainer-gated): T0019.5 manual checks B–E against a
  local Docker Postgres (D5) → one-time `alembic stamp head` on Neon (D6) → T0019.1
  verdict confirmed in a *tracked* document (D2) → first `workflow_dispatch` run watched
  per the T0019.6 manual checklist.

**Dependency ordering:** T0019 closeout → reconciliation → CI gate → cron activation.
The cron *cannot* fire before reconciliation (default-branch rule); everything else in
M20 is independent of M21.

### M21 — Serving-Path Hardening & Honesty Baseline

**Objective:** close the two classes of gap in the thing users actually touch — the
read path's structural holes, and DoD bullet 6's evidence gap — via the sanctioned
measure-then-fix path.

**In scope (indicative tickets):**
- **API-side startup schema assertion** — reuse/adapt `assert_clean_jobs_schema` at
  FastAPI startup (fail loudly at boot, not mid-query). Closes the read-path half of the
  2026-07-15 drift incident.
- **`get_job_details` explicit column allowlist** mirroring `schema_context` (drops the
  `SELECT *`); extend the hidden-column guard tests to cover the details path.
- **`query_clean_jobs` error observability:** the one-line `logger.error` at the
  `ExecutorError` catch site (+ the validator-reject branch).
- **Pre-baseline checks:** confirm the `qwen/qwen3.6-27b` model ID live (§6e / KI LOW);
  run the blocked live probes (T0017.1/.2 streaming checks, T0012.10 judge spot-check +
  the `thinking_budget` decision, T0011.6 judge-agreement gate) — all need maintainer
  creds (D4).
- **T0011.5 v1 baseline:** full 17-golden run, frozen v1 metric set, calibrate
  thresholds, write the baseline report (needs Groq/Google creds + ~3 daily quota windows
  or a paid tier — see the recorded Groq TPD constraint).
- **Prompt-v2 designed pass + re-measure:** few-shot examples for the measured failures
  (freshness refusal, hidden-salary phrasing, out-of-schema short-circuit; optionally
  salary-sort scoping and id-first), the §5c `evaluation_steps` refinement in the same
  pass per §7 Phase 3, then the v2 baseline diffed against v1 and judged against the
  release bar (D9).

**Dependency ordering:** the three code tickets are independent and can start
immediately (parallel with M20). The baseline chain is strictly ordered:
pre-baseline checks → v1 baseline → prompt-v2 → v2 re-measure. Nothing in M21 depends on
M20 *except* that the eventual prompt-v2 merge should go through M20's CI gate if it
lands first.

### M22 — v1.0 Release Cut

**Objective:** turn "the deploy works" into a versioned, defensible release: every DoD
bullet verified and recorded against the shipped artifact, the legal posture decided and
applied, the docs telling the truth, and a tag on `main`.

**In scope (indicative tickets):**
- **DoD verification sweep:** a scripted manual pass of all eight §4 bullets against the
  live deploy, recorded in `Manual_Verification_Guide.md` (the release's evidence page).
  Includes a restart-survival check and the two-session independence check run *live*.
- **ToS posture applied** per D8 — if (b): source attribution + per-posting URL on the
  demo surface / disclaimer.
- **Docs conformance:** `README.md` quickstart = the single documented start command
  (bullet 8); `Repo_Current_State.md` refresh; archive stale roadmap notes; record the
  keep-alive/idle-pool outcome (T0019.7 runbook, D7) and the chosen 60-day auto-disable
  mitigation (D11).
- **Release notes + `v1.0.0` tag on `main`** (and the Render deploy pinned to it).

**Dependency ordering:** hard-blocked on M20 (trusted `main` + CI) and on M21's release
bar being met or explicitly waived (D9). The keep-alive measurement (D7) should be
*recorded* by M22 but its outcome (shed-idle-connections / shrink window / $7 tier) does
not block the tag — it changes config, not the artifact.

---

## 3. Explicit Out-of-Scope per milestone (defers to post-1.0)

**M20 defers:**
- Any history rewriting / rebase of the ticket-branch topology (merge only).
- Running `eval`-marked tests in CI (creds + quota; revisit post-1.0 with a scheduled,
  budgeted eval workflow).
- Multi-environment CD (staging), IaC/Render blueprints, deploy previews.
- A second Free service or any workspace change that erodes the 750-instance-hour margin.

**M21 defers:**
- **`is_active` agent exposure + honesty hedge** — stays gated behind T0011.5 →
  prompt-v2 → targeted recalibration delta (fixed decision). M21 *produces* the baseline
  and prompt-v2 that gate demands, but the exposure itself plus its new goldens are
  post-1.0.
- Deterministic hedge enforcement (view / `WHERE` injection / post-processing) — remains
  ruled out.
- Splitting the Honesty metric (sharpen only, §5f), a multi-turn conversational metric
  (§5g), criteria-to-config centralization (§5e), and any runtime metric toggle (§5h).
- Chasing the individual model-behavior LOW items outside what the designed prompt-v2
  pass covers.

**M22 defers:**
- Everything in `MVP_Spec.md` §6: resume upload, embeddings/RAG similarity, charts,
  larger/live data expansion beyond the nightly VietnamWorks refresh, accounts/auth.
- A second job board (ITviec/TopDev/TopCV/LinkedIn) and the multi-source orchestrator
  (§4.2 #7 deferrals, all unchanged).
- Ingestion coverage fixes (`max_jobs` raise + query interleave) **unless** the
  maintainer pulls them forward (D13) — they change corpus breadth, not correctness, and
  the request-volume increase interacts with the ToS posture.
- Custom domain (cosmetic), paid tiers (unless D7's decision rule forces the $7 escape),
  §6m ops items (TTL, pool tuning, PII retention, broader monitoring), checkpointer
  Windows-dev fix, SSE parser generalization, client idle timeout.

---

## 4. Maintainer decisions & gates (blocking; listed for the maintainer to answer)

Executions (no choice to make, only you can run them):

- **D2 — T0019.1 verdict confirmation.** Confirm the favorable robots/ToS verdict in a
  tracked doc. Note: the *uncommitted* `MVP_Technical_Design.md` edit claims this was
  confirmed 2026-07-19, but no committed document records it — confirm authoritatively.
- **D4 — Credentials for the eval/live checks.** T0011.5 baseline, T0011.6 judge
  agreement, T0012.10 spot-check, T0017.1/.2 live probes, model-ID confirmation — all
  blocked on Groq/Google creds only you hold. Budget: ~3 daily Groq TPD windows or paid.
- **D5 — T0019.5 manual checks B–E** against a local Docker Postgres, *before* the cron
  is enabled against Neon (the KI HIGH gate you accepted at merge).
- **D6 — One-time `alembic stamp head` on Neon** (Manual_Verification_Guide → T0019.2 §F).
- **D7 — Execute the T0019.7 keep-alive runbook**, take the 24 h Neon reading, apply the
  pre-written decision rule, record the outcome in §1a.

Decisions (a call to make):

- **D1 — `main` reconciliation strategy** (already yours by prior agreement). New input:
  the cron's default-branch requirement means T0019.6 cannot fire until this happens —
  it is now sequenced work, not background hygiene.
- **D3 — The working-tree strays.** The uncommitted `MVP_Technical_Design.md` edit
  references **T0019.9 (coverage)** and **T0019.10 (detail visibility)** — IDs absent
  from `Tickets.md`. Adopt them (scope as real tickets — they map cleanly onto the
  `max_jobs`/interleave and `get_job_details` allowlist items), or revert the edit and
  let M21/D13 own those fixes under new numbers.
- **D8 — ToS republishing posture** for the public demo: accept-and-document /
  attribute+link (cheapest, closest to ToS §7) / gate the link / seek permission.
- **D9 — The release bar for DoD bullet 6.** After the v2 re-measure: what threshold (or
  qualitative standard) counts as "refuses reliably enough for v1.0"? Alternatively:
  accept measured imperfection, document it as a known limitation in the release notes,
  and ship — that is a legitimate fork-A outcome, but it is yours to take.
- **D10 — Does v1.0 require the nightly cron live?** The MVP spec explicitly accepts a
  static snapshot (§5), so a parked-cron v1.0 is spec-compliant; the live refresh is
  strictly better but couples the tag to D1/D2/D5/D6. Decide which side of the tag the
  cron activation sits on.
- **D11 — 60-day Actions auto-disable mitigation.** The keepalive action the ticket named
  is defunct (ToS-blocked). Options: monthly manual no-op / a from-scratch self-ping
  workflow / accept-and-calendar it.
- **D13 — Ingestion coverage fixes pre- or post-1.0** (`max_jobs` above the ~112 ceiling
  + round-robin interleave). Pre-1.0 widens the corpus the release demos; post-1.0 keeps
  M20–M22 lean. Interacts with D8 (more requests against the same host).

---

## 5. Cross-references

- `docs/MVP_Spec.md` §3/§4 — the bar and DoD this document audits against.
- `docs/Repo_Current_State.md` — branch topology, T0019 status, live-deploy record.
- `docs/Known_Issues.md` — every gap cited in §1 lives there with full context.
- `docs/Tickets.md` T0019 + Backlog — fixed sequencing; the unscheduled seeds M20 absorbs.
- `pre-deploy-refinement-plan.md` §6/§7/§8 — the deploy-hardening body and open decisions
  M20–M22 graduate.
- `ingestion-milestone-plan.md` §1/§5 — T0019 rationale and its unverified assumptions
  (several become M20 gates).
- `deployment-research-plan.md` §1a/§9/§10/§11 — keep-alive, monitoring ceiling, cost
  ceiling, robots/ToS record.
- `.github/workflows/ingestion.yml` (untracked) — the T0019.6 artifact; its header records
  the default-branch and defunct-keepalive facts §0 relies on.
