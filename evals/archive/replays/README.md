# Preserved historical replays

The artifacts in this directory are **preserved evidence, not active regression fixtures**.
They keep their original bytes exactly as committed; nothing here is re-captured, edited,
or deleted. They no longer validate against the current registry and are therefore kept
outside [`evals/replays/`](../../replays/) so the active replay directory only ever holds
artifacts that CI can reproduce against the current scenario set (issue #148, resolved by #249).

| Artifact | Prompt | Captured | Why it was preserved |
|---|---|---|---|
| [`t0024.4-v3-obligations.json`](t0024.4-v3-obligations.json) | v3 | T0024.4 | First replay of the obligation-refusal scenarios; English capture graded against Vietnamese glossary anchors after T0033.2. |
| [`t0025.7-acceptance.json`](t0025.7-acceptance.json) | v1 | T0025.7 | The T0025.7 acceptance capture, including the recorded cross-currency failure in `HON-CURRENCY-1`. |
| [`v6-baseline-20260823.json`](v6-baseline-20260823.json) | v6 | 2026-08-23 baseline run | Baseline evidence for the v6 prompt lineage; contains a scenario id retired from the registry since capture. |

Each file's own manifest (`run_id`, `schema_version`, `source_capture`, `sanitized`,
`prompt_version`) is the authoritative provenance record for that artifact.

## Reading an archived artifact

These artifacts can still be loaded and inspected without a model call:

```powershell
uv run python -c "from evals.replay import load_replay; from pathlib import Path; import json; print(json.dumps(load_replay(Path('evals/archive/replays/t0024.4-v3-obligations.json'))['manifest'], indent=2))"
```

They will fail `validate_replay` by design when questions or scenario ids have drifted from
the frozen registry; that failure is the historical record, not a defect to fix in place.
Current regression evidence lives only in `evals/replays/`.
