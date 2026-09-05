# Evaluate agent behavior

> **Eviction:** This pointer leaves when the evaluation instrument is retired or replaced.

How to run, inspect, calibrate, and publish evidence from the evaluation harness.

The evaluation harness measures the agent against a frozen fixture and a behavior contract.
Layout, commands, and operating limits are documented in the evaluation instrument itself:

- [`evals/README.md`](../../evals/README.md) — navigation hub: role routing, decision tree, quick commands, full file map.
- [`evals/pipeline.md`](../../evals/pipeline.md) — the five-step pipeline (capture → execution accuracy → deterministic grade → freeze → replay), the result-term table, and the step-by-step run commands.
- [`evals/Operating_Manual.md`](../../evals/Operating_Manual.md) — maintainer review rules, authority boundary, and outcome interpretation.

## What it is for

The harness establishes a measurable baseline of task correctness and the honesty bar **before**
any work whose design depends on measured model behavior is built. Evaluation measures behavior;
it does not fix it. Remediation is separate work.

## Where the details live

| Question | Document |
|---|---|
| What are the three seams (routing / NL→SQL / synthesis)? | [`evals/deterministic/index.md`](../../evals/deterministic/index.md) |
| What does the semantic judge measure, and on what provider? | [`evals/semantic/index.md`](../../evals/semantic/index.md) |
| How are thresholds calibrated, and what bars does the gate enforce? | [`evals/calibration/thresholds.md`](../../evals/calibration/thresholds.md) |
| How do I author a new scenario? | [`evals/authoring/index.md`](../../evals/authoring/index.md) |
| How does the no-model replay gate work? | [`evals/replay/index.md`](../../evals/replay/index.md) |
| How are grader/judge/human disagreements resolved? | [`evals/disagreements/index.md`](../../evals/disagreements/index.md) |
| Which test pins which behavior? | [`tests/evals/`](../../tests/evals/) — test-to-module mapping |
| What is the current baseline and open cases? | [`evals/Instrument_Report.md`](../../evals/Instrument_Report.md) |
