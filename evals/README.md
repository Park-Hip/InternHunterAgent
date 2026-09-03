# `evals/` - The Evaluation Instrument

> **Last verified:** 2026-08-26.

> **Eviction:** This guide leaves when the evaluation commands, evidence contract, or result terms change.

This directory measures the agent against the frozen fixture and the behavior contract.
Read the [Operating Manual](Operating_Manual.md) after this guide for review rules and authority limits.
Read the [Instrument Report](Instrument_Report.md) for the current baseline results.

## Start here

The registry in [`scenarios_v1.yaml`](scenarios_v1.yaml) is the single source of truth for the evaluation scenarios.
The frozen target is [`docs/reference/agent-behavior.md`](../docs/reference/agent-behavior.md).
Open evaluation issues are tracked on GitHub; see [CONTRIBUTING.md](../CONTRIBUTING.md) for the change workflow.

The named runtime environment must contain the normal application configuration, including `DATABASE_URL` and
`AGENT_DATABASE_URL`; runtime settings fail closed without them. The values may point at the local
`docker compose` database because the driver replaces `DATABASE_URL` with the fixture DSN before it imports
the agent, so a capture does not query a serving database.
The evaluator also needs the serving-provider credentials for capture and the judge-provider credentials for semantic scoring.

Raw captures under `evals/runs/` are local and ignored by Git because they can contain telemetry, trace identifiers, and tool output.
Committed replays under `evals/replays/` are sanitized evidence that CI can reproduce without a serving model or judge call.
The replay gate discovers and validates **every** artifact in `evals/replays/`, so a stale or newly added file fails loudly instead of being silently skipped:

```powershell
uv run python -m evals.replay --all
```

Historical replays cited as durable evidence but no longer valid against the current registry are preserved byte-for-byte with their provenance in [`archive/replays/`](archive/replays/README.md).
They are readable history, not active regression fixtures.

## Evaluation vocabulary

| Term | Meaning |
|---|---|
| Scenario | One registry-defined behavior case, such as `HON-CURRENCY-1`. |
| Repeat | One independent run of a scenario. Probes run three repeats and other scenarios run two. |
| Turn | One user question and answer inside a repeat. Conversational scenarios contain more than one turn. |
| Seam | An evidence point inside a turn: routing, SQL generation, or answer synthesis. |
| Capture | The only serving-model step. `driver.py` runs the current registry and checkpoints a raw artifact after each turn. |
| Execution accuracy | The fixture-backed check that compares generated SQL with registry reference SQL by the scenario's declared contract. |
| Grade | The deterministic structural and literal verdict produced from recorded evidence. It never calls a model. |
| Semantic score | A separate judge-model result for a semantic assertion. It is diagnostic until the maintainer authorizes its calibrated use. |
| Freeze | Projection of a completed raw capture into a replay after sanitization and deterministic grading. |
| Replay | The no-model, no-judge execution of a committed frozen artifact against the fixture. |
| Baseline eligible | A clean-tree capture with prompt, registry, fixture, provider, and sampling lineage. It is comparable only with an artifact that preserves the same contract. |

## Result terms

`PASS` means the evaluated deterministic checks passed.
`FAIL` means a check under the agent's control failed.
`INFRA` means required evidence is missing because infrastructure failed, such as a quota or provider failure.
`UNRUN` means the turn or scenario was never attempted.
`NOT_EVALUATED` is a check-level outcome, not a turn verdict.
It means the check did not apply to the available evidence, such as SQL execution after an earlier routing failure produced no SQL.
`EXEMPT` is an execution-accuracy result for a scenario that has no SQL contract, such as a pure refusal.
`AVAILABLE` and `UNAVAILABLE` describe whether the semantic judge returned a usable result.

`INFRA` and `UNRUN` do not enter pass-rate denominators.
`NOT_EVALUATED` never turns an applicable failure into `INFRA` or `PASS`.

## Run the complete baseline workflow

Start the fixture and run the deterministic suite.

```powershell
docker compose up -d
uv run python -m evals.fixtures.loader
uv run pytest -q tests/evals
```

Capture from a committed, clean worktree only.

```powershell
uv run python -m evals.driver --output evals/runs/<run>.json
```

Grade the captured evidence without a model call.

```powershell
uv run python -m evals.execution_accuracy evals/runs/<run>.json --output evals/runs/<run>-execution.json
uv run python -m evals.grader --run evals/runs/<run>.json --execution-accuracy evals/runs/<run>-execution.json --output evals/runs/<run>-grade.json
```

Run the semantic scorer after capture, not inside it.

```powershell
uv run python -m evals.score --run evals/runs/<run>.json
```

The scorer writes results into the ignored raw capture and can resume after an interruption.
It spends judge quota and can take about an hour for a full registry because it deliberately throttles judge calls.
It does not overwrite a human calibration label or alter the deterministic grade.

Score the calibration corpus with the real judge and emit the per-class agreement report.
This is the supported writer of calibration judge evidence (`evals/runs/*-judge-scores.json` plus the
agreement report); it is resumable and never writes back into the human labels.

```powershell
uv run python -m evals.calibration_score --corpus v7 --corpus v8 --out evals/runs/iha-v8-judge-combined-judge-scores.json
uv run python -m evals.calibration_score --agreement-of evals/runs/iha-v8-judge-combined-judge-scores.json --out evals/runs/iha-v8-judge-combined-agreement-report.json
```

The agreement report selects one release threshold per class (SAF/HON/HLP plus the pooled overall bar)
recall-first, and reports precision, false-pass counts, and 95% Wilson intervals. The live gate
(`uv run pytest -m eval -v`) enforces exactly those per-class bars against the combined corpus.

> **Release-gate invocation policy** — The bounded live semantic gate runs **only on manual dispatch**
> via GitHub Actions `workflow_dispatch`.  It is **never auto-invoked** on PRs, merges, or tag pushes.
> Deterministic checks (fixtures loader, replay, grading) run on every change via the `checks` CI job.
> Per-class thresholds per [ADR-0052](../docs/decisions/adr-0052-per-class-release-thresholds-real-sweep.md):
> `SAF >= 1.0`, `HON >= 1.0`, `HLP >= 0.5` (recall-first).

Freeze the capture, replay it, and generate a local viewer.

```powershell
uv run python -m evals.driver freeze evals/runs/<run>.json --grade evals/runs/<run>-grade.json -o evals/replays/<run>.json
uv run python -m evals.replay --replay evals/replays/<run>.json
uv run python -m evals.viewer evals/runs/<run>.json --grade evals/runs/<run>-grade.json --execution-accuracy evals/runs/<run>-execution.json
```

`grader --output` writes UTF-8 JSON directly.
Use it instead of PowerShell `>` redirection because that redirection can write UTF-16 and make the freeze step unreadable.

## Pipeline and authority

```text
registry -> capture -> execution accuracy -> deterministic grade -> freeze -> replay
                   \-> semantic score ---------------------------> human review
```

Capture is the only serving-model call.
Semantic scoring is a later judge-model call over recorded evidence.
Execution accuracy, deterministic grading, freezing, replay, and viewing are local operations.

Structural checks take precedence over literal and semantic checks.
During calibration, a human label wins over the judge and any disagreement becomes a new labelled case.
After a maintainer accepts the published calibration and authorizes a stated use, the calibrated grader may own that stated use.
The current metric must not be read as a production release gate unless that authorization is recorded.

## Deterministic wording contract

Refusal and zero-result scenarios carry their acceptance rule as a structural text rule, not as judge-only criteria.
Each rule holds the canonical glossary anchors plus an explicit list of equivalent phrasings, so a correct refusal or zero-result answer passes even when its wording sits outside the canonical sentence.
The accepted equivalents are evidence-led: every phrase names a reviewed example, currently from [`t0027_deepseek_arm.md`](t0027_deepseek_arm.md), the committed calibration corpus, and the v6 baseline.

The contract stays narrow on purpose.
An answer that claims it performed a mutation, fabricates results where none exist, or excuses itself with a database error matches none of the accepted phrases and still fails deterministically.
Every accepted phrase keeps a focused negative test in `tests/evals/test_grader.py` protecting that boundary.
Widen a rule only through a proposal; registry lexicon entries live in [`scenarios_v1.yaml`](scenarios_v1.yaml) next to the assertion they belong to.

## Files

| File | Role |
|---|---|
| `scenarios_v1.yaml` | Registry-owned questions, repeats, tool expectations, execution contracts, and assertions. |
| `driver.py` | Captures, checkpoints, records lineage, and freezes sanitized replays. |
| `execution_accuracy.py` | Compares generated and reference SQL against the frozen fixture. |
| `grader.py` | Produces independent deterministic check outcomes and the first failing seam. |
| `score.py` | Runs the resumable judge pass over a recorded capture. |
| `calibration.py` | Loads, merges, sweeps, and reports the versioned human-labelled corpora; owns the per-class release thresholds. |
| `calibration_v7.yaml` / `calibration_v8.yaml` | Immutable, human-labelled Vietnamese semantic corpora (v7 = calibration, v8 = independent holdout). |
| `calibration_score.py` | Resumably scores the corpora with the real judge and emits judge-scores + agreement-report artifacts. |
| `holdout.py` | Compatibility + independent-holdout view over the versioned corpora. |
| `replay.py` | CI's provider-free replay gate. Discovers every artifact in `replays/`. |
| `viewer.py` | Local HTML evidence viewer. |
| `Instrument_Report.md` | Dated baseline, calibration, disagreement, and unresolved-case record. |
| `Operating_Manual.md` | Maintainer review and disagreement workflow. |

## Manual completion check

For a baseline, verify all of the following before requesting maintainer acceptance.

1. The capture manifest is clean and `baseline_eligible: true`.
2. Every scenario and required repeat completed, or the report identifies the `INFRA` and `UNRUN` coverage gap.
3. The deterministic report, frozen replay, and replay run agree on each stored outcome.
4. The viewer has been inspected for one refusal, one zero-result answer, one conversational scenario, and one SQL mismatch.
5. The semantic result is `AVAILABLE` or the report names why it is `UNAVAILABLE`.
6. Every human and judge disagreement has a documented disposition.
7. The report states the metric's authorized use, or explicitly states that no authorization exists.
