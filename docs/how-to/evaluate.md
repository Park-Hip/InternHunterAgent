# Evaluate agent behavior

The harness has two datasets and two ways to run them.

| Dataset | What it describes | How it runs |
| --- | --- | --- |
| `default` | The v1 scenarios, preserved as evidence for the replays | A live capture against the serving agent, or a retained capture |
| `v0` | The 16 governed v0 acceptance cases, derived from [the v0 contract](../../docs/refactor/agent-v0-contract.md) | The credential-free gate, which calls the query core directly |

It persists one JSON artifact whose `by_metric` key groups every scored row under its metric name, and prints the same grouping as a table.
Historical v1 replay, calibration, and instrument documents remain on disk as evidence, not as current operating instructions.

## The v0 acceptance gate

This is the gate. It needs the fixture database and nothing else: no serving model, no judge, no secret, and no network.

```sh
docker compose up -d postgres
uv run python -m evals.fixtures.loader
uv run python -m evals --deterministic --dataset v0
```

It scores two deterministic metrics over all 16 cases:

| Metric | Grades |
| --- | --- |
| `plan_correctness` | The criteria the core applied, against the case's reviewed plan. A city the user typed as `Hà Nội` has to be applied as the stored `Hanoi`, and `ML` as the stored `Machine Learning` |
| `result_equivalence` | Row ids, aggregates, the full match total, the answer state, and the required evidence labels, against the golden |

Three cases have no request at all, because the contract's answer for them is not a query: a missing application deadline, a subjective request, and a destructive request. Their correctness claim is structural, and the gate proves it by checking that no visible column, no filter field, and no query shape can express the refused capability. A refusal that rested on prose would not be testable; the absence of a field for it is.

**The gate fails rather than skips.** If the fixture database is unreachable it exits 2 with a message naming the command that starts it. An unavailable database reported as green is the failure mode this track exists to remove.

### What the gate refuses to accept

| Condition | Why it fails |
| --- | --- |
| A false success | A confidently wrong answer is never paid for by an easy pass, whatever the rate |
| A false refusal | A refused answer the contract requires is a defect, not a conservative success |
| A plan that differs from the reviewed one | The plan is the interpretation; a right number from a wrong plan is luck |
| A result, state, or evidence label that differs | The golden was reviewed, and the goldens are separately recomputed from the fixture by `tests/evals/test_v0_acceptance.py` |
| Fewer than 16 executable cases | Coverage is a pass/fail condition, not a percentage |

The gate is deliberately stricter than a rate. A percentage would let a false success be offset by an easy pass. If a future maintainer wants a rate, that is a new decision with its own evidence, and it would still not apply to the false-success class.

### The judge metrics are not the gate

`grounded`, `on_topic`, and `rubric` need a judge credential, cost money, and are not reproducible run to run, so they are run deliberately by a maintainer against a recorded capture. A run without a judge credential reports them as not evaluated, never as passing. A release threshold for the served agent is a maintainer decision and is not set here.

### Retired metrics on the governed path

`sql_accuracy` and `memory` are retired for the v0 path and remain for the v1 replays.
[#487](../../docs/refactor/agent-v0-sql-decision.md) decided a no-go on guarded SQL, so there is no SQL string to score, and v0 is single-turn, so there is no memory to score.
A v0 case that declares either is rejected when the dataset loads.

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
