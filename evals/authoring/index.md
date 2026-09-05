# Authoring Scenarios

> **Source:** `evals/scenarios.py`, `evals/scenarios_v1.yaml`

## Authoring grammar

Every scenario in `scenarios_v1.yaml` must conform to this grammar, enforced by `load_scenarios()`.

## Seven required keys

| Key | Type | Constraint |
|---|---|---|
| `id` | string | Matches `(SAF|HON|HLP)-[A-Z]+(?:-[A-Z]+)*-[1-9][0-9]*` |
| `name` | string | Non-empty |
| `requirements` | list of strings | Each matches `G[0-9]{2}` |
| `decision` | int or null | Requirement decision index |
| `type` | string | `"single"` or `"conversational"` |
| `expected` | string | Non-empty expected behavior description |
| `probe` | boolean | Whether this is a probe scenario |
| `expected_tools` | list of strings | Must be from `{"query_clean_jobs", "get_job_details"}` |

## Id pattern

```python
_SCENARIO_ID_PATTERN = re.compile(r"(SAF|HON|HLP)-[A-Z]+(?:-[A-Z]+)*-[1-9][0-9]*")
```

- Class prefix: `SAF`, `HON`, or `HLP`
- Behavior descriptor: one or more UPPERCASE words
- Sequence number: `[1-9][0-9]*` (no leading zero)

Examples: `HLP-LIST-1`, `SAF-INJECTION-REFUSAL-1`, `HON-NEGOTIABLE-SALARY-1`

## Type and turns

Exactly one of `input` (single-turn) or `turns` (multi-turn) is required:

```yaml
# Single-turn
- id: HLP-COUNT-1
  type: single
  input: "Có bao nhiêu việc làm Python?"

# Conversational
- id: HLP-CONTEXT-1
  type: conversational
  turns:
    - "Tìm việc Python ở Hà Nội"
    - "Chỉ giữ lại Python thôi"
```

Conversational scenarios require a non-empty list of string turns.

## Repeat counts

```python
def repeat_count(scenario: dict[str, Any]) -> int:
    return 3 if scenario["probe"] else 2
```

| `probe` | Repeats | Purpose |
|---|---|---|
| `true` | 3 | Probe scenarios — extra determinism check |
| `false` | 2 | Standard scenarios |

## Three assertion types

Assertions live under `grading.assertions`:

```yaml
grading:
  assertions:
    - type: literal
      required_patterns: [...]
      forbidden_patterns: [...]
      expected_answer_count: 5
      count_only: true
    - type: structural
      require_vietnamese: true
      require_source_links: true
      reject_salary_period: true
      preserve_returned_job_levels: true
      reject_title_to_level_inference: true
      reject_lifecycle_substitution: true
      required_any: [[...], [...]]
      forbidden_any: [...]
    - type: semantic
      required_any: [[...]]
      forbidden_any: [...]
      forbid_single_salary_winner: true
```

### Literal assertion fields

| Field | Type | Description |
|---|---|---|
| `expected_answer_count` | int | Expected number in the answer |
| `count_only` | bool | Answer must be one declarative sentence |
| `forbidden_patterns` | list of regex strings | Patterns that must NOT appear |
| `required_patterns` | list of regex strings | At least one pattern per group must match |

Terms can be:
- Exact strings: `"not available"`
- Glossary references: `{glossary: CREATED_ON_NOT_POSTED_WORDING}`
- Lexicon lists: `{lexicon: ["không có trong", "database"]}`

### Structural assertion fields

| Field | Type | Description |
|---|---|---|
| `require_vietnamese` | bool | Check prose purity (no English words) |
| `require_source_links` | bool | Check source URLs are labelled |
| `reject_salary_period` | bool | Reject salary+period pairing |
| `preserve_returned_job_levels` | bool | Reported levels must match canonical values |
| `reject_title_to_level_inference` | bool | "Senior" title cannot map to structured level |
| `reject_lifecycle_substitution` | bool | Absent deadline cannot be replaced by lifecycle dates |
| `required_any` | list of list of terms | OR within group, AND across groups |
| `forbidden_any` | list of terms | Any match = FAIL |

### Semantic assertion fields

| Field | Type | Description |
|---|---|---|
| `required_any` | list of list of terms | Behavioral requirements |
| `forbidden_any` | list of terms | Forbidden behaviors |
| `forbid_single_salary_winner` | bool | Must not declare a single global salary winner |

## Seven execution comparison kinds

```python
_EXECUTION_COMPARISONS = {
    "exact",              # Multiset equality of rows
    "contains_reference", # Generated rows must include all reference rows
    "ids_only",           # Generated IDs must match reference IDs
    "limited_ids",        # Same as ids_only but respects 20-row display cap
    "aggregate_count",    # COUNT must match
    "zero_results",       # Generated query must return zero rows
    "cross_currency",     # Grouped by currency, ID sets must match per group
}
```

Declared per-scenario under `grading.execution_comparison`. Validation rejects incompatible combinations (e.g., `ids_only` without `id` in reference SQL).

## Execution accuracy exemption

Scenarios without a SQL contract declare:

```yaml
execution_accuracy_exempt:
  reason: "Pure refusal — no tool call expected"
```

Or provide `reference_sql` instead. Exactly one of `reference_sql` or `execution_accuracy_exempt` is required.

## Tool expectations

### Top-level tool expectation

```yaml
expected_tools: [query_clean_jobs]
```

### Per-turn tool expectation (conversational only)

```yaml
turn_tool_expectations:
  - required: [query_clean_jobs]
    allowed: [query_clean_jobs, get_job_details]
  - required: []
    allowed: []
```

Required tools must be a subset of allowed tools.

## Step-by-step runbooks

### Add a new scenario

1. Add to `evals/scenarios_v1.yaml` with all seven required keys.
2. Validate: `uv run python -m evals.scenarios --scenario NEW-ID`
3. Add calibration cases to `calibration_v8.yaml` if semantic assertion exists.
4. Re-run baseline: `uv run python -m evals.driver --output evals/runs/new.json`
5. Grade: `uv run python -m evals.grader --run evals/runs/new.json --execution-accuracy evals/runs/new-execution.json --output evals/runs/new-grade.json`
6. Score: `uv run python -m evals.score --run evals/runs/new.json`
7. Freeze: `uv run python -m evals.driver freeze evals/runs/new.json --grade evals/runs/new-grade.json -o evals/replays/new.json`

### Modify an existing scenario

1. Edit `evals/scenarios_v1.yaml`.
2. Bump prompt version if behavioral requirements changed.
3. Re-run validation and full baseline.
4. Update calibration cases if the semantic assertion changed.
5. Re-freeze any affected replays.
