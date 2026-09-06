# Execution Accuracy — Layer 1

> **Source:** `evals/execution_accuracy.py`

Layer 1 of the cascade compares the agent's generated SQL against a **reference SQL** defined
in the scenario registry. The comparison contract is declared per-scenario and comes in
**7 modes**. This layer is fully deterministic — no model call, no provider dependency.

## Comparison modes

| Mode | What it checks | Scenarios |
|---|---|---|
| `exact` | Generated rows must exactly match reference rows (multiset equality) | HLP-LIST-1, HLP-DETAIL-3/4/7, HLP-COMPOUND-1, most list/detail scenarios |
| `ids_only` | Generated IDs must match reference IDs (ignores other columns) | HON-CURRENCY-1 (partial), some multi-tool scenarios |
| `limited_ids` | Same as ids_only but respects the 20-row display cap | HLP-TRUNCATION-1 |
| `contains_reference` | Generated rows must include all reference rows (superset allowed) | Some retrieval scenarios |
| `aggregate_count` | Generated query must return the same COUNT as reference | HLP-COUNT-1, HLP-TECH-STACK-1, HON-PREMISE-CORRECTION-1 |
| `zero_results` | Generated query must return zero rows (reference returns zero) | HON-ZERO-RESULTS-1, HLP-DETAIL-5 |
| `cross_currency` | Generated rows grouped by currency must contain same ID sets as reference | HON-CURRENCY-1 (full scenario) |

## How it works

`execution_accuracy.py` executes both the generated SQL and reference SQL against the **same
fixture database** using SQLAlchemy. It builds `Counter` multisets of rows (or IDs) and
compares them. For `cross_currency`, it groups rows by `salary_currency` and compares ID sets
per group.

### Key design decisions

- **Reference SQL is written by hand** in `scenarios_v1.yaml` — it's the ground-truth query.
- **EXEMPT** status for scenarios with no SQL contract (pure refusals, off-topic redirects).
- **NOT_EVALUATED** when no SQL was generated (routing failure means SQL check can't run).
- **Projection checks** verify the agent selected the right columns (e.g., `id` must be first).

## Execution accuracy exemption

Scenarios without a SQL contract declare:

```yaml
execution_accuracy_exempt:
  reason: "Pure refusal — no tool call expected"
```

Or provide `reference_sql` instead. Exactly one of `reference_sql` or `execution_accuracy_exempt`
is required per scenario.

## Common failure modes

| Failure | Cause | Example |
|---|---|---|
| Wrong table/column | Agent searches `tech_stack`/`description` instead of `role` for job-title queries | HLP-LIST-1: returned 13 rows instead of 5 |
| Extra filters | Agent adds unsolicited filters not in reference SQL | "machine learning" filter on "all jobs" |
| LIMIT mismatch | Agent applies LIMIT when reference doesn't | Count queries returning rows instead of COUNT(*) |
| Currency filtering | Agent filters to one currency instead of grouping | HON-CURRENCY-1: returns only VND rows |
| Missing JOIN | Agent doesn't join required tables for multi-field queries | Detail scenarios with missing columns |

## Command

```powershell
uv run python -m evals.execution_accuracy evals/runs/<run>.json --output evals/runs/<run>-execution.json
```

## Tests

- `tests/evals/test_execution_accuracy.py` (~540 lines) — Unit tests for all 7 SQL comparison modes
