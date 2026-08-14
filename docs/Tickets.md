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
| 27 | T0027 | DeepSeek Provider Integration | 📋 | Named 2026-08-14: spike, a second provider branch behind config, then a measured decision on the default |
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

Plans are archived in [`archive/Tickets_Archive.md`](archive/Tickets_Archive.md), outcomes are in
[Completion Reports](Completion_Reports.md), durable choices are D-040 through D-044 in the
[Decision Log](Decision_Log.md), and open risks stay in [Known Issues](Known_Issues.md).

**What still routes forward.** T0025.7 closed partial - 13 of 19 turns measured, with
`HLP-CONTEXT-1` and `HLP-COMPOUND-1` never captured - so the grader agreeing with all 13 human
labels is an assertion check, not an accuracy estimate. Full remeasurement is **T0024.4**;
thresholds and judge calibration belong to the release gate (D-A, D-B, D-C); the paid-tier decision
those two scenarios need is in [Known Issues](Known_Issues.md), and **T0027** is its other answer.

---

## T0026: Milestone 26 - Evaluation Workspace Hygiene - Complete 2026-08-14

Plans are archived in [`archive/Tickets_Archive.md`](archive/Tickets_Archive.md) and outcomes
are in [Completion Reports](Completion_Reports.md). `evals/` went from 33 flat entries to an
indexed directory: a README, one owner for the fixture database URL, the deterministic tests
under `tests/evals/`, and 24 scenarios carrying their grading rules as registry data.
**No verdict changed** - the regrade of the acceptance capture is byte-identical, and the
replay CI gate is what proves it.

**What still constrains `evals/`.** `evals/writeback.py` stays while
[`harness.py`](../evals/harness.py) imports it, and `test_judge.py` and `test_three_seams.py`
stay put because `deepeval test run` addresses them by path.

---

## T0027: Milestone 27 - DeepSeek Provider Integration - 📋 Named 2026-08-14, not scoped

The agent has run on one provider since M0, and Groq's free tier is now the binding constraint on
measurement: 8K TPM is what forces `eval.driver.turn_pacing_seconds: 75` and spreads a
29-scenario matrix over roughly three daily windows, which is why T0025.7 closed partial. DeepSeek
publishes no TPM or TPD ceiling - only account concurrency - at an estimated **$0.15 per full
87-turn matrix** on `deepseek-v4-flash`.

**The research is already written** and must be read before any block below is scoped:
[`research/deepseek-provider-evaluation.md`](../research/deepseek-provider-evaluation.md). It
records pricing and limits, the file-level change surface, and the three thinking-mode landmines
that make this more than a config edit: sampling parameters are silently ignored, `tool_choice` is
rejected with HTTP 400, and `reasoning_content` must be echoed back on every tool-carrying turn,
which `ChatDeepSeek` does not do, in an upstream issue closed as not planned. Disabling thinking
mitigates all three, and proving that is what .1 is for.

* **T0027.1** - a throwaway spike under `scripts/` running the five checks in the research §6:
  reachability, `extra_body` reaching the wire, a two-leg tool loop with no 400, determinism at
  `temperature: 0.0`, streaming with no reasoning chunks. Record results there. **Go/no-go.**
* **T0027.2** - a `deepseek` branch in [`provider.py`](../src/agents/runtime/provider.py) with its
  own per-profile config keys, `DEEPSEEK_API_KEY` plumbed through `src/core/config.py`,
  `.env.example`, and `render.yaml`, and the Groq tests mirrored. Groq stays `agent.provider`;
  this ticket only makes the alternative selectable. Blocked on .1.
* **T0027.3** - run the full 29-scenario matrix on DeepSeek against the fixture, compare per-turn
  against the recorded baseline, and only then decide the default and write the Decision Log entry
  beside D-017. A provider swap invalidates the baseline, so the delta is the deliverable, not the
  pass rate. Blocked on .2.

**Not release-blocking.** M23 and M24 come first, and this stays a provider *option* until .3
decides otherwise. **Out of scope for the whole milestone:** changing any scenario, threshold,
grader rule, or prompt; removing the Groq branch; moving the judge off the Gemini free tier.
