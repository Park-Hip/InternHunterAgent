# Evaluate agent behavior

The active evaluation harness reads scenarios from [`evals/datasets/scenarios.yaml`](../../evals/datasets/scenarios.yaml).
It persists one JSON artifact whose `by_metric` key groups every scored row under its metric name, and prints the same grouping as a table.
Historical v1 replay, calibration, and instrument documents remain on disk as evidence, not as current operating instructions.

## Live evaluation

Start the fixture database and rebuild it before capturing agent behavior:

```sh
docker compose up -d
uv run python -m evals.fixtures.loader
uv run python -m evals --dataset default --out evals/runs/local-report.json
```

Live capture requires a configured serving-model credential.
The `grounded`, `on_topic`, `memory`, and `rubric` metrics additionally require the configured judge credential.
Each selected scenario is captured once and scored on its applicable metrics.
Use `--ids HLP-LIST-1,SAF-INDIRECT-INJECTION-1` to narrow a run, or `--only tool_correctness,sql_accuracy` to omit the judge.
Omitting the judge does **not** remove the serving-model credential requirement for a live capture.

## Credential-free deterministic check

Use `--capture` to score retained, previously captured evidence without calling a provider:

```sh
uv run python -m evals --only tool_correctness,sql_accuracy --capture evals/replays/t0025.9-committed.json --ids SAF-DESTRUCTIVE-REFUSAL-1,HLP-CONTEXT-1
```

Only scenarios actually present in the retained capture are scored.
The fixture database is required whenever the captured scenario has reference SQL.
This CI smoke check is not a new capture and does not cover all 50 scenarios.
Scores of 0.0 are findings rather than infrastructure failures; errors, unrun cases, and infrastructure failures exit nonzero.
A metric that cannot be scored for a captured turn is reported as a row with a null score and a `NOT_APPLICABLE` reason rather than being dropped: that happens today for `grounded` whenever a turn captured no tool output.
`--require-pass` additionally exits nonzero for any metric that is not exactly 1.0, including those null scores.
The fixture loader still exports `fixture_database_url()` for other research scripts.

To compare the 12 preserved v8 human labels with the current judge once credentials are available, run `uv run pytest -o addopts='' -m eval -s tests/evals/test_holdout_judge.py`.
Disagreements are printed as findings for the dataset redesign, not hidden or treated as calibrated thresholds.

See [`evals/Instrument_Report.md`](../../evals/Instrument_Report.md) for historical baseline context, not current scores.
