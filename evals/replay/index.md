# Replay

> **Source:** `evals/replay.py`, `evals/driver.py::freeze_capture()`, ADR-0046

## What replay is

A replay is a frozen, sanitized artifact that CI can reproduce without a serving model or judge call. It is produced by the `freeze` step, which projects a completed raw capture into a narrow schema.

## Freeze→sanitize→replay contract

The freeze pipeline (`evals/driver.py::freeze_capture()`):

1. **Sanitize** the raw capture: strip all external tracing linkage (trace IDs, dataset run IDs) using `_sanitize_capture_for_replay()`.
2. **Reject** any artifact containing forbidden content (credentials, trace IDs) using the `FORBIDDEN_CONTENT` regex.
3. **Validate** the grade report matches the capture's run_id.
4. **Project** into the replay schema with only the evidence needed for deterministic reproduction.
5. **Validate** the replay against `validate_replay()` before writing.

```python
# Forbidden content pattern (evals/sanitization.py)
FORBIDDEN_CONTENT = re.compile(
    r"postgres(?:ql)?://|api[_-]?key|authorization:|langfuse|trace[_-]?id|\bsk-[a-z0-9]",
    re.IGNORECASE,
)
```

## What replay retains and drops (per ADR-0046)

| Retained | Dropped |
|---|---|
| `run_id` | `trace_id`, `dataset_run_id` |
| `prompt_versions` (named surfaces) | Token usage, latency, finish reasons |
| `question`, `answer` | Tool output (may contain PII) |
| `tools_called` | Trace identifiers |
| `sql_text` | Langfuse-specific fields |
| `tool_arguments` | Telemetry |
| `expected_execution_accuracy` | |
| `expected_grade` | |

The freeze step refuses a capture that still carries a live trace identifier or cannot name its prompt.

## Replay schema

### Schema version 4 (current)

```python
REPLAY_SCHEMA_VERSION = 4
```

Records independently versioned prompt surfaces:

```json
{
  "manifest": {
    "run_id": "...",
    "schema_version": 4,
    "source_capture": "run.json",
    "sanitized": true,
    "prompt_versions": {
      "system": "v12",
      "schema_context": "v1",
      "sql_generation": "v13"
    }
  },
  "status": "COMPLETE",
  "scenarios": {
    "HLP-LIST-1": {
      "scenario_type": "single",
      "status": "COMPLETE",
      "repeats": [{
        "repeat": 1,
        "status": "COMPLETE",
        "turns": [{
          "turn": 1,
          "status": "COMPLETE",
          "expected_execution_accuracy": "PASS",
          "expected_grade": "PASS",
          "seams": {
            "question": "...",
            "answer": "...",
            "tools_called": ["query_clean_jobs"],
            "tool_output": "...",
            "tool_arguments": [...],
            "sql_text": "SELECT ..."
          }
        }]
      }]
    }
  }
}
```

### Legacy schema versions

Versions 2 and 3 preserve the legacy file-wide `prompt_version`. Historical artifacts keep their bytes and can still be replayed, but cannot be compared to named lineage one surface at a time.

## CI replay gate

```powershell
uv run python -m evals.replay --all
```

`run_active_replays()` discovers **every** artifact in `evals/replays/` and validates each one. A stale or newly added file fails loudly instead of being silently skipped. The gate:

1. Loads each replay JSON.
2. Validates schema, provenance, and forbidden content.
3. Re-runs execution accuracy and deterministic grading against the fixture.
4. Asserts expected outcomes match stored values.
5. Collects all failures across the set before reporting.

## Active replays

| File | Description |
|---|---|
| `t0025.9-committed.json` | Core committed replay (schema v4) |
| `iha251-hlp-abstraction-v10.json` | HLP abstraction scenario replay |
| `iha358-indirect-injection-v11.json` | SAF indirect injection replay |

## Archived replays

Historical captures preserved under `evals/archive/replays/` are no longer current regression evidence (the registry moved on). They keep their original bytes and provenance but are readable history, not active fixtures:

- `t0024.4-v3-obligations.json`
- `t0025.7-acceptance.json`
- `v6-baseline-20260823.json`
- `iha243-honesty-v9.json`
