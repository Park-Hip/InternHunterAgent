# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-14 against the active ticket plan and completion records.

> **Eviction:** A ticket plan leaves when its completion report is recorded and its historical scope
> is moved to the ticket archive.

Ticket specs and delivery sequence for the MVP. Each entry below is the **plan** for one open
ticket (Objective / In Scope / Out of Scope). The milestone index keeps every milestone, open or
closed; plans for the closed ones live in
[`archive/Tickets_Archive.md`](archive/Tickets_Archive.md).
What a ticket *actually did* lives in [`Completion_Reports.md`](Completion_Reports.md), and the
current snapshot lives in [`Repo_Current_State.md`](Repo_Current_State.md).

**Legend:** ✅ Done · 🔨 In progress · ▶ Next · ⏸ Parallel / paused · 📋 Backlog

| M | Ticket | Milestone | Status | Goal |
|---|--------|-----------|:--:|------|
| 0–5 | T0000–05 | Foundation → Hardening | ✅ | FastAPI boot, request flow, ReAct runtime, Langfuse, tracing, hardening |
| 6 | T0006 | First Real SQL Tool | ✅ | Read-only `query_clean_jobs`; answer-only API |
| 7 | T0007 | Conversation Memory | ✅ | Postgres checkpointer, session→thread, trim cap |
| 8 | T0008 | System Prompt & Persona | ✅ | Resumi persona, honesty rules, schema → config |
| 9 | T0009 | Data Ingestion (VietnamWorks) | ✅ | `raw_jobs` + `clean_jobs`, idempotent loader |
| 10 | T0010 | Pre-deploy Hardening | ✅ | Typed errors, single-table allowlist, off-loop LLM |
| 11 | T0011 | Model Evaluation Harness | ✅ ⚠ | DeepEval judge, fixture DB, 3-seam metrics, writeback |
| 12 | T0012 | Hardening & Known-Issue Fixes | ✅ | qwen leak fix, metric unblock, `trace_url`, fallbacks |
| 13 | T0013 | Pre-Deploy Refinement | ✅ | `tech_stack` rebuild, 16-col v1 schema freeze |
| 14 | T0014 | Pre-Deploy Known-Issue Fixes | ✅ | Config-load robustness, register housekeeping |
| 15 | T0015 | Agent Behavior Spec & Scenario Matrix | ✅ | Closed 2026-08-12: spec, glossary, `prompt_version`, one graded matrix run; remainder absorbed by M24/M25 |
| 16 | T0016 | Security Posture | ✅ | CORS, rate limit, input cap, `/docs` decision |
| 17 | T0017 | Streaming Response Delivery | ✅ | `astream` + no-leak filter, SSE endpoint |
| 18 | T0018 | Clickable Demo (UI + go-live) | ✅ | .1–.4 done · **live: https://internhunteragent.onrender.com** |
| 19 | T0019 | Ingestion Deploy Readiness (live-DB) | ✅ | .1–.10 done; landed on `main` via PR #29 |
| 20 | T0020 | Reconciliation & Activation | ✅ ⚠ | `main` reconciled, Render pinned to `main`, CI gate live, cron runbook — **2 maintainer actions open** |
| 21 | T0021 | Serving-Path Hardening | ✅ | .1-.4 complete 2026-08-12; historical plans archived |
| 22 | T0022 | **Docs Hygiene & Documentation System** | ✅ | Phase 1 (.1-.9) complete 2026-08-10: lint gate, front door, Decision Log, research prune · Phase 2 (.10-.14) complete 2026-08-12: prune, archive collapse, register rebuild, restructure, enforcement |
| 23 | T0023 | v1.0 Release Cut | 📋 | DoD sweep, ToS posture, **live cron (D-038)**, tag — renumbered from T0022 on 2026-08-09 |
| 24 | T0024 | Honesty Enforcement (obligation seam) | 📋 | Carved out of M21 on 2026-08-12; designed, indexed, sequenced after T0023 |
| 25 | T0025 | **Evaluation Instrument** | ✅ | .0-.10 complete 2026-08-13: registry, driver, viewer, execution accuracy, three-tier grader, replay CI gate · .7 closed partial (13 of 19 turns; 2 scenarios need a paid tier) |
| 26 | T0026 | Evaluation Workspace Hygiene | ✅ | Complete 2026-08-14 (.1 front door and one fixture-URL owner, .2 tests into `tests/evals/`, .3 grading rules into the registry). No verdict changed |
| 28 | T0028 | Evaluation Documentation Ownership | 📋 | Scoped 2026-08-14: give eval facts an owner in the Fact Ledger, cut the duplicated scenario tables, seal the frozen records, promote an operating manual |
| — | Backlog | Custom domain | 📋 | deferred until after v1.0; cosmetic only |

> ⚠ **M11:** milestone shipped, but the T0011.5 baseline-calibration run is still **blocked** on a
> maintainer executing it. Verified 2026-08-12: the Groq and Google keys are configured locally, so
> the constraint is the Groq daily token budget and operator time, not access. See
> [`Known_Issues.md`](Known_Issues.md).
>
> ⚠ **M20:** complete as a coder milestone; two **maintainer** actions remain open — branch
> protection to *enforce* the CI gate, and the gated cron activation. See
> [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md).
> The cron activation now **blocks T0023**: [`Decision_Log.md`](Decision_Log.md) D-038 makes a live
> schedule a required MVP capability, so its gates — including the terms posture — are
> release-blocking rather than optional hardening.

---

## T0024: Milestone 24 - Honesty Enforcement (obligation seam) — 📋 Named, indexed, not scoped
**Carved out of M21 on 2026-08-12.** The model-honesty half of the former *Serving-Path Hardening &
Honesty Baseline* milestone, separated because its blockers are unrelated to the serving path: it
needs the frozen `behavior_glossary` landed in `config/prompts.yaml`, a detection mechanism, and
repeated Groq daily-quota windows for its measurement gate.

**The design is already written** and must be read before any block below is scoped:
[`research/honesty-enforcement-design.md`](../research/honesty-enforcement-design.md). It measures
the 2026-07-14 scenario matrix (C-category 0/7), rejects prompt few-shots as the primary locus, and
adopts deterministic hedge-obligation detection over the validated SQL and result set — the
mechanism the passing truncation notice already proves in this repo. Its §8 proposes five blocks
under the milestone number **T0020**, which reconciliation took; they are re-indexed here and
carry no other change:

* **T0024.1** — land `behavior_glossary` and `prompt_version` on the deploy lineage from
  `archive/t0015.2-behavior-glossary`, with a loader and a token-coverage test. **As a loaded
  artifact, not as system-prompt text** — see
  [`research/prompt-refinement-methods.md`](../research/prompt-refinement-methods.md), which finds
  18 rules sits past the ~8–10 instruction knee and splits data-driven hedges (injected when the
  obligation fires) from request-driven refusals (the five that stay in the prompt). No blockers.
* **T0024.2** — `detect_obligations(sql, table)` plus the revived `QueryToolResult` seam, rendered
  as a delimited caveat block in both tools' output. Blocked on .1.
* **T0024.3** — the caveat-relay rule in the system prompt and a `prompt_version` bump. Blocked
  on .2.
* **T0024.4** — re-run the 29-scenario matrix against the fixture database as the ship gate, and
  record the per-rule deltas. Blocked on .3 and one Groq daily window.
* **T0024.5** — verify-and-append enforcement middleware, built **only** if .4 shows the model drops
  explicit caveats.
* **T0024.6** — apply settled decision **#10** to `config/prompts.yaml`. The persona line still
  opens "helps users explore internship and job postings", and the T0015.5 edit that was to correct
  it never landed. T0025.2 measured the cost in
  [`evals/v1_error_analysis.md`](../evals/v1_error_analysis.md): six turns of
  `INTERNSHIP_SCOPE_NARROWING` and `INTERNSHIP_PERSONA_WORDING` across HON-ZERO-RESULTS-1,
  HON-FREE-TEXT-1, HLP-LOCATION-SYNONYM-1, and HLP-REFERENT-2. Decide
  explicitly whether the sibling decline line inherits the fix — decision #10 names the persona line
  alone, while the measured narrowing implicates both. **Class 3 wording, not obligation-seam
  work**, so it neither blocks nor is blocked by .2-.5. Blocked on .1 for `prompt_version`, which
  exists nowhere today; **run immediately after it**, and before T0025.3's first capture run, so no
  two runs straddle an unversioned prompt change.

**Sequenced after T0023, except .1 and .6**, which are pulled ahead: T0025.6 needs .1's glossary
tokens, and .6 must land before T0025.3's first capture run. D-021 gates `is_active` exposure
behind this work, and the release bar
for the honesty Definition-of-Done bullet is decision **D9** in the readiness plan — answered during
T0023's sweep, not here. A v1.0 tag that records a measured honesty limitation is a legitimate
outcome; this milestone is how the limitation gets closed afterward.

## T0025: Milestone 25 - Evaluation Instrument - Complete 2026-08-13

The ten ticket plans are archived in
[`archive/Tickets_Archive.md`](archive/Tickets_Archive.md); their outcomes are in
[Completion Reports](Completion_Reports.md).

**What the milestone delivered.** A frozen Alembic-built fixture, a 29-scenario registry that owns
probe flags, reference SQL, and tool expectations, an in-process driver with manifests and
checkpoint/resume, a local trace viewer, execution accuracy by executing generated and reference
SQL against the fixture, and a deterministic three-tier grader with four outcomes. CI now replays
committed three-seam evidence and grades it with no model, judge, or outbound call.

**Where it stopped, deliberately.** T0025.7 closed partial: the free tier's admission ceiling left
13 of 19 attempted turns measured, and `HLP-CONTEXT-1` and `HLP-COMPOUND-1` were never captured.
The grader agrees with all 13 human labels, but 13 turns is an assertion check, not a
production-wide accuracy estimate.

**Who owns what next.**

| Concern | Owner |
|---|---|
| Fixing the behaviors the instrument found | **M24 - Honesty Enforcement** |
| Full 29-scenario remeasurement on the accepted instrument | **T0024.4**, once the tier decision lands |
| Ship or no-ship thresholds, and the release policy behind them | **The release gate (D-A, D-B)** |
| Judge calibration and fidelity | **The release gate (D-C)** |
| The paid-tier decision the last two scenarios need | [Known Issues](Known_Issues.md) |

Open evaluation risks stay in [Known Issues](Known_Issues.md); durable choices are D-040 through
D-044 in the [Decision Log](Decision_Log.md).

---

## T0026: Milestone 26 - Evaluation Workspace Hygiene - Complete 2026-08-14

The three ticket plans are archived in
[`archive/Tickets_Archive.md`](archive/Tickets_Archive.md); their outcomes are in
[Completion Reports](Completion_Reports.md).

**What the milestone delivered.** A front door (`evals/README.md`) and one owner for the
fixture-database URL, the eight test modules moved under `tests/evals/`, and the grader's rule
table moved into `evals/scenarios_v1.yaml` so a grading rule now sits beside its expectation.
No verdict, threshold, or scenario expectation changed.

---

## T0028: Milestone 28 - Evaluation Documentation Ownership - 📋 Scoped 2026-08-14

The evaluation documentation passes all ten checks in `scripts/docs_lint.py`, so hygiene is not the
failure here. Ownership is.

Measured on 2026-08-14: the 29-scenario matrix is hand-written in **five** files - the registry
`evals/scenarios_v1.yaml`, `docs/Agent_Behavior_Spec.md` §4a-4c, `evals/v1_scenario_matrix.md`,
`evals/grader_audit.md`, and `evals/v1_error_analysis.md`.
Four of those five also carry each scenario's input and expected behavior.
`HLP-COUNT-1`'s expected sentence is character-identical, modulo backticks and the arrow glyph,
across the registry, the behavior spec, and the scenario matrix.

No lint check compares one file against another, so drift between those copies would be silent.
That matters more here than elsewhere, because the behavior spec is what the grader is calibrated
against, and D-041 already names the registry the single source of truth for scenario expectations.
This milestone is the repo's own doctrine applied to its own evaluation docs -
[`research/docs-hygiene-and-system-plan.md`](../research/docs-hygiene-and-system-plan.md) §5.3:
"if you are about to write a fact into a doc that does not own it, write a link instead."

A second gap sits beside the first. The Fact Ledger in [`README.md`](README.md) assigns an owner to
fourteen fact classes and **none of them is an evaluation fact**, which is why the duplication was
never caught by the system built to catch it.

**This milestone changes no verdict and no rule.** No scenario expectation, grading rule,
threshold, or committed replay artifact is edited. It moves facts to their owner, seals the frozen
records, and teaches the linter to check what it currently cannot.

**Not release-blocking.** T0023 does not depend on it. It is sequenced before T0023 by maintainer
choice on 2026-08-14 and can be preempted at any block boundary.

**Out of scope for the whole milestone**
* Changing any scenario, expectation, grading rule, threshold, or replay artifact.
* Re-running the evaluation, or producing any new measurement.
* Building a documentation system separate from the M22 one - considered and rejected 2026-08-14.
* M24 honesty work, and the paid-tier decision the last two uncaptured scenarios need.

### T0028.1 - Give evaluation facts an owner, and a check that enforces it

**Objective.** Add the missing evaluation rows to the Fact Ledger in [`README.md`](README.md), and
add a `scripts/docs_lint.py` check that every scenario ID named in tracked Markdown exists in
`evals/scenarios_v1.yaml`.

**In Scope**
* Three Fact Ledger rows: scenario definitions and expectations (owner `evals/scenarios_v1.yaml`),
  behavior requirements and probe protocol (owner `docs/Agent_Behavior_Spec.md`), and the graded
  outcomes of a dated run (owner that dated record under `evals/`).
* A new check in `scripts/docs_lint.py` that scans tracked Markdown for `(HLP|HON|SAF)-[A-Z0-9-]+`
  and fails on any ID absent from the registry, using the same `lint-allow-*` escape-hatch style as
  the existing checks.
* Test coverage for the new check, matching how the existing checks are covered.

**Out of Scope**
* Editing the duplicated tables themselves - that is .2 and .3.
* Any check that compares expectation *text* across files. ID existence only.

**Manual verification**
1. `uv run python scripts/docs_lint.py` exits 0.
2. Temporarily add `HLP-NOT-A-SCENARIO-9` to a tracked Markdown file and re-run the linter; it
   fails, naming both the file and the ID. Revert the edit.
3. `docs/README.md` shows the three new Fact Ledger rows and stays under its cap.

**Blockers.** None.

### T0028.2 - Cut the duplicated scenario table out of the behavior spec

**Objective.** Reduce `docs/Agent_Behavior_Spec.md` §4a-4c to what that spec owns - scenario ID,
the requirement under test, and the probe protocol - and link to `evals/scenarios_v1.yaml` for
inputs and expected outputs.

**Notes.** The spec's "frozen 2026-07-11" header protects its requirements from drifting
mid-measurement; it does not protect the duplicated per-scenario expectations. The maintainer
confirmed on 2026-08-14 that the file is editable on those terms. Roughly 49 lines are in range.

**In Scope**
* Rewrite §4a-4c down to the owned columns plus a link to the registry.
* Keep every scenario ID present, so the .1 check and every inbound reference still resolve.
* Refresh the verification stamp per [`Docs_Conventions.md`](Docs_Conventions.md).

**Out of Scope**
* §1-§3 and §5 onward.
* Changing any requirement text, probe flag, or scenario ID.

**Manual verification**
1. Every ID in `evals/scenarios_v1.yaml` still appears in §4a-4c.
2. `uv run python scripts/docs_lint.py` exits 0.
3. Searching the tree for `COUNT(*) via query_clean_jobs` returns the registry and the dated
   records only, not the behavior spec.

**Blockers.** .1, for the check that proves no ID was dropped.

### T0028.3 - Seal the frozen records, and merge the two instrument reports

**Objective.** Move the two dated snapshots out of the living document set, and fold
`evals/holdout_report.md` into `evals/grader_audit.md` as a single instrument report.

**Notes.** `evals/v1_scenario_matrix.md` and `evals/v1_error_analysis.md` legitimately restate the
matrix, because a snapshot has to carry its subject. The defect is that they sit beside living docs
with nothing marking them sealed. `is_archive()` in `scripts/docs_lint.py` already exempts
`docs/archive/` and `research/archive/`.

**In Scope**
* Create `evals/archive/`, move both dated records into it, and extend `is_archive()` to cover it.
* Merge `holdout_report.md` into `grader_audit.md`, renamed `evals/Instrument_Report.md`. <!-- lint-allow-link-path -->
* Update the caps rows in [`README.md`](README.md) and every inbound link.

**Out of Scope**
* Editing the content of either dated record.
* Re-deriving any number in the merged report.

**Manual verification**
1. `uv run python scripts/docs_lint.py` exits 0.
2. No Markdown file in the tree links to a moved or renamed path.
3. `docs/README.md` lists `evals/Instrument_Report.md` and drops the two merged rows. <!-- lint-allow-link-path -->

**Blockers.** None. Independent of .1 and .2.

### T0028.4 - Promote an operating manual, and sweep the stale claims

**Objective.** Give `evals/` the operating manual the tracked tree does not have, and correct the
two documented claims that measurement shows are wrong.

**Notes.** A manual-grade explainer already exists at `.lavish/how-the-evaluation-works.html`,
written 2026-08-13, but `.lavish/` is gitignored, so no reader of the repository can find it.
Every claim in it must be re-verified against the tree before promotion. It is a draft, not a
source.

**In Scope**
* A prose operating manual under `evals/`, registered with a cap in [`README.md`](README.md): why
  the instrument exists, the three seams, the three scenario classes, the run-to-artifact path, the
  three grading tiers and four outcomes, `--resume` and `PARTIAL_QUOTA`, and the stated limits.
* Correct [`Offline_Pipelines_Design.md`](Offline_Pipelines_Design.md) §8.6-8.7, which says the
  replay gate is "not wired into CI" and "Deferred" (T0025.9 shipped it, and `.github/workflows/`
  runs it) and pins `llama-3.3-70b-versatile` (settings pin `qwen/qwen3.6-27b`).
* The two M26 follow-ups: the stale `test_judge_scaffold.py` reference, and the
  `Completion_Reports.md` lint exemption.

**Out of Scope**
* Writing the missing sanitizer that produces a committable replay artifact. Recorded as a
  follow-up, not built here.
* Any new measurement.

**Manual verification**
1. A reader who has never run the evaluation can follow the manual end to end and reach a graded
   artifact.
2. Every command quoted in the manual runs as written.
3. `uv run python scripts/docs_lint.py` exits 0.
4. `docs/Offline_Pipelines_Design.md` §8.6-8.7 names the shipped CI gate and the configured model.

**Blockers.** None. Independent of .1-.3.
