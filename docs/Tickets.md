# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-13 against the active ticket plan and completion records.

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
| 26 | T0026 | Evaluation Workspace Hygiene | 🔨 | Scoped 2026-08-14; .1 complete (front door, one fixture-URL owner, docs registered); .2 tests into `tests/`, .3 grader rule table into the registry remain — not release-blocking |
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

## T0026: Milestone 26 - Evaluation Workspace Hygiene - 📋 Scoped 2026-08-14

M25 built the instrument ticket by ticket, and `evals/` accumulated the shape of that sequence
rather than a designed one. Measured on 2026-08-14: **33 flat entries**, of which **8 are test
modules** and **4 are Markdown records that no index owns**, plus **no `README.md`** explaining
what any of it is or which commands cost quota.

This milestone is hygiene only. **It changes no verdict.** Every ticket below must leave the
committed replay and the 13-turn regrade producing byte-identical outcomes, and the CI gate is what
proves it.

> **Not release-blocking.** M23 and M24 come first. Pull this in when `evals/` gets in the way,
> or run T0026.1 alone as a cheap standalone win.

**Out of scope for the whole milestone:** any change to a scenario, a threshold, a grader verdict,
a prompt, or the agent; new metrics; judge work; deleting `evals/writeback.py`, which
[`harness.py`](../evals/harness.py) line 34 still imports.

### T0026.1: A front door for `evals/`, and one owner for the fixture URL
> **Complete 2026-08-14.** `evals/README.md` lands, `fixture_database_url()` is the single owner,
> and five `evals/` documents are registered in the map.
> The dedupe went the opposite way from what the plan assumed: the driver's copy was load-bearing,
> not redundant. Resolving through `src.core.config.settings` freezes `Settings()` against the
> serving database before the driver can bind `DATABASE_URL`, so a capture would have run the agent
> against production data. The shared function reads the YAML directly, and a regression test that
> was proven to fail on the hazard now pins it.

**Objective:** Make the directory legible to someone who did not build it, and stop two modules
disagreeing about how to find the fixture database.

**In Scope:**
* Add a README at evals/README.md covering: what each module does, the order the pipeline runs in
  (registry → driver → execution accuracy → grader → replay), which commands spend provider quota
  and which do not, and where run artifacts land. Link it from [`docs/README.md`](README.md).
* Collapse the two `_fixture_database_url` implementations into one exported function owned by
  [`evals/fixtures/loader.py`](../evals/fixtures/loader.py). `driver.py` line 71 re-reads
  `config/settings.yaml` itself and raises `RuntimeError`; `loader.py` line 34 raises `ValueError`;
  `execution_accuracy.py` line 14 imports the private name across a module boundary. Pick one
  public function and one error type, and have all three call sites use it.
* Register the four unowned records - `grader_audit.md`, `v1_scenario_matrix.md`,
  `v1_error_analysis.md`, `holdout_report.md` - in the [documentation map](README.md) caps table
  with an owner, tier, cap, and reader. Set each cap from its measured length, per the map's rule.

**Out of Scope:**
* Moving or renaming any Python module. Rewriting the content of the four records.

**Notes for the implementer:**
* `driver.py` calls `_bind_fixture_environment()` at import time, which is why lines 113-114 carry
  `# noqa: E402`. `src/core/config.py` line 122 exposes `settings` as a lazy proxy, so importing
  `evals.fixtures.loader` before the bind is safe - but verify that the driver still binds the
  environment before `evals.harness` is imported, because `harness` pulls in the agent factory.

**Manual verification:**
1. `uv run python -m evals.fixtures.loader` then `uv run python -m evals.replay` still pass.
2. `uv run python -m evals.driver --resume --output evals/runs/run.json` starts and binds the
   fixture database, with no `DATABASE_URL` leakage to the serving database.
3. `uv run python scripts/docs_lint.py` passes, including the caps check on the four new entries.
4. A reader who has never opened the directory can name, from the new README alone, which two
   commands spend Groq quota.

**Blockers:** none. Spends no provider or judge quota.

### T0026.2: Move the deterministic eval tests under `tests/`
**Objective:** Leave `evals/` holding the instrument, not the instrument plus its test suite.
Over half its entries are currently tests.

**In Scope:**
* Move the six deterministic modules - `test_driver.py`, `test_execution_accuracy.py`,
  `test_grader.py`, `test_replay.py`, `test_scenarios.py`, `test_viewer.py` - and the two under
  `evals/fixtures/` into `tests/evals/`, preserving their contents.
* **Keep `test_judge.py` and `test_three_seams.py` where they are.** They are the only
  `eval`-marked modules, and `deepeval test run evals/test_three_seams.py` addresses them by path.
* Narrow [`evals/conftest.py`](../evals/conftest.py) so its `DATABASE_URL` redirect applies to the
  eval tests that need it rather than to every pytest collection. This closes the standing
  `[LOW · OPEN]` entry in [Known Issues](Known_Issues.md); move it to
  [Resolved Issues](Resolved_Issues.md) with the evidence.

**Out of Scope:**
* Rewriting any assertion. Changing what the suite covers. Touching the two `eval`-marked modules.

**Manual verification:**
1. `uv run pytest -q` reports the same pass count as before the move, with the same single
   environmental skip.
2. `uv run pytest -q tests/` alone now collects the moved modules.
3. `uv run pytest -m eval --collect-only` still finds both `eval`-marked modules at their old paths.
4. Run a non-eval test in isolation and confirm collection leaves `DATABASE_URL` untouched.

**Blockers:** T0026.1, so the README describes the final layout. Spends no quota.

### T0026.3: Move the grader's rule table into the scenario registry
**Objective:** Finish the migration T0025.9 started. `expected_tools` now comes from the registry;
the rest of each scenario's expectations still do not.

[`grader.py::_rule_for`](../evals/grader.py) is 71 lines holding **24 hardcoded scenario ids** and
roughly **99 literal match strings** - answer counts, required phrasings, forbidden phrasings, and
one bespoke structural flag. That is behavior data living in code, which is the same defect that
made the grader fail `HON-SQL-DESCRIBE-1` for three captured turns, and it contradicts the
project rule that parameters belong in configuration.

**In Scope:**
* Move `expected_answer_count`, the `TextRule` contents, and `forbid_single_salary_winner` into
  per-scenario fields in [`scenarios_v1.yaml`](../evals/scenarios_v1.yaml), alongside
  `expected_tools`. Extend the loader's validation to reject an unknown or malformed rule field the
  way it already rejects an unknown tool name.
* Reduce `_rule_for` to a registry lookup. Keep `ScenarioRule`, the three tiers, and the four
  outcomes exactly as they are.
* Keep the six-scenario holdout meaningful: its assertions must still be authored independently of
  the registry, or the contract test becomes circular. State in `holdout.py` how that is preserved.

**Out of Scope:**
* Changing any rule's content, adding a rule, relaxing a rule, or touching the judge tier.
* Re-authoring scenarios.

**The invariant, and how it is proven:** the regrade of
`evals/runs/t0025.7-acceptance.json` must stay 7 `PASS` / 6 `FAIL` / 2 `INFRA` with per-turn
statuses unchanged, and `uv run python -m evals.replay` must pass unmodified. A verdict that moves
means the migration changed a rule, which is out of scope - revert rather than update the expected
outcome.

**Manual verification:**
1. Diff the regrade output against the pre-change run; it must be identical turn for turn.
2. `uv run python -m evals.replay` passes with the committed artifact untouched.
3. Break one migrated rule in the YAML, confirm the grader disagrees with its recorded human label,
   then restore it.
4. `uv run pytest -q`, Ruff, mypy, and documentation lint pass.

**Blockers:** T0026.1. Independent of T0026.2. Spends no provider or judge quota.
