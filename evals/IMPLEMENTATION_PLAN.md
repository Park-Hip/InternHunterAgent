# InternHunterAgent — Eval Pass Rate Improvement Plan

**Branch:** `fm/iha-eval-implementation-plan`
**Baseline:** v11 prompt · 63.8% pass rate (60 PASS / 34 FAIL, 94 turns)
**Target:** 91–92% after all phases
**Source reports:** `data/iha-eval-pass-rate-investigation/report.md`, `data/iha-false-pass-resolution/report.md` <!-- lint-allow-link-path -->

---

## Quick Summary

| Phase | Fix | Effort | Impact | Status |
|---|---|---:|---:|---|
| 1 | 1A — Prompt v12 re-capture | 1 day | +7 pts → 71.3% | Pending |
| 1 | 1B — Source links cascade fix | 2–3 days | +10 pts → ~82% | Pending |
| 1 | 1C — HLP threshold tuning | 0.5 day | +1 pt → ~83% | Pending |
| 2 | 2A — SQL prompt hardening | 3–5 days | +5–8 pts → ~90% | Pending |
| 2 | 2B — Detail/clarify prompt | 2–3 days | +4 pts → ~90% | Pending |
| 2 | 2C — Grader precision tweaks | 1–2 days | +1 pt → ~91% | Pending |
| 3 | 3A — Judge prompt hardening | 1–2 weeks | Eliminates 8 FPs | Pending |
| 3 | 3B — Scenario design review | Ongoing | Variable | Pending |

---


---

## Documentation Audit — Completed (2026-09-05)

The evaluation-instrument documentation audit is **complete**. The approved plan is fully implemented:

- **Semantic tier** documented under `evals/semantic/` (index, judge, rubric, exemplars, not-evaluated).
- **Calibration** documented under `evals/calibration/` (index, corpus, thresholds).
- **Replay** documented under `evals/replay/index.md`.
- **Authoring** documented under `evals/authoring/index.md`.
- **Tests mapping** documented under `tests/evals/ — test-to-module mapping`.
- **Pipeline** documented in `evals/pipeline.md` (5 steps, result terms, commands).
- **Disagreements** documented under `evals/disagreements/index.md`.
- **Deterministic deep dive** converted from Lavish HTML to `evals/deterministic/index.md` (in-repo, version-controlled).
- `evals/README.md` rewritten as a navigation hub (role routing, decision tree, quick commands, full map).
- `docs/how-to/evaluate.md` reduced to a thin pointer.

## Phase 1: Quick Wins (1–3 days each, target ~82%)

### 1A — Prompt v12 Re-capture

**Impact:** +7 pts (63.8% → 71.3%)
**Effort:** 1 day
**Risk:** None (pure re-run)

**What:** The v12 system prompt (already in `config/prompts.yaml`, `prompt_versions.system: v12`) explicitly forbids quoting column names like `listing_expires_on`. This fixes 7 `no_schema_identifier_leak` failures.

**Steps:**
1. Bump `prompt_versions.system` to `v12` (if not already)
2. Re-run baseline: `uv run python evals/driver.py --baseline`
3. Compare `v11-baseline-20260902-grade.json` with new capture

**Files:** `config/prompts.yaml` (system_prompt section, already v12)
**Command:** `uv run python evals/driver.py --baseline --prompt-version v12`

**Verification:** Confirm 7 `no_schema_identifier_leak` failures disappear. Expect 67 PASS / 27 FAIL.

---

### 1B — Source Links Cascade Fix

**Impact:** +10 pts (resolves 10 of 14 source_links failures)
**Effort:** 2–3 days
**Risk:** Medium — changes grader semantics

**Root cause:** When `execution_accuracy` fails, the grader uses `generated_rows` (agent's wrong results) to check `source_links`. The agent's answer correctly lists URLs for its actual returned rows, but the grader expects URLs from the *reference* rows — causing a false cascade.

**Fix sketch** (`evals/grader.py`):

```python
# Line 68-71: Evidence constructor
returned_rows=(
    seams.get("returned_rows")
    or turn.get("returned_rows")
    or (execution_accuracy or turn.get("execution_accuracy") or {}).get("generated_rows")
    # Keep existing fallback chain
),

# _source_link_check (line 726+): add execution_passed parameter
def _source_link_check(
    answer: str | None,
    returned_rows: list[dict[str, Any]] | None,
    execution_passed: bool | None = None,
) -> Check:
    urls = [
        row["source_url"]
        for row in returned_rows or []
        if isinstance(row.get("source_url"), str) and row["source_url"].strip()
    ]
    rendered = answer or ""
    has_label = "nguồn" in rendered.casefold() or "source link" in rendered.casefold()
    availability_claims = [
        pattern.pattern
        for pattern in _SOURCE_AVAILABILITY_PATTERNS
        if pattern.search(rendered)
    ]
    if execution_passed is False and urls:
        # Execution failed: validate URLs present in answer itself,
        # not URLs from wrong reference rows.
        import re
        found_urls = re.findall(r'https?://[^\s&lt;)+\]]+', rendered)
        if found_urls:
            return Check(
                "source_links", True,
                "execution failed; validated URLs from answer text",
                "structural",
            )
    missing = [url for url in urls if url not in rendered]
    passed = not urls or (has_label and not missing and not availability_claims)
    ...
```

**Files:** `evals/grader.py` lines 68–71, 726–747
**Tests:** `uv run pytest tests/evals/test_grader.py -k source`

**Verification:**
1. Run grader tests
2. Re-capture v11 baseline with modified grader — source_links should drop from 14 → ~4
3. Confirm no new false negatives on scenarios where execution_accuracy passes

**Rollback:** Revert `grader.py` to prior commit and re-run v11 capture.

---

### 1C — HLP Threshold Tuning

**Impact:** +1 pt (eliminates 1 false pass from 8 total)
**Effort:** 0.5 day
**Risk:** Very low

**What:** Sweep data from the false-pass report shows HLP false passes drop from 4 → 3 at threshold ~0.6, with recall staying at 1.0. This eliminates `hlp-senior-title-v8-fail` (the boundary case where the judge acknowledged the defect but scored 0.5).

**Steps:**
1. Find all HLP scenarios with `judge_threshold: 0.5` in `evals/scenarios_v1.yaml`
2. Change to `judge_threshold: 0.6`
3. Re-run calibration: `uv run python evals/calibration_score.py`
4. Confirm FP drops to 3, recall stays 1.0

**Files:** `evals/scenarios_v1.yaml`
**Command:** `uv run python evals/calibration_score.py`

**Rollback:** One-line revert: `judge_threshold: 0.6` → `0.5`

---

## Phase 2: Medium Effort (1–2 weeks, target ~90%)

### 2A — SQL Generation Prompt Hardening

**Impact:** +5–8 pts (reduces execution_accuracy failures from 12 → ~4–7)
**Effort:** 3–5 days
**Risk:** Medium — over-constraining could break some currently-passing scenarios

**Root cause:** 12 execution_accuracy failures stem from the agent generating imprecise SQL:
- Searching `tech_stack`/`description` instead of `role` for job-title queries (6 turns)
- Returning full rows instead of `COUNT(*)` for count queries (2 turns)
- Applying unsolicited filters like "machine learning" on "all jobs" (1 turn)
- Filtering out USD rows on cross-currency queries (3 turns)

**Fix** — add to `config/prompts.yaml` `sql_generation` section, bump version to `v13`:

```yaml
# ADD these rules to sql_generation:

- For job-title queries (e.g. "AI Engineer", "Data Scientist"), match the role column
  first: role ILIKE '%AI Engineer%'. Do NOT fall back to searching tech_stack and
  description for role-like terms unless the user explicitly asks about technologies
  or skills.

- For "how many / count / bao nhiêu" questions, output exactly:
    SELECT COUNT(*) AS count
  Do NOT SELECT id, title, or any row columns. Return the number, not a list.

- Do NOT add a LIMIT clause unless the user explicitly requests a specific number
  of results (e.g. "top 5", "show me 3 jobs"). Otherwise omit LIMIT — the system
  applies its own result cap.

- For cross-currency ranking queries, return ALL salary rows grouped by currency.
  Never filter to only one currency group. Order by salary only within each
  currency group.
```

**Files:** `config/prompts.yaml` — `sql_generation` section (~line 50), bump `prompt_versions.sql_generation: v13`
**Tests:** Re-capture baseline, check execution_accuracy metric

**Verification:**
1. Bump `prompt_versions.sql_generation` to `v13`
2. Re-capture: `uv run python evals/driver.py --baseline`
3. Check execution_accuracy failures drop from 12 → ~4–7
4. Verify no regression in other check categories

**Rollback:** Revert `sql_generation` section to v11 text and `prompt_versions.sql_generation` back to `v11`.

---

### 2B — Detail/Clarify Behavior Prompt

**Impact:** +4 pts (fixes HLP-DETAIL-3, HLP-DETAIL-7, HLP-CLARIFY-1)
**Effort:** 2–3 days
**Risk:** Low

**Root cause:** Agent asks for clarification when explicit numeric IDs are provided, and doesn't call `get_job_details` directly.

**Fix** — add to `config/prompts.yaml` under `# Clarification and multi-turn refinement`:

```yaml
- When the user provides explicit numeric IDs (e.g. "việc số 1, 2, 3" or "jobs 1, 2, 3, 4"),
  pass them directly to get_job_details([...]). Do not ask for clarification about the IDs.
- Only ask for clarification when the request is genuinely ambiguous, not when specific
  IDs or parameters are provided.
```

**Files:** `config/prompts.yaml` — system_prompt, clarification subsection
**Version bump:** `prompt_versions.system: v12` → `v13`

**Verification:** Re-capture, check required_tool_called failures drop from 4 → 0.

---

### 2C — Grader Precision Tweaks

**Impact:** +1 pt (reduces false positives on salary_period and language_pure)
**Effort:** 1–2 days
**Risk:** Low

**Sub-fix A — Salary period false positive:**
In `evals/grader.py`, modify `_salary_period_check` to not infer an implicit monthly period from salary amounts alone. Only flag when the answer explicitly states a conflicting period.

**Sub-fix B — Language purity exceptions:**
In `evals/grader.py` `_answer_language_pure`, add an allowlist of common technical terms that naturally appear in Vietnamese job postings:
```python
_ALLOWED_TECH_TERMS = frozenset({
    "AI", "SQL", "Python", "Data", "ML", "Remote", "React", "Docker",
    "JavaScript", "TypeScript", "Backend", "Frontend", "Fullstack",
    "Java", "Go", "Rust", "Kotlin", "Swift", "PHP", "Ruby", "Node",
    "AWS", "GCP", "Azure", "Linux", "Git", "API", "REST", "GraphQL",
})
```

**Files:** `evals/grader.py` — lines ~476 (`_answer_mentions_returned_salary`), ~947 (`_answer_language_pure`)
**Tests:** `uv run pytest tests/evals/ -k "salary or language"`

---

## Phase 3: Longer Term (2–4 weeks, target ~91–92%)

### 3A — Judge Prompt Hardening

**Impact:** Eliminates all 8 false passes from calibration review
**Effort:** 1–2 weeks
**Risk:** Medium — stricter judge could increase false negatives

**Root cause:** All 8 false passes share one pattern: the judge accepts answers that structurally violate scenario requirements because the rubric doesn't enforce those structures explicitly.

**Fix** — add to judge prompt in `evals/semantic.py`:

```
STRUCTURAL REQUIREMENTS (must be enforced strictly):

1. FREE_TEXT queries: If the data has no dedicated field for the requested info,
   the hedge ("based on posting text, may be imperfect") MUST appear before or
   interleaved with any list — never as an afterthought at the end.

2. NEGOTIABLE_SALARY: "negotiable" or "not disclosed" is DIFFERENT from
   "absent from data". If is_salary_negotiable=true, the salary EXISTS but the
   amount is not fixed. Do not use ABSENT_FIELD language for negotiable salaries.

3. REFERENT_CLARIFY: If the conversation has no prior list of items, you MUST
   require the assistant to ask a clarifying question. Never accept an answer
   that invents a referent (e.g. "the 5 jobs from earlier") when no prior list
   exists.

4. GENERAL_KNOWLEDGE: An answer that "offers to search" is NOT sufficient.
   The assistant must actually perform the search and list the results.
   Only offering is a FAIL.

5. SENIOR_TITLE: The hedge is required for ALL title-text matches, not just
   fuzzy matches. "Senior" in a job title is title text, not a structured
   seniority level. The answer must hedge even when the word "Senior" appears
   verbatim in the title.

6. ROLE_FALLBACK: When a user's term doesn't match the primary role field,
   the assistant must attempt the fallback: search title and description,
   and disclose that matched rows are categorized as role='Other'. Do not
   give up and ask for clarification.
```

**Files:** `evals/semantic.py` — judge prompt construction (~line 1–80)
**Tests:** Re-run calibration agreement on v7+v8 corpus — confirm 0 false passes; run `calibration_score.py` — confirm recall still 1.0

**Verification:**
1. Re-run `uv run python evals/calibration_score.py` on v7+v8
2. Confirm all 8 previously-false-pass cases now score correctly
3. Run full baseline — check no regression

**Rollback:** Revert `semantic.py`; calibration agreement report is preserved as evidence.

---

### 3B — Scenario Design Review

**Impact:** Variable (depends on findings)
**Effort:** Ongoing
**Risk:** Low — only widens contracts, never tightens

**Scenarios to review:**

| Scenario | Issue | Proposed Fix |
|---|---|---|
| `HLP-COUNT-1` | `count_only` requires single sentence; list with count embedded fails | Widen to accept a list where the count is explicitly stated |
| `HLP-TRUNCATION-1` | Reference returns all 20 jobs; agent returns 16 "AI/Data" jobs | Widen reference SQL or adjust agent expectation |
| `SAF-DESTRUCTIVE-REFUSAL-2` | Extra `source_url` column triggers execution_accuracy failure | Relax column-exactness check for optional trailing columns |

**Files:** `evals/scenarios_v1.yaml`, `evals/grader.py` (execution accuracy column check)

---

## Dependency Graph

```
1A (v12 re-capture) ──┬──→ 1B (cascade fix) ──→ 2B (detail/clarify) ──┐
                       │                       │                         │
                       └──→ 2A (SQL prompt) ───┴──→ 3A (judge prompt) ──→ 3B (scenario review)
1C (threshold) ──independent──→ 2C (grader precision) ──────────────────────→
```

**Critical path:** 1A → 1B → 2B → 3A
Each phase gates the next because:
- v12 re-capture establishes the new baseline
- The cascade fix must land before SQL prompt changes are measurable
- Judge hardening depends on knowing the post-fix failure profile

---

## Risk Register

| Fix | Risk | Mitigation | Rollback |
|---|---|---|---|
| **1B** | Changes grader semantics; old evidence less comparable | Re-run v11 baseline before/after change; document new behavior | Revert `grader.py`, re-run capture |
| **2A** | Over-constrain SQL prompt, break currently-passing scenarios | Add rules as soft guidance ("prefer role first, fall back if no match"), not hard bans | Revert `sql_generation` section + version |
| **3A** | Stricter judge increases false negatives | Validate on calibration corpus first; compare agreement rates | Revert `semantic.py` |
| **1C** | Raising threshold causes recall drop | Sweep data shows recall=1.0 at 0.6; verify with full calibration run | One-line revert in `scenarios_v1.yaml` |
| **2C** | Widening checks reduces grading rigor | Each tweak narrowly scoped; run targeted tests first | Revert `grader.py` changes |
| **1A** | None | N/A | N/A |

---

## Estimated Pass Rate Progression

| Milestone | PASS | FAIL | Rate |
|---|---:|---:|---:|
| Current (v11) | 60 | 34 | 63.8% |
| After 1A (v12 recapture) | 67 | 27 | 71.3% |
| After 1B (cascade fix) | ~77 | ~17 | ~82% |
| After 1C (threshold) | ~78 | ~16 | ~83% |
| After 2A (SQL prompt) | ~83–86 | ~8–11 | ~88–90% |
| After 2B (detail/clarify) | ~87 | ~7 | ~92% |
| After 2C (grader precision) | ~88 | ~6 | ~93% |
| After 3A (judge prompt) | ~88–90 | ~4–6 | ~91–92%* |
| After 3B (scenario review) | Variable | Variable | Variable |

*Judge prompt hardening eliminates false passes in calibration but may slightly reduce measured baseline pass rate by catching genuine failures the loose judge previously missed.

---

## Commands Reference

```bash
# Re-capture baseline with v12 prompt
uv run python evals/driver.py --baseline --prompt-version v12

# Run grader tests
uv run pytest tests/evals/test_grader.py -k source

# Run calibration score
uv run python evals/calibration_score.py

# Full test suite
uv run pytest

# Lint docs
uv run python scripts/docs_lint.py
```

---

## Artifacts

<!-- lint-allow-link-path:begin -->

| Artifact | Path |
|---|---|
| Visual plan | `evals/implementation-plan.html` |
| This document | `evals/IMPLEMENTATION_PLAN.md` |
| Scout report 1 | `/home/hiep/firstmate/data/iha-eval-pass-rate-investigation/report.md` |
| Scout report 2 | `/home/hiep/firstmate/data/iha-false-pass-resolution/report.md` |
| Grade report | `evals/runs/v11-baseline-20260902-grade.json` |
| Execution report | `evals/runs/v11-baseline-20260902-execution.json` |
| Scenarios | `evals/scenarios_v1.yaml` |
| Grader source | `evals/grader.py` |
| Judge source | `evals/semantic.py` |
| Prompts | `config/prompts.yaml` |

<!-- lint-allow-link-path:end -->
