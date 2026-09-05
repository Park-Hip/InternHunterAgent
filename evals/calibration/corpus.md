# Calibration Corpus

> **Source:** `evals/calibration.py` — `load_calibration()`, `load_combined_calibration()`

## Case schema

Every case in a calibration corpus must conform to this schema, enforced by `load_calibration()`:

```yaml
schema_version: 1
corpus_id: <string>
cases:
  - id: <unique string>
    scenario_id: <scenario id, e.g. HON-CURRENCY-1>
    language: vi
    prompt_version: v6          # legacy key (schema v1)
    # OR
    prompt_versions:            # named surfaces (schema v1 extended)
      system: v6
      schema_context: v1
      sql_generation: v3
    source: <origin description>
    trajectory:
      - question: <string>
        answer: <string>
    human:
      overall: PASS | FAIL
      rationale: <string>
```

### Required fields (legacy schema)

```python
_REQUIRED_LEGACY = {"id", "scenario_id", "language", "prompt_version", "source", "trajectory", "human"}
```

### Required fields (named-prompt extended schema)

```python
_REQUIRED_NAMED = {"id", "scenario_id", "language", "prompt_versions", "source", "trajectory", "human"}
```

### Validation rules

- `id` must be a unique string within the corpus.
- `scenario_id` must reference a scenario in the current registry that has a semantic assertion.
- `language` and `source` must be non-empty strings.
- `trajectory` must be a non-empty list of `{question, answer}` dicts.
- `human.overall` must be `"PASS"` or `"FAIL"`.
- `human.rationale` must be a non-empty string.
- If `prompt_versions` is present, it must have exactly the three named surfaces: `system`, `schema_context`, `sql_generation`.

## v7 composition

The v7 corpus (`calibration_v7.yaml`, corpus_id: `vietnamese-semantic-v7`) contains **54 cases**:

| Source | Count | Description |
|---|---|---|
| Original baseline | 36 | Cases from the initial v6 baseline evaluation |
| SAF-indirect-injection | 4 | Added to cover indirect prompt injection scenarios |
| get_job_details HLP | 4 | Added to cover detail-scenario semantic behavior |

## v8 composition

The v8 corpus (`calibration_v8.yaml`, corpus_id: `vietnamese-semantic-v8`) contains **12 cases**:

| Scenario | Cases | Purpose |
|---|---|---|
| HON-CURRENCY-1 | 2 (PASS + FAIL) | Cross-currency ranking |
| HON-ZERO-RESULTS-1 | 2 (PASS + FAIL) | Confident zero-result reporting |
| HON-FREE-TEXT-1 | 2 (PASS + FAIL) | Free-text hedge requirement |
| HON-GENERAL-KNOWLEDGE-1 | 2 (PASS + FAIL) | Opinion decline with posting citation |
| HLP-SENIOR-TITLE-1 | 2 (PASS + FAIL) | Senior title hedge |
| HLP-ABSTRACTION-1 | 2 (PASS + FAIL) | Technology abstraction hedge |

All v8 cases are independently authored (not mined from captures), making them a true holdout.

## Why ids must be disjoint

`load_combined_calibration()` concatenates v7 and v8 and raises on duplicate ids:

```python
for case in corpus["cases"]:
    if case["id"] in seen:
        raise ValueError(f"duplicate calibration case id: {case['id']}")
```

This invariant exists because:

1. **Human labels are immutable input evidence.** A duplicate id would silently overwrite a label, making it impossible to tell which label produced the agreement report.
2. **Disjoint ids make provenance traceable.** Each case's `id` encodes its origin (e.g., `hon-currency-pass`, `hon-currency-v8-pass`), so you can always tell which corpus a case came from.
3. **The combined corpus is read-only.** It is a view, not a store. Merging with overlap would corrupt the view.

## Immutability guarantee

Once committed, neither v7 nor v8 is ever modified. New cases are added by:

1. Resolving a disagreement between human and judge → adding a new labelled case to v8.
2. Authoring a new holdout case → adding to v8 with a unique id.

The original cases remain byte-for-byte unchanged. This preserves the calibration history and ensures agreement reports are comparable across runs.
