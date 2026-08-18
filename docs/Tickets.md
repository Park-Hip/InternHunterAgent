# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-18 against the active ticket plan and completion records.

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
| 24 | T0024 | Honesty Enforcement (obligation seam) | ✅ ⚠ | Complete 2026-08-18 (.1/.6 `73b058a` glossary + `prompt_version` + decision #10 · .2 PR #68 `detect_obligations` and the `MANDATORY CAVEATS` block · .3 PR #69 the caveat-relay contract, `v2`→`v3` · .4 PR #70 the frozen gate). .5 measured out and never built. The gate reads **11 PASS / 7 FAIL over 18 turns**: `HON-CURRENCY-1` 0/3 → 3/3, but `HON-CREATED-ON-1` and `HON-ABSENT-FIELD-1` fail 3/3 and no `v2` control was captured — residuals in [`Known_Issues.md`](Known_Issues.md) |
| 25 | T0025 | **Evaluation Instrument** | ✅ | .0-.10 complete 2026-08-13: registry, driver, viewer, execution accuracy, three-tier grader, replay CI gate · .7 closed partial (13 of 19 turns; 2 scenarios need a paid tier) |
| 26 | T0026 | Evaluation Workspace Hygiene | ✅ | Complete 2026-08-14 (.1 front door and one fixture-URL owner, .2 tests into `tests/evals/`, .3 grading rules into the registry). No verdict changed |
| 27 | T0027 | DeepSeek Provider Integration | ✅ | Complete 2026-08-15 (.1-.4), following the deferred T0015.6 procedure · the spike passed, the arm measured 29/29 scenarios in 5m20s for ~$0.04, and .4 flipped both profiles to DeepSeek (D-045) with pacing at 0 and no provider key required at boot · the Groq branch stays selectable |
| 28 | T0028 | Evaluation Documentation Ownership | ✅ | Complete 2026-08-14 (.1 Fact Ledger rows + `scenario-id` check, .2 dedupe the behavior spec, .3 seal + merge the instrument reports, .4 operating manual + stale-claim sweep). No verdict, rule, or threshold changed |
| 29 | T0029 | Evaluation Readability | ✅ | .1 complete 2026-08-15: the verdict, the run's identity, and telemetry rendered in the viewer. Spent no quota; changed no rule |
| 30 | T0030 | Evaluation Evidence Durability | ✅ | Complete 2026-08-17 (PR #61): .1 the `freeze` command, .2 the surviving T0025.7 capture frozen to `evals/replays/`, .3 **D-046** on telemetry · closed the `[HIGH · DECISION]` capture-preservation entry. The lost T0027.3 capture stays lost |
| 31 | T0031 | Parallel Agent Workflow | ✅ | Complete 2026-08-17 (.1 PR #53 registry, frozen registers, per-ticket entries · .2 PR #57 three registers generated from the entries · .3 PR #59 `Repo_Current_State.md` derived from the tree · .4 PR #62 `registry`, `scope`, and `frozen` checks in CI). Build status and the branch check stayed undone, both recorded |
| 32 | T0032 | Prompt Surface Pass | ✅ | Complete 2026-08-18 (.4 PR #63 selected the English prompt plus a Vietnamese-output rule for later promotion · .1 PR #65 finished decision #10 on the two Python sites · .3 PR #66 pinned the column list across the three prompt blocks · .2 PR #67 recorded the model-facing string surface behind an AST scan). Prompt wording in `config/prompts.yaml` is unchanged and no instruction was pruned, both by design |
| 34 | T0034 | Serving Memory Window Hardening | ✅ | Complete 2026-08-18 (.1 PR #73 reproduced message-count eviction at the sixth one-tool turn and the fourth sequential-two-tool turn; .2 PR #74 replaced the 20-message cap with a six-turn policy that retains complete turns). The multi-turn issue is resolved; the six-turn bound is the intentional token-growth trade-off |
| 35 | T0035 | Capture Lineage Stamp | ✅ | Complete 2026-08-18 (.1 PR #72): `prompt_version` is recorded in the capture manifest, required by `freeze_capture`, validated at replay `schema_version` 2, and drawn in the viewer's run header. The three committed replays were backfilled from the prompt version in the commit each capture ran at. An unlabelled capture cannot become a labelled-looking replay |
| 36 | T0036 | Scope Check Generated-Region Exemption | ✅ | Complete 2026-08-18 (.1 PR #64): `check_scope` gained the `only_generated_changed` exemption `check_frozen` has carried since T0031.2, so a ticket branch that adds a `docs/entries/` file can run the mandatory generator and still pass. Unblocked the three M32 PRs; the docs job being advisory rather than required is left open as a maintainer decision |
| 37 | T0037 | Ingestion Failure Bounding | ✅ | Complete 2026-08-18 (.1 PR #71): `api.max_elapsed_seconds` 600 bounds the whole VietnamWorks fetch, so a total-source outage returns from `fetch()` and reaches `main()`'s abort path instead of being cancelled at the workflow's 15-minute ceiling. Verified against a real non-routable blackhole: 21.8s against an unbounded worst case of 336s. `timeout-minutes` was in scope and deliberately left at 15 |
| 38 | T0038 | Grader Correctness | ✅ | Complete 2026-08-18: glossary and registry anchors replace bare textual rules, SQL accuracy has explicit comparison modes, honesty seam 3 remains visible when seam 2 fails, and the frozen v3 replay now grades 15 PASS / 3 FAIL without a new capture |
| — | Backlog | Custom domain | 📋 | deferred until after v1.0; cosmetic only |

> **Numbers are allocated in [`roadmap.yaml`](roadmap.yaml), not here.** This table is a reader's
> index of what the registry already decided. M29 and M30 merged on 2026-08-17 as PRs #51 and #52
> and each added its own row on the way in; T0031.1 adds only its own. That is the last row a
> ticket adds - once this milestone lands, the table is frozen and the integration step maintains
> it.

> ⚠ **M11:** milestone shipped, but the T0011.5 baseline-calibration run is still **blocked** on a
> maintainer executing it. Verified 2026-08-12: the Groq and Google keys are configured locally, so
> the constraint is the Groq daily token budget and operator time, not access. See
> [`Known_Issues.md`](Known_Issues.md).
>
> ⚠ **M20:** complete as a coder milestone; one **maintainer** action remains open — branch
> protection to *enforce* the CI gate. See
> [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md).
> The cron activation **closed on 2026-08-17**: four consecutive unattended `schedule` runs
> succeeded on 2026-08-14 through 08-17, which satisfies the runbook's §7 last row and clears the
> [`Decision_Log.md`](Decision_Log.md) D-038 requirement that a live schedule is an MVP capability.
> T0023 is therefore unblocked on the cron, and owes its DoD sweep and the terms posture.
>
> ⚠ **M24:** the milestone shipped its whole mechanism, but the gate it shipped against records a
> **measured honesty limitation rather than a clean pass** — 11 PASS / 7 FAIL over 18 turns, no
> `v2` control, and six of the 29 scenarios covered. T0023's DoD sweep owes decision **D9** those
> numbers, not a tick. The residuals are filed in [`Known_Issues.md`](Known_Issues.md) and the plan
> is archived in [`archive/Tickets_Archive.md`](archive/Tickets_Archive.md).
