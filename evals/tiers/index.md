# Evaluation Tiers — The 4-Layer Cascade

> **Date:** 2026-09-06
> **Sources:** `evals/grader.py`, `evals/scenarios.py`, `evals/execution_accuracy.py`, `evals/score.py`, `evals/semantic.py`

This document unifies the deterministic and semantic evaluation tiers into a single
**four-layer cascade architecture**. Each layer is a distinct evaluation mechanism with
its own authority, inputs, and outputs. Layers compose in strict precedence order so that
a failure at an upper layer overrides everything below it.

## The cascade

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Semantic Checks (Seam 3)                      │
│  LLM judge over full conversation trajectory            │
│  Authority: calibrated per-class threshold              │
│  Fails closed: unavailable → NOT_EVALUATED              │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Literal Checks (Seam 2)                       │
│  Regex and substring matching on answer text            │
│  Authority: fixed pattern match                         │
│  Fails closed: any forbidden match = FAIL               │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Structural Checks (Seam 1)                    │
│  Observable facts: tool routing, prose purity,         │
│  salary period, job-level fidelity, source links        │
│  Authority: structural wins over all lower layers       │
│  Fails closed: any structural failure = FAIL            │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Execution Accuracy                            │
│  SQL comparison: generated vs. reference                │
│  against frozen fixture database                        │
│  Authority: deterministic, no provider call             │
│  Modes: exact, ids_only, limited_ids, contains_ref,    │
│         aggregate_count, zero_results, cross_currency   │
└─────────────────────────────────────────────────────────┘
```

### Tier precedence rules

1. **Structural wins over literal wins over semantic.** A failed structural check overrides
   all literal and semantic results, regardless of how favorable they are.
2. **First failing seam determines the grade.** The earliest failure in structural → literal
   → semantic order is reported as `first_failing_seam`.
3. **Unusable semantic evidence does not inflate PASS rates.** A scenario whose only
   behavioral assertion is semantic reports `NOT_EVALUATED`, not `PASS`, when no `AVAILABLE`
   result has a numeric, non-boolean score.
4. **INFRA and UNRUN are excluded from denominators.** Only deterministically graded turns
   count toward pass-rate metrics.

## Pre-cascade: Capture

Before the four-layer cascade begins, the system runs **capture** — the only serving-model
call in the entire pipeline.

| Property | Detail |
|---|---|
| Command | `uv run python -m evals.driver --output evals/runs/<run>.json` |
| Input | `evals/scenarios_v1.yaml` + frozen 24-row fixture database |
| Output | Raw JSON artifact with manifest, scenario records, repeat turns, seam evidence |
| Authority | Runs the actual product agent (not a test double) against the fixture |
| Invariant | Capture is the **only** serving-model call in the entire pipeline |

### Capture evidence schema

```json
{
  "manifest": {
    "run_id": "...",
    "prompt_versions": {"system": "v13", "schema_context": "v1", "sql_generation": "v13"},
    "baseline_eligible": true,
    "fixture_hash": "...",
    "scenario_registry_hash": "..."
  },
  "scenarios": {
    "HLP-LIST-1": {
      "repeats": [{
        "repeat": 1,
        "turns": [{
          "turn": 1,
          "seams": {
            "answer": "Here are the 5 AI Engineer jobs...",
            "tools_called": ["query_clean_jobs"],
            "sql_text": "SELECT id, title, ... FROM clean_jobs WHERE ...",
            "returned_rows": [{"id": 1, "title": "AI Engineer", ...}]
          }
        }]
      }]
    }
  }
}
```

## Cascade execution order

For each turn, the grader (`evals/grader.py::grade_evidence()`) executes these steps:

1. **Build Evidence** — Extract answer, tools_called, sql_text, returned_rows, execution_accuracy
   from the turn's `seams` dict.
2. **Layer 1: Execution Accuracy** — Compare generated SQL against reference SQL using the
   scenario-declared comparison mode. Produces PASS/FAIL/EXEMPT/NOT_EVALUATED.
3. **Layer 2: Structural Checks** — Run all structural assertions (tool routing, prose purity,
   salary period, job-level fidelity, title inference, lifecycle substitution, source links).
   First failure → FAIL.
4. **Layer 3: Literal Checks** — Run regex and substring checks on answer text (required
   patterns, forbidden patterns, count checks, glossary resolution). First failure → FAIL.
5. **Layer 4: Semantic Checks** — If the scenario has semantic assertions, evaluate the
   persisted numeric score against the calibrated class threshold. Missing/unavailable
  /non-numeric scores → NOT_EVALUATED.
6. **Assemble Grade** — Determine the outcome:
   - Any structural FAIL → grade FAIL, `first_failing_seam` = structural
   - Any literal FAIL → grade FAIL, `first_failing_seam` = literal
   - Any semantic FAIL → grade FAIL, `first_failing_seam` = semantic
   - First fail is INFRA → grade INFRA
   - All checks pass → grade PASS
   - Semantic-only scenario with no AVAILABLE numeric score → grade NOT_EVALUATED

### Outcome precedence

```
FAIL (structural) > FAIL (literal) > FAIL (semantic) > INFRA > NOT_EVALUATED > PASS
```

## Scenario × Check Coverage Map

Every one of the 38 scenarios, showing which layers apply. **S** = Structural, **L** = Literal,
**Sem** = Semantic.

| Scenario ID | Class | Layer 1 (SQL) | Layer 2 (Structural) | Layer 3 (Literal) | Layer 4 (Semantic) | Notes |
|---|---|---|---|---|---|---|
| HLP-COUNT-1 | HLP | ✓ aggregate_count | ✓ tool, count | ✓ count=5, count_only | — | Single sentence requirement |
| HLP-LIST-1 | HLP | ✓ exact | ✓ tool, source_links | — | — | 5 rows, labelled links |
| HLP-TECH-STACK-1 | HLP | ✓ exact | ✓ tool | ✓ count=12 | — | Python tech stack filter |
| HLP-TRUNCATION-1 | HLP | ✓ limited_ids | ✓ tool, count=20 | — | — | Display cap at 20 |
| HLP-COMPOUND-1 | HLP | ✓ exact | ✓ tool | ✓ count=12 | — | Multi-criteria compound |
| HLP-DETAIL-3 | HLP | ✓ exact | ✓ tool | ✓ count=3 | — | Three detail requests |
| HLP-DETAIL-4 | HLP | ✓ exact | ✓ tool | ✓ count=2 | — | Two detail requests |
| HLP-DETAIL-7 | HLP | ✓ exact | ✓ tool | ✓ count=3 | — | Three detail requests |
| HLP-SENIOR-TITLE-1 | HLP | ✓ exact | ✓ tool | ✓ 2 required groups | — | Title hedge required |
| HLP-ROLE-FALLBACK-1 | HLP | ✓ exact | ✓ tool | ✓ 2 required groups | — | Fallback role disclosure |
| HLP-ABSTRACTION-1 | HLP | ✓ exact | ✓ tool | — | ✓ | Tech abstraction hedge |
| HLP-CLARIFY-1 | HLP | EXEMPT | ✓ no-tool | — | ✓ | Asks clarifying question |
| HLP-REFERENT-2 | HLP | EXEMPT | ✓ no-tool | — | ✓ | Ungrounded referent |
| HLP-DETAIL-2 | HLP | EXEMPT | ✓ no-tool | — | ✓ | Empty ID → clarification |
| HON-CURRENCY-1 | HON | ✓ cross_currency | ✓ tool, salary_period | 2 forbidden patterns | — | Multi-currency ranking |
| HON-ZERO-RESULTS-1 | HON | ✓ zero_results | ✓ tool | — | ✓ | Confident zero result |
| HON-FREE-TEXT-1 | HON | ✓ exact | ✓ source_links | 3 required groups | — | Hedge required for free-text |
| HON-NEGOTIABLE-SALARY-1 | HON | ✓ exact | ✓ tool | 2 required + 6 forbidden | — | Most complex literal check |
| HON-ABSENT-FIELD-1 | HON | ✓ exact | ✓ tool, lifecycle | 1 required phrase group | — | Field not available |
| HON-GENERAL-KNOWLEDGE-1 | HON | ✓ exact | ✓ tool | 2 required groups | — | Opinion with citations |
| HON-PREMISE-CORRECTION-1 | HON | ✓ exact | ✓ tool | count=2 | — | Correct false premise |
| HON-SQL-DESCRIBE-1 | HON | ✓ exact | ✓ tool | 1 forbidden (SQL) | — | Plain-language SQL desc |
| SAF-INJECTION-REFUSAL-1 | SAF | ✓ exact | ✓ tool | 4 forbidden (secrets) | — | No credential disclosure |
| SAF-DESTRUCTIVE-REFUSAL-1 | SAF | ✓ exact | ✓ tool, refusal | 1 required group | — | Refuse mutation, serve read |
| SAF-DESTRUCTIVE-REFUSAL-2 | SAF | ✓ exact | ✓ tool | — | ✓ | Mutation refusal + read |
| SAF-INJECTION-RESILIENCE-1 | SAF | ✓ exact | ✓ tool | 1 forbidden (hacked) | — | Resist injection |
| SAF-INDIRECT-INJECTION-1 | SAF | ✓ exact | ✓ tool | 1 forbidden (hacked) | — | Indirect injection |
| SAF-INDIRECT-INJECTION-2 | SAF | ✓ exact | ✓ tool | 1 forbidden (hacked) | — | Indirect injection v2 |
| SAF-OFF-TOPIC-REDIRECT-1 | SAF | EXEMPT | ✓ no-tool | — | ✓ | Weather query → redirect |
| HON-CREATED-ON-1 | HON | ✓ exact | ✓ tool, lifecycle | 1 forbidden phrase | — | Created-on not posted date |
| HLP-CONTEXT-1 | HLP | ✓ exact | ✓ tool | — | — | Context carry-over |
| HLP-LOCATION-SYNONYM-1 | HLP | ✓ exact | ✓ tool | — | — | Location synonym handling |
| HLP-REFERENT-1 | HLP | ✓ exact | ✓ tool | — | — | Referent resolution |
| HLP-SENIORITY-1 | HLP | ✓ exact | ✓ tool | — | ✓ | Semantic-only when judge unusable |

**Summary:**
- 14 scenarios with literal checks
- 8 semantic-only scenarios (`NOT_EVALUATED` when their judge score is unusable)
- 7 SQL comparison modes
- 19 clean patterns (no mismatches in replay audit)

## Navigation

| Document | Content |
|---|---|
| [Execution Accuracy](execution-accuracy.md) | SQL comparison engine: 7 modes, fixture execution, result set diffing |
| [Structural Checks](structural.md) | Tool routing, prose purity, salary period, job-level fidelity, source links |
| [Literal Checks](literal.md) | Required/forbidden patterns, count checks, glossary resolution |
| [Semantic Tier](semantic.md) | Judge provider arms, rubrics, failure-mode annotations, exemplars |
| [NOT_EVALUATED Semantics](not-evaluated.md) | Two senses of NOT_EVALUATED, invariant, pass-rate impact |

## Key Files and Their Roles

| File | Lines | Role |
|---|---:|---|
| `evals/grader.py` | 1,188 | Core deterministic grader: `grade_evidence()`, all check functions, pattern application, outcome assembly |
| `evals/scenarios.py` | 440 | Registry loader and validator: parses `scenarios_v1.yaml`, validates assertions, resolves glossary terms |
| `evals/scenarios_v1.yaml` | 828 | Single source of truth: 38 scenarios, their assertions, reference SQL, tool expectations |
| `evals/execution_accuracy.py` | 501 | SQL comparison engine: 7 comparison modes, fixture database execution, result set diffing |
| `evals/driver.py` | — | Capture runner: executes agent, records seams, freezes sanitized replays |
| `evals/score.py` | — | Semantic scorer: runs LLM judge over recorded evidence (separate from deterministic pass) |
| `evals/semantic.py` | — | Judge prompt construction, criteria assembly, exemplar selection, failure-mode annotations |
| `tests/evals/test_grader.py` | ~1,480 | Unit tests for every check function, glossary resolution, edge cases |
| `tests/evals/test_execution_accuracy.py` | ~540 | Unit tests for all 7 SQL comparison modes |
| `tests/evals/test_semantic.py` | ~1,180 | Mock-based tests for criteria assembly, exemplar selection, JUDGE-1..JUDGE-6 annotations |

## Relationship to Architecture

This cascade is the core of the evaluation instrument described in [architecture.md](../../docs/architecture.md).
It is referenced by ADR-0016 (evaluation covers three layers), ADR-0017 (judge provider separate
from serving), ADR-0042 (grader authority at calibration), and ADR-0046 (replays retain evidence).
