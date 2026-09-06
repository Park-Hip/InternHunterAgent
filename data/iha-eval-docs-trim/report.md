# Eval Docs Consolidation — Report

> **Date:** 2026-09-06
> **Branch:** `fm/iha-eval-docs-trim`

## Summary

Consolidated the scattered evaluation documentation across `evals/deterministic/` and `evals/semantic/` into a unified `evals/tiers/` directory organized around the 4-layer cascade architecture. Moved two dated artifacts to `evals/archive/`. Updated all cross-references.

## Findings

### Current surface (before)

- **23 markdown files** across `docs/` and `evals/` related to evaluation
- **Two parallel description layers**: `evals/deterministic/index.md` (14 KB) described the full pipeline including semantic checks, while `evals/semantic/` (5 files, ~8 KB) described the same semantic tier from a different angle <!-- lint-allow-link-path -->
- **Overlap**: both docs covered tier precedence, scenario coverage, and outcome interpretation
- **Broken navigation**: `docs/how-to/evaluate.md` pointed to `evals/deterministic/index.md` and `evals/semantic/index.md`, which were separate from the unified mental model <!-- lint-allow-link-path -->
- **Dated artifacts in root**: `V6_Grader_Audit_2026-08-23.md` and `t0027_deepseek_arm.md` were floating in `evals/` instead of `evals/archive/` <!-- lint-allow-link-path -->

### Consolidation opportunities identified

1. **Deterministic + semantic unification**: The `deterministic/index.md` already described semantic checks as "Step 5" of its pipeline. The `semantic/` directory described the same tier from an implementation perspective. These naturally merge into a single cascade architecture with focused reference sub-docs.
2. **Diátaxis alignment**: The current structure mixed explanation, reference, and how-to across overlapping directories. The new `tiers/` structure cleanly separates:
   - **Explanation**: `tiers/index.md` (cascade architecture)
   - **Reference**: `tiers/execution-accuracy.md`, `tiers/structural.md`, `tiers/literal.md`, `tiers/semantic-*.md`
   - **How-to**: `pipeline.md`, `Operating_Manual.md`, `authoring/index.md`, `replay/index.md`
3. **Archive hygiene**: Historical artifacts belong in `archive/`, not the eval root.

## Merge Map

| Action | From | To | Lines preserved |
|---|---|---|---|
| MERGE | `evals/deterministic/index.md` | `evals/tiers/index.md` | Cascade overview, precedence rules, coverage map, key files <!-- lint-allow-link-path --> |
| MERGE | `evals/deterministic/index.md` §2 | `evals/tiers/execution-accuracy.md` | SQL comparison engine, 7 modes <!-- lint-allow-link-path --> |
| MERGE | `evals/deterministic/index.md` §3 | `evals/tiers/structural.md` | All structural check references <!-- lint-allow-link-path --> |
| MERGE | `evals/deterministic/index.md` §4 | `evals/tiers/literal.md` | Pattern tables, glossary resolution, seam-2 audit notes <!-- lint-allow-link-path --> |
| MERGE | `evals/semantic/index.md` | `evals/tiers/semantic.md` | Tier overview, authority, failure modes, criterion assembly <!-- lint-allow-link-path --> |
| MERGE | `evals/semantic/judge.md` | `evals/tiers/semantic-judge.md` | Judge implementation details <!-- lint-allow-link-path --> |
| MERGE | `evals/semantic/rubric.md` | `evals/tiers/semantic-rubric.md` | Class rubrics, JUDGE-1..6, anti-directives <!-- lint-allow-link-path --> |
| MERGE | `evals/semantic/exemplars.md` | `evals/tiers/semantic-exemplars.md` | Exemplar selection algorithm <!-- lint-allow-link-path --> |
| MOVE | `evals/semantic/not-evaluated.md` | `evals/tiers/not-evaluated.md` | NOT_EVALUATED semantics (no content change) <!-- lint-allow-link-path --> |
| MOVE | `evals/V6_Grader_Audit_2026-08-23.md` | `evals/archive/V6_Grader_Audit_2026-08-23.md` | Historical evidence <!-- lint-allow-link-path --> |
| MOVE | `evals/t0027_deepseek_arm.md` | `evals/archive/t0027_deepseek_arm.md` | Historical evidence <!-- lint-allow-link-path --> |
| DELETE | `evals/deterministic/` | — | Directory removed after merge <!-- lint-allow-link-path --> |
| DELETE | `evals/semantic/` | — | Directory removed after merge <!-- lint-allow-link-path --> |

## Files Changed

### Created (9 new files)
- `evals/tiers/index.md` — unified 4-layer cascade architecture
- `evals/tiers/execution-accuracy.md` — SQL comparison layer reference
- `evals/tiers/structural.md` — structural checks reference
- `evals/tiers/literal.md` — literal checks reference
- `evals/tiers/semantic.md` — semantic tier overview
- `evals/tiers/semantic-judge.md` — judge implementation
- `evals/tiers/semantic-rubric.md` — class rubrics and failure modes
- `evals/tiers/semantic-exemplars.md` — exemplar selection
- `evals/tiers/not-evaluated.md` — NOT_EVALUATED semantics

### Modified (3 files)
- `evals/README.md` — updated role routing, decision tree, and directory map
- `evals/IMPLEMENTATION_PLAN.md` — updated documentation audit section
- `docs/how-to/evaluate.md` — updated pointer links from old paths to `tiers/`

### Moved (2 files)
- `evals/V6_Grader_Audit_2026-08-23.md` → `evals/archive/V6_Grader_Audit_2026-08-23.md` <!-- lint-allow-link-path -->
- `evals/t0027_deepseek_arm.md` → `evals/archive/t0027_deepseek_arm.md` <!-- lint-allow-link-path -->

### Deleted (2 directories)
- `evals/deterministic/` (1 file, content merged)
- `evals/semantic/` (5 files, content merged/moved)

## What Was Kept Unchanged

- `evals/pipeline.md` — core pipeline documentation, no overlap with tiers
- `evals/Operating_Manual.md` — maintainer review procedures
- `evals/Instrument_Report.md` — dated baseline report
- `evals/calibration/` (index.md, corpus.md, thresholds.md) — well-organized, no overlap
- `evals/replay/index.md` — replay contract
- `evals/authoring/index.md` — scenario authoring guide
- `evals/disagreements/index.md` — disagreement workflow
- `evals/archive/` (existing files) — historical evidence
- `docs/architecture.md` — system architecture, only references evals in passing
- `docs/how-to/operate.md`, `docs/how-to/release-gate.md`, `docs/how-to/latency-observability.md` — unrelated ops docs
- `docs/reference/` — schema, configuration, agent behavior
- `docs/decisions/` — ADRs, only ADR-0016/0017/0018/0037/0041/0042/0043/0046/0052 are eval-related and already cross-referenced correctly

## Cross-Reference Updates

All internal links from the old paths have been updated:
- `docs/how-to/evaluate.md`: `evals/deterministic/index.md` → `evals/tiers/index.md`, `evals/semantic/index.md` → `evals/tiers/semantic.md` <!-- lint-allow-link-path -->
- `evals/README.md`: role routing and decision tree entries updated
- `evals/README.md`: directory map updated to show `tiers/` instead of `deterministic/` + `semantic/`
- `evals/IMPLEMENTATION_PLAN.md`: documentation audit section updated

No code files (`*.py`) reference the old doc paths, so no code changes were needed.

## Diátaxis Taxonomy Analysis

The consolidation aligns with the Diátaxis framework:

| Diátaxis Type | Purpose | Documents |
|---|---|---|
| **Explanation** | Build mental models | `tiers/index.md`, `tiers/semantic.md`, `calibration/index.md` |
| **How-To** | Solve problems step-by-step | `pipeline.md`, `Operating_Manual.md`, `authoring/index.md`, `replay/index.md`, `disagreements/index.md` |
| **Reference** | Look up facts | `tiers/execution-accuracy.md`, `tiers/structural.md`, `tiers/literal.md`, `tiers/semantic-judge.md`, `tiers/semantic-rubric.md`, `tiers/semantic-exemplars.md`, `tiers/not-evaluated.md`, `calibration/corpus.md`, `calibration/thresholds.md` |
| **Navigation** | Route by intent | `evals/README.md`, `docs/README.md`, `docs/how-to/evaluate.md` |

The previous structure had the deterministic doc serving double duty as both explanation and reference, while the semantic docs were purely reference. The new structure makes the distinction explicit: `tiers/index.md` is the explanation, and the tier-specific files are reference.

## Verification

- `uv run python scripts/docs_lint.py` — clean (no stale links)
- All markdown files are UTF-8 without BOM
- No PowerShell round-trip was used
- No secrets or production credentials are referenced in any changed doc

## Lavish Artifact

Interactive before/after doc-tree visualization: `data/iha-eval-docs-trim/docs-map.html`
