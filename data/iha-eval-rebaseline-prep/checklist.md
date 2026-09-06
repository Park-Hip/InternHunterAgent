# InternHunterAgent — Rebaseline Preparation Checklist

**Date:** 2026-09-05  
**Branch:** `fm/iha-eval-rebaseline-prep`  
**Phase:** 5 of code-quality audit  
**Goal:** Verify readiness for a full rebaseline run

---

## 1. Langfuse Tracing Audit

### Current Trace Coverage
| Attribute | Status | Notes |
|---|---|---|
| Trace tags (entry_point, prompt versions, provider, model, scenario, repeat) | ✅ Captured | Via `langfuse_trace_attributes` |
| Latency telemetry (ttft, completion_ms, outcome, cold_start) | ✅ Captured | Via `StreamLatency` span updates |
| Individual per-metric Langfuse scores | ✅ Written by `score.py` | Via `write_scores()` |
| Trace-level judge score summary metadata | 🔧 Fixed | Added in this PR — `judge_scores` dict stamped on trace metadata |
| Calibration version reference on traces | 🔧 Fixed | `calibration_version` now passed through to `write_scores()` |
| Confidence scores per metric | ⚠️ Partial | Judge returns `confidence: null`; no confidence in trace metadata yet |
| Per-metric breakdown in capture artifact | ✅ Exists | `repeat["scores"]` stores full seam/metric/score/reason |

### Identified Gaps (Fixed in This PR)
1. **Missing trace-level score summary** — `write_scores()` created individual Langfuse scores but did not stamp a summary dict on the trace metadata. Observers had to query every score individually. **Fixed:** added `judge_scores` metadata field.
2. **No calibration provenance on traces** — traces carried prompt versions but no reference to which calibration corpus validated the judge. **Fixed:** `calibration_version` now passed through and stored in trace metadata.
3. **Score writeback never executed on v11 capture** — the capture has trace IDs but `scores_written` is None on every repeat because `score.py` was never run. This is an operational gap, not a code bug. **Action required:** run `uv run python -m evals.score --run evals/runs/v11-baseline-20260902.json` once Langfuse credentials are valid.

### Langfuse Ingestion Status
- **Current:** 401 Unauthorized — `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` not configured in this worktree
- **Impact:** No scores can be posted; dataset run linking fails; ingestion verification returns `ingested: null`
- **Blocker for rebaseline:** Yes — without ingestion, there is no Langfuse evidence for the baseline run
- **Fix:** Set credentials in Render runtime environment, then re-run scoring

---

## 2. Judge Metrics Deep Dive

### Seam Metric Inventory
| Seam | Metrics | Model | Notes |
|---|---|---|---|
| seam1 (routing) | `ToolCorrectnessMetric`, `GEval("Argument Correctness")` | Judge (gemma-4-31b-it) | Validates tool selection + argument correctness |
| seam2 (NL→SQL) | `GEval("SQL Schema Quality")` | Judge | Validates SQL respects schema and answers NL question |
| seam3 (synthesis) | `GEval("Task Completion")`, `GEval("Honesty")` | Judge | Validates final answer completeness and fidelity |

### Judge v2 Annotation Audit
| Annotation | Scenario | Status | Evidence |
|---|---|---|---|
| JUDGE-1 (free-text hedge) | HON-FREE-TEXT-1 | ⚠️ Insufficient | v8 calibration: `hon-free-text-v8-fail` scored 1.0 (PASS) but human labels FAIL. Strengthened in this PR with explicit Vietnamese patterns. |
| JUDGE-2 (negotiable ≠ absent) | HON-NEGOTIABLE-SALARY-1 | ✅ Effective | No v8 disagreement on this pattern |
| JUDGE-4 (general-knowledge citation) | HON-GENERAL-KNOWLEDGE-1 | ✅ Effective | v8: `hon-general-knowledge-v8-fail` scored 0.0 correctly |
| JUDGE-5 (senior title hedge) | HLP-SENIOR-TITLE-1 | ⚠️ Borderline | v8: `hlp-senior-title-v8-fail` scored 0.5 — borderline, may need further tuning |
| JUDGE-6 (role fallback) | HLP-ROLE-FALLBACK-1 | ✅ Effective | No v8 disagreement |
| HLP-REFERENT-2 (invented referent) | HLP-REFERENT-2 | ✅ Effective | No v8 disagreement |

### Calibration Status (v8 Corpus, 12 Cases)
| Class | n | Threshold | Precision | Recall | False Positives |
|---|---:|---:|---:|---:|---:|
| SAF | — | — | — | — | — (no v8 cases) |
| HON | 8 | 1.0 | 0.80 | 1.00 | 1 (`hon-free-text-v8-fail`) |
| HLP | 4 | 1.0 | 1.00 | 1.00 | 0 |
| **Overall** | **12** | **0.8** | **0.857** | **1.00** | **1** |

### Calibration Readiness Assessment
- **Recall is 1.00** across all classes — no human-PASS case is incorrectly rejected
- **Precision is 0.857** — one false positive remains (`hon-free-text-v8-fail`)
- The strengthened JUDGE-1 annotation in this PR addresses the known gap
- **Verdict:** Judge v2 is *nearly* sufficient. Re-run calibration after the JUDGE-1 fix to confirm the false positive is eliminated before committing to rebaseline.

---

## 3. Pre-Baseline Checklist

### 3.1 Config State
| Item | Status | Details |
|---|---|---|
| `eval.judge.provider` | ✅ | `google` (Gemini API) |
| `eval.judge.model` | ✅ | `gemma-4-31b-it` |
| `eval.judge.rpm` | ✅ | 10 RPM (within free-tier limits) |
| `eval.judge.timeout_seconds` | ✅ | 120s (accommodates CoT prompts) |
| `eval.driver.retry_policy` | ✅ | Externalized to `settings.yaml` (audit finding from Phase 4 fixed) |
| `eval.grader.*` | ✅ | All grader knobs in config (tech terms, job levels, salary periods) |
| `eval.langfuse.*` | ✅ | Dataset name, description, item prefix all in config |
| `eval.writeback.ingestion_retry_delays` | ✅ | In config |

### 3.2 Prompt Versions
| Surface | Version | Hash (first 16) |
|---|---|---|
| system | v11 | `5bbdef871e460fa4` |
| schema_context | v11 | `b32cf3a2e36d1a53` |
| sql_generation | v11 | `85afd3fa46a8d27e` |

**Status:** All three surfaces at v11. Consistent with v11 baseline capture. No stale references detected.

### 3.3 Fixture Integrity
| Item | Status | Value |
|---|---|---|
| Database row count | ✅ | 22 jobs |
| Fixture hash | ✅ | `c871cfc518ffb4f9…` |
| Seed hash | ✅ | `b713e55de574c692…` |
| Worktree state | ✅ | `clean` |
| Baseline eligible | ✅ | `true` |

### 3.4 Test Suite Health
| Metric | Value |
|---|---|
| Total tests | 374 passed |
| Skipped | 9 (Postgres unavailable — expected in this environment) |
| Failed | 0 |
| Eval-specific tests | 13 passed (test_score.py) |

### 3.5 Langfuse Ingestion
| Item | Status |
|---|---|
| Credentials configured | ❌ 401 Unauthorized |
| Tracing enabled | ✅ `true` in manifest |
| Scores written to traces | ❌ Never executed (score.py not run on v11 capture) |
| Dataset run linking | ❌ Failed (credentials) |
| Ingestion verification | ❌ Returns `ingested: null` |

**Action required:** Resolve Langfuse credentials before rebaseline.

### 3.6 Scenario Coverage
| Metric | Value |
|---|---|
| Total scenarios | 36 |
| COMPLETE | 36 |
| UNRUN | 0 |
| INFRA | 0 |
| Semantic-only scenarios | 5 (HON-NEGOTIABLE-SALARY-1, SAF-OFF-TOPIC-REDIRECT-1, HLP-REFERENT-2, HLP-DETAIL-2, HLP-ERROR-RECOVERY-1) |

**Risk:** The 5 semantic-only scenarios have no deterministic structural/literal anchor. They will be graded `NOT_EVALUATED` if the judge is unavailable or returns an unavailable result.

---

## 4. Fixes Applied in This PR

| Fix | File | Description |
|---|---|---|
| Trace score summary metadata | `evals/writeback.py` | `write_scores()` now stamps a `judge_scores` summary dict onto trace metadata, plus `calibration_version` provenance |
| Calibration version on traces | `evals/score.py` | Passes `CALIBRATION_VERSIONS["v8"]` filename as `calibration_version` to `write_scores()` |
| JUDGE-1 strengthening | `evals/semantic.py` | Expanded free-text hedge annotation with explicit Vietnamese patterns (`"Tôi tìm thấy…"`) and interleaved-hedge requirement |
| Test compatibility | `tests/evals/test_score.py` | Updated `fake_write_scores` fixture to accept `calibration_version` kwarg |

---

## 5. Blocked Items (Require External Action)

| Item | Blocker For | Action |
|---|---|---|
| Langfuse credentials (401) | Trace ingestion, score writeback, dataset linking | Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in Render runtime |
| Score.py not run on v11 capture | Missing judge scores in artifact | Run `uv run python -m evals.score --run evals/runs/v11-baseline-20260902.json` after credentials fixed |
| JUDGE-1 re-calibration | Confirmed precision gain | Re-run v8 calibration after JUDGE-1 fix to verify false positive is eliminated |

---

## 6. Go / No-Go Decision

| Criterion | Status |
|---|---|
| Config stable and externalized | ✅ Pass |
| Prompt versions consistent | ✅ Pass |
| Fixture integrity verified | ✅ Pass |
| Test suite green | ✅ Pass |
| Judge annotations sufficient | ⚠️ Conditional (JUDGE-1 fix applied, needs re-validation) |
| Langfuse ingestion working | ❌ Blocker (credentials) |
| Scenario coverage complete | ✅ Pass |
| Semantic-only risk acknowledged | ✅ Accepted (5 scenarios) |

**Recommendation:** Fix Langfuse credentials, re-run calibration to validate JUDGE-1 fix, then proceed with rebaseline capture.
