# Evaluate agent behavior

The harness has one scenario dataset and one credential-free gate.

| Dataset | What it describes | How it runs |
| --- | --- | --- |
| `default` | The v1 scenarios, preserved as evidence for the replays | A live capture against the serving agent, or a retained capture |

The SQL guard gate reads its own reviewed corpus rather than a capture dataset, so it is not in the registry above.
It persists one JSON artifact whose `by_metric` key groups every scored row under its metric name, and prints the same grouping as a table.
Historical v1 replay, calibration, and instrument documents remain on disk as evidence, not as current operating instructions.

## The SQL guard gate

This is the gate.
It needs the fixture database and nothing else: no serving model, no judge, no secret, and no network.
It is the successor ADR-0060 required when it retired the v0 acceptance gate.

```sh
docker compose up -d postgres
uv run python -m evals.fixtures.loader
uv run python -m evals --gate
```

It runs every reviewed case in [`evals/datasets/sql_guard.yaml`](../../evals/datasets/sql_guard.yaml) through the same pipeline the tool uses - `validate_sql`, `resolve_bounds`, then the fixture - and scores two deterministic metrics:

| Metric | Grades |
| --- | --- |
| `guard_correctness` | The `validate_sql` verdict against the reviewed one. A rejected case also pins the rule that must reject it, so widening the validator cannot quietly drop the guard's floor |
| `result_equivalence` | The rows the reviewed SQL returns on the fixture, against a reviewer-written reference, through `evals/sql_check.py` |

The corpus has 15 cases in five classes: `reviewed` questions the guard must accept, the guard's floor (`hidden` and `cost` statements that must stay rejected), `ambiguous` accepted risks (A01-A03) that pin today's behavior and name the risk, and one injection carried by posting text.
An accepted risk is a case, not prose: a guard that starts refusing one turns the gate red and the [ADR-0060 risk table](../decisions/adr-0060-retire-the-agent-v0-bundle.md) has to move with it.

**The gate fails rather than skips.** If the fixture database is unreachable it exits 2 with a message naming the command that starts it. An unavailable database reported as green is the failure mode this gate exists to remove.

### What the gate refuses to accept

| Condition | Why it fails |
| --- | --- |
| A verdict other than the reviewed one | The reviewed statement is the case's assertion; reviewed SQL the guard rejects, or forbidden SQL it accepts, is a defect |
| A rejected case rejected by a different rule | The floor is a pass/fail condition: the self-join, `pg_sleep`, multi-table, and hidden-column rules must each still reject their own case |
| A result other than the reviewed one | The reference was reviewed, and `tests/evals/test_sql_gate.py` pins the gate's grading and its refusals |

The gate is deliberately stricter than a rate. A percentage would let a false success be offset by an easy pass. If a future maintainer wants a rate, that is a new decision with its own evidence.

The cross-currency false-success class used to be graded here through the obligation detector, which [#702](https://github.com/Park-Hip/InternHunterAgent/issues/702) deleted with the caveat machinery.
That risk now belongs to the `sql_generation` rule that every salary aggregate groups by `salary_currency`, and the Layer 1 baseline measures it; R05, R06, and A02 keep the statement shapes visible.

### The judge metrics are not the gate

`grounded`, `on_topic`, and `rubric` need a judge credential, cost money, and are not reproducible run to run, so they are run deliberately by a maintainer against a recorded capture. A run without a judge credential reports them as not evaluated, never as passing. A release threshold for the served agent is a maintainer decision and is not set here.

### Metrics the governed path never scored

The Stage 4 decision (#487) kept `sql_accuracy` and `memory` out of the governed v0 path, which wrote
no SQL and was single-turn, so there was no SQL string to score and no memory to score.
Both names remain in the registry because the v1 scenarios declare them, and the path that could not
declare them is retired.

## Live evaluation of the v1 scenarios

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
A deterministic metric that is not exactly 1.0 exits nonzero. That is the default, not an opt-in: the table above you and the shell exit code must not disagree.
Asking for a metric that the selected scenarios do not declare is an error, not an empty report. `uv run python -m evals --only sql_accuracy --ids SAF-DESTRUCTIVE-REFUSAL-1` names the metric and exits nonzero rather than printing nothing and passing.
`--allow-fail` turns a below-threshold deterministic score back into a printed finding for exploratory runs. It does not excuse a metric that could not be evaluated: errors, unrun cases, and infrastructure failures exit nonzero in every mode.
Judge metrics stay reported-only. A judge score is continuous in `[0, 1]`, so requiring 1.0 of it would fail every run and prove nothing; no judge threshold is configured yet.
The fixture loader still exports `fixture_database_url()` for other research scripts.

To compare the 12 preserved v8 human labels with the current judge once credentials are available, run `uv run pytest -o addopts='' -m eval -s tests/evals/test_holdout_judge.py`.
Disagreements are printed as findings for the dataset redesign, not hidden or treated as calibrated thresholds.

See [`evals/archive/Instrument_Report.md`](../../evals/archive/Instrument_Report.md) for historical baseline context, not current scores.
