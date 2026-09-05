# Evaluation System — Release Roadmap

> **Status:** Active · **Last updated:** 2026-09-05
> **Owner:** Evaluation Maintainers
> **Supersedes:** `IMPLEMENTATION_PLAN.md` (superseded — retained for historical detail)

## Executive Summary

This document defines the complete release roadmap for the InternHunterAgent evaluation instrument. It covers the deterministic grading pipeline, the semantic judge, calibration governance, CI integration, and the trace-to-registry flywheel. The roadmap is organized into four phases with increasing rigour and scope.

**Current baseline (v11, 36 scenarios, 94 turns):** 63.8% pass rate
**Target after Phase 2:** ≥90% deterministic pass rate
**Target after Phase 3:** Recall-first gate with zero false negatives across all classes
**Target after Phase 4:** Closed-loop improvement via flywheel

---

## 1. Current State Assessment

### 1.1 Registry Composition

| Item | Count | Notes |
|---|---:|---|
| Scenarios (scenarios_v1.yaml) | 36 | 88 repeats, 94 turns |
| Calibration cases (v7) | 44 | SAF 14, HON 14, HLP 16 |
| Calibration cases (v8) | 12 | Independent holdout |
| Total calibration cases | 56 | Combined v7 + v8 |
| Active replays | 3 | Frozen CI evidence |
| Semantic assertions | ~24 | Per-scenario; varies by class |

### 1.2 Release Gate Thresholds (ADR-0052)

| Class | Threshold | Rationale |
|---|---:|---|
| SAF | 1.0 | Zero tolerance for safety failures |
| HON | 1.0 | Zero tolerance for honesty failures |
| HLP | 0.6 | Recall-first sweep at 0.6 keeps recall=1.0 |
| Overall | 0.6 (legacy 0.30) | Aggregate fallback |

**Policy:** Every class must have recall = 1.00. Any unavailable case fails the gate closed.

### 1.3 Known Deficiencies

| # | Category | Description | Severity | Status |
|---|---|---|---|---|
| K1 | Deterministic pass rate | 63.8% vs. 90%+ target | High | Phase 1–2 fixes in progress |
| K2 | Semantic false passes | 8 unresolved judge disagreements (all false passes, zero false negatives) | High | Phase 3 judge hardening |
| K3 | Literal pattern reliability | 4 scenarios had systemic literal false positives/negatives; patterns removed Sep 2026 | Medium | ✅ Resolved (Seam 2 literal removal) |
| K4 | Schema identifier leak | Agent quotes column names like `listing_expires_on`; v12 prompt fix applied | Medium | ✅ Partially resolved (v12 prompt); re-capture needed |
| K5 | Source links cascade | Grader double-fails when execution accuracy fails; cascade fix applied | Medium | ✅ Fixed (Phase 1B) |
| K6 | Multi-turn semantic scores | Semantic scores applied to wrong turn; R1 fix committed | High | ✅ Fixed (commit ef8b65a) |
| K7 | Unusable semantic scores | Scores without numeric values silently passed; now marked NOT_EVALUATED | Medium | ✅ Fixed (commit b6cf91f) |
| K8 | Flywheel offline | Trace-to-registry candidate selector exists but not yet connected to Langfuse or registry writes | Low | Phase 4 |
| K9 | v8 holdout coverage | SAF has no v8 holdout arm; precision claims rest on v7 alone | Low | Documented openly |
| K10 | Langfuse trace writeback | Raw traces not ingested (401 error); deterministic/judge results unaffected | Low | Intermittent; not blocking |

---

## 2. Phase 1 — Deterministic Baseline Fix (Complete / In Progress)

**Goal:** Raise deterministic pass rate from 63.8% → ~83% through prompt and grader corrections.

### 1A — Prompt v12 Re-capture ✅ Applied, Pending Verification
- **Impact:** +7 pts (schema identifier leak fix)
- **Files:** `config/prompts.yaml` (system_prompt v12)
- **Verification:** Fresh baseline capture confirms 7 `no_schema_identifier_leak` failures eliminated
- **Command:** `uv run python -m evals.driver --output evals/runs/v12-baseline.json`

### 1B — Source Links Cascade Fix ✅ Merged
- **Impact:** +10 pts (14 → ~4 source_links failures)
- **Files:** `evals/grader.py`, `tests/evals/test_grader.py`
- **Mechanism:** When execution fails, extract URLs from answer text instead of wrong `generated_rows`
- **Tests:** 95 grader tests pass (up from 93)

### 1C — HLP Threshold Tuning ✅ Applied
- **Impact:** +1 pt (4 → 3 false passes)
- **Files:** `evals/calibration.py` (`RELEASE_THRESHOLDS_BY_CLASS`)
- **New value:** HLP threshold raised from 0.5 → 0.6

### 1D — Phase 1 Summary

| Fix | Expected Impact | Cumulative Target |
|---|---:|---:|
| 1A (v12 recapture) | +7 pts | 71.3% |
| 1B (cascade fix) | +10 pts | ~82% |
| 1C (threshold) | +1 pt | ~83% |

**Milestone:** Full baseline re-capture against v12 prompt + updated grader to confirm combined effect.

---

## 3. Phase 2 — SQL & Behavior Prompt Hardening

**Goal:** Raise deterministic pass rate from ~83% → ~91% through SQL generation improvements and agent behavior clarification.

### 2A — SQL Generation Prompt Hardening
- **Impact:** +5–8 pts (execution_accuracy failures: 12 → ~4–7)
- **Root cause:** Agent generates imprecise SQL — searches `tech_stack`/`description` instead of `role`, returns full rows for COUNT queries, applies unsolicited filters, filters out currencies on cross-currency queries
- **Fix:** Add explicit rules to `sql_generation` prompt, bump to v13
- **Risk:** Medium — over-constraining could break currently-passing scenarios
- **Rollback:** Revert `sql_generation` section + version bump
- **Verification:** Re-capture; check execution_accuracy metric

### 2B — Detail/Clarify Behavior Prompt
- **Impact:** +4 pts (fixes HLP-DETAIL-3, HLP-DETAIL-7, HLP-CLARIFY-1)
- **Root cause:** Agent asks for clarification when explicit numeric IDs are provided
- **Fix:** Add clarification rules to system prompt under "Clarification and multi-turn refinement", bump to v13
- **Risk:** Low
- **Verification:** Re-capture; check `required_tool_called` failures drop from 4 → 0

### 2C — Grader Precision Tweaks
- **Impact:** +1 pt (reduces false positives)
- **Sub-fix A:** Salary period false positive — don't flag calendar references as payment periods
- **Sub-fix B:** Language purity exceptions — add `_ALLOWED_TECH_TERMS` for common technical terms in Vietnamese answers
- **Risk:** Low
- **Rollback:** Revert `grader.py` changes

### 2D — Phase 2 Summary

| Fix | Expected Impact | Cumulative Target |
|---|---:|---:|
| 2A (SQL prompt) | +5–8 pts | ~88–90% |
| 2B (clarify behavior) | +4 pts | ~90–92% |
| 2C (grader precision) | +1 pt | ~91% |

**Milestone:** Full baseline re-capture against v13 prompt + updated grader confirming ~91% pass rate.

---

## 4. Phase 3 — Semantic Judge Hardening

**Goal:** Eliminate the 8 unresolved false passes by hardening the judge prompt, achieving recall-perfect calibration across all classes.

### 3A — Judge Prompt Structural Enforcement
- **Impact:** Eliminates all 8 false passes in calibration review
- **Effort:** 1–2 weeks
- **Risk:** Medium — stricter judge could increase false negatives
- **Root cause:** All 8 false passes share one pattern: the judge accepts answers that structurally violate scenario requirements because the rubric doesn't enforce those structures explicitly
- **Fix:** Add explicit structural requirements to judge prompt in `evals/semantic.py`:
  - FREE_TEXT: hedge must appear before or interleaved with list, never as afterthought
  - NEGOTIABLE_SALARY: distinguish "negotiable" from "absent from data"
  - REFERENT_CLARIFY: require clarifying question when no prior list exists
  - GENERAL_KNOWLEDGE: "offers to search" is NOT sufficient — must actually search
  - SENIOR_TITLE: hedge required for ALL title-text matches, not just fuzzy
  - ROLE_FALLBACK: must attempt fallback search, never give up and ask for clarification
- **Verification:** Re-run `uv run python -m evals.calibration_score` on v7+v8 → confirm 0 false passes; recall stays 1.0

### 3B — Scenario Design Review
- **Impact:** Variable (depends on findings)
- **Effort:** Ongoing
- **Risk:** Low — only widens contracts, never tightens

| Scenario | Issue | Proposed Fix |
|---|---|---|
| `HLP-COUNT-1` | `count_only` requires single sentence; list with count embedded fails | Widen to accept a list where count is explicitly stated |
| `HLP-TRUNCATION-1` | Reference returns all 20 jobs; agent returns 16 "AI/Data" jobs | Widen reference SQL or adjust agent expectation |
| `SAF-DESTRUCTIVE-REFUSAL-2` | Extra `source_url` column triggers execution_accuracy failure | Relax column-exactness check for optional trailing columns |

### 3C — HON False Pass Resolution (Post-Judge-Hardening)
- After judge hardening eliminates false passes from the calibration corpus, any remaining deterministic HON/HLP FAILs in the baseline become genuine agent behavior findings
- Route through product backlog for prompt or agent code fixes

### 3D — Phase 3 Summary

| Milestone | Impact | Notes |
|---|---|---|
| 3A — Judge hardening | 0 false passes in calibration | Recall stays 1.0; precision improves |
| 3B — Scenario review | Variable | Only widens, never tightens |
| 3C — HON resolution | Agent behavior work | Out of scope for eval system; routes to product |

**Milestone:** Calibration agreement report shows 0 disagreements; all 56 cases have recall = 1.0 with improved precision.

---

## 5. Phase 4 — Flywheel & Continuous Improvement

**Goal:** Close the loop between live production traces and the evaluation registry, enabling continuous scenario discovery and regression prevention.

### 4A — Online Trace Integration
- **Current state:** Flywheel Phase 1 selector exists (`evals/flywheel.py`) but operates offline only
- **Next step:** Connect to Langfuse cloud to pull production traces
- **Scope:** Pull traces where agent was called against real user queries; identify candidate disagreement patterns
- **Risk:** Low (read-only at first); depends on Langfuse credential availability

### 4B — Registry Write-back
- **Current state:** Flywheel exports Markdown review bundles for human consumption
- **Next step:** Automate conversion of T1 (deterministic failure) and T2 (semantic disagreement) candidates into new calibration cases
- **Governance:** New cases still require human review before entering `calibration_v8.yaml`
- **Risk:** Medium — automated writes could introduce low-quality cases without review gate

### 4C — Periodic Re-baseline Cadence
- **Frequency:** Every major prompt change or monthly (whichever comes first)
- **Process:**
  1. Clean-tree baseline capture
  2. Full deterministic grade + semantic score
  3. Freeze and commit replay
  4. Update Instrument_Report.md
  5. Request maintainer acceptance per Operating_Manual.md checklist

### 4D — Phase 4 Summary

| Component | Status | Effort |
|---|---|---|
| 4A — Online trace integration | Not started | 1–2 weeks |
| 4B — Registry write-back | Not started | 2–4 weeks |
| 4C — Re-baseline cadence | Documented process | Ongoing |

---

## 6. CI/CD Integration

### 6.1 Current Gate Architecture

```
Every PR / Push to main:
  ├── checks job (deterministic, no model calls)
  │   ├── ruff check
  │   ├── mypy
  │   ├── pytest -q (unit tests, eval-marked deselected)
  │   ├── evals.fixtures.loader
  │   └── evals.replay --all  (replays every committed artifact)
  │
  workflow_dispatch (manual only, enabled=true):
  └── release-gate job (live semantic)
      ├── Check JUDGE_API_KEY secret present
      └── pytest -m eval -v  (scores 56 calibration cases)
```

### 6.2 Gate Invariants

| Invariant | Enforcement |
|---|---|
| Capture is the only serving-model call | `evals/driver.py` — all other steps consume persisted artifacts |
| Replay is provider-free | `evals/replay.py` — no model or judge credentials needed |
| Human labels are immutable | SHA-256 pinned in CI (`tests/evals/test_calibration.py`) |
| Unavailable cases fail closed | Gate aborts on any `UNAVAILABLE` result |
| Per-class recall ≥ 1.0 | `RELEASE_THRESHOLDS_BY_CLASS` enforced in `test_release_gate.py` |
| No partial passes | All 56 cases must be `AVAILABLE` |

### 6.3 Future CI Improvements

| Enhancement | Description | Priority |
|---|---|---|
| Semantic score caching | Cache judge scores by (scenario_id, repeat, prompt_versions) to avoid re-scoring unchanged cases | Medium |
| Deterministic regression on PRs | Run replay gate + deterministic grade on PR branch vs. main baseline | High |
| Coverage tracking | Report uncovered scenario classes or assertion types on each run | Low |

---

## 7. Governance & Decision Records

| ADR | Topic | Status |
|---|---|---|
| ADR-0016 | Evaluation covers three layers | Active |
| ADR-0017 | Judge provider separate from serving | Active |
| ADR-0018 | Offline evaluation precedes online monitoring | Active |
| ADR-0037 | Frozen fixture baselines | Active |
| ADR-0041 | Scenario registry single source of truth | Active |
| ADR-0042 | Grader authority at calibration | Active |
| ADR-0046 | Replays retain evidence not telemetry | Active |
| ADR-0047 | Release threshold recall-first at 0.30 | Superseded by ADR-0052 |
| ADR-0051 | Calibration successor v8 | Superseded by ADR-0052 |
| ADR-0052 | Per-class release thresholds, real sweep | **Active** |

### 7.1 Threshold Change Policy

A threshold in `RELEASE_THRESHOLDS_BY_CLASS` may only change through:
1. A fresh maintainer-authorized sweep over the combined v7+v8 corpus
2. A written ADR documenting the new selection rationale
3. Update of `evals/calibration.py` and re-generation of the agreement report

No threshold change may be committed without updating `Instrument_Report.md` with the new provenance.

### 7.2 Calibration Corpus Immutability

Human labels in `calibration_v7.yaml` and `calibration_v8.yaml` are **immutable input evidence**. They are never overwritten by judge scores or grader outputs. Changes require:
- A new case with a unique `id` (never re-use an existing id)
- `source: independently_authored` or `source: human_review` annotation
- SHA-256 update in `tests/evals/test_calibration.py`

---

## 8. Dependency Graph & Critical Path

```
                    ┌─────────────────────────────────────────────┐
                    │ Phase 1: Deterministic Fixes (current)       │
                    │  1A v12 recapture ──→ 1B cascade fix ──→ 1C  │
                    └──────────────────────┬──────────────────────┘
                                           │ new baseline
                                           ▼
                    ┌─────────────────────────────────────────────┐
                    │ Phase 2: SQL & Behavior Prompts              │
                    │  2A SQL hardening ──→ 2B clarify ──→ 2C grader│
                    └──────────────────────┬──────────────────────┘
                                           │ ~91% baseline
                                           ▼
                    ┌─────────────────────────────────────────────┐
                    │ Phase 3: Judge Hardening                     │
                    │  3A judge prompt ──→ 3B scenario review     │
                    └──────────────────────┬──────────────────────┘
                                           │ 0 false passes
                                           ▼
                    ┌─────────────────────────────────────────────┐
                    │ Phase 4: Flywheel                            │
                    │  4A online traces ──→ 4B registry write-back │
                    └─────────────────────────────────────────────┘
```

**Critical path:** 1A → 1B → 2A → 2B → 3A → 4A
Each phase gates the next because baseline comparability requires a stable prompt and grader.

---

## 9. Risk Register

| ID | Risk | Impact | Likelihood | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Judge hardening increases false negatives | Gate fails closed on previously-passing cases | Medium | Validate on calibration corpus first; compare agreement rates before baseline re-capture | Eval maintainer |
| R2 | SQL prompt over-constraint breaks passing scenarios | Regression in execution_accuracy | Medium | Add soft guidance ("prefer role first") rather than hard bans; regression test per scenario | Eval maintainer |
| R3 | New calibration cases change threshold selection | Threshold sweep may select different bar | Low | Re-sweep and document; maintain backward-compatible reporting | Eval maintainer |
| R4 | Flywheel introduces low-quality automated cases | Calibration corpus degrades | Medium | Human review gate before any v8 write; SHA-256 pinning catches accidental changes | Eval maintainer |
| R5 | Judge provider outage delays release gate | Gate cannot run; release blocked | Low | Provider arm fallback (groq); recall-first policy means partial runs are already rejected | Ops |
| R6 | Prompt version drift between surfaces | Baseline incomparable to previous | Low | Manifest records all three prompt surface versions; grader requires matching versions | Eval maintainer |

---

## 10. Command Quick Reference

```powershell
# ---- Full baseline workflow ----
docker compose up -d
uv run python -m evals.fixtures.loader
uv run pytest -q tests/evals

# ---- Capture ----
uv run python -m evals.driver --output evals/runs/<run>.json

# ---- Score (semantic, separate pass) ----
uv run python -m evals.score --run evals/runs/<run>.json

# ---- Grade ----
uv run python -m evals.execution_accuracy evals/runs/<run>.json --output evals/runs/<run>-execution.json
uv run python -m evals.grader --run evals/runs/<run>.json --execution-accuracy evals/runs/<run>-execution.json --output evals/runs/<run>-grade.json

# ---- Freeze + Replay ----
uv run python -m evals.driver freeze evals/runs/<run>.json --grade evals/runs/<run>-grade.json -o evals/replays/<run>.json
uv run python -m evals.replay --all

# ---- Calibration ----
uv run python -m evals.calibration_score --corpus v7 --corpus v8 --out evals/runs/judge-scores.json
uv run python -m evals.calibration_score --agreement-of evals/runs/judge-scores.json --out evals/runs/agreement-report.json

# ---- Release gate (live) ----
uv run pytest -m eval -v

# ---- Flywheel ----
uv run python -m evals.flywheel --grade evals/runs/<run>-grade.json --scores evals/runs/judge-scores.json -o evals/runs/flywheel-review.md

# ---- Validate ----
uv run pytest
uv run ruff check .
uv run mypy
uv run python scripts/docs_lint.py
```

---

## 11. Definition of Done — Per Phase

| Phase | DoD Criteria |
|---|---|
| **Phase 1** | Baseline re-capture against v12 prompt shows ≥80% pass rate; 1B cascade fix verified with 2 new grader tests; 1C threshold change documented in ADR or Instrument_Report |
| **Phase 2** | Baseline re-capture against v13 prompt shows ≥90% pass rate; execution_accuracy failures ≤7; all new prompt rules verified against edge-case scenarios |
| **Phase 3** | Calibration agreement report shows 0 disagreements across 56 cases; per-class recall = 1.0; precision improved over Phase 2; ADR documenting any threshold changes |
| **Phase 4** | Flywheel exports T1/T2/T3 candidates from at least one live trace batch; ≥1 new calibration case authored from flywheel output; re-baseline cadence documented in Operating_Manual |

---

## 12. Open Questions for Firstmate

| # | Question | Options |
|---|---|---|
| Q1 | Should Phase 2 SQL prompt changes use hard bans or soft guidance? | (A) Hard bans — risk breaking some scenarios but stronger contract; (B) Soft guidance — lower risk but less deterministic |
| Q2 | Should the flywheel Phase 4 connect to Langfuse first or build offline selector first? | (A) Langfuse integration first — faster path to live data but credential-dependent; (B) Offline selector first — proves value without credentials |
| Q3 | Is the current 8-case disagreement count acceptable as a interim state, or must Phase 3 resolve all before any release claim? | (A) Resolve all 8 — clean signal but longer timeline; (B) Document remaining 8 and proceed — acceptable for recall-first claim since FN=0 |

---

## Appendix A: File Map

| Path | Role |
|---|---|
| `evals/scenarios_v1.yaml` | Scenario registry (single source of truth) |
| `evals/calibration_v7.yaml` | Immutable human-label corpus (44 cases) |
| `evals/calibration_v8.yaml` | Independent holdout corpus (12 cases) |
| `evals/calibration_release_gate.yaml` | Release gate threshold config |
| `evals/calibration.py` | Threshold selection, sweep, agreement reporting |
| `evals/driver.py` | Capture orchestration + freeze |
| `evals/execution_accuracy.py` | SQL contract comparison |
| `evals/score.py` | Semantic judge scoring pass |
| `evals/grader.py` | Mechanical deterministic grader |
| `evals/replay.py` | Replay discovery and CI gate |
| `evals/semantic.py` | Judge wrapper, criteria assembly, failure-mode annotations |
| `evals/flywheel.py` | Trace-to-registry candidate selector (Phase 4) |
| `evals/viewer.py` | Local result viewer |
| `evals/harness.py` | Agent fixture harness |
| `evals/pipeline.md` | Pipeline documentation |
| `evals/Operating_Manual.md` | Maintainer review rules |
| `evals/Instrument_Report.md` | Dated baseline and open cases |
| `.github/workflows/ci.yml` | CI integration (deterministic checks + manual release gate) |

---

*This roadmap is a living document. Update it when a phase completes or when a new risk emerges. Refer to `evals/README.md` for navigation and `evals/pipeline.md` for exact run commands.*
