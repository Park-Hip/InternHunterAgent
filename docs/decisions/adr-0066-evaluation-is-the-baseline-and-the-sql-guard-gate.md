# Evaluation is the baseline and the SQL guard gate

> **Status:** Active · **Decided:** 2026-10-26
>
> **Superseded in part by:** [ADR-0067](adr-0067-agent-run-milestones-and-deterministic-answer-checks.md), which replaces item 6 and allows an agent-run milestone
>
> **Supersedes:** [ADR-0041](adr-0041-scenario-registry-single-source-of-truth.md),
> [ADR-0042](adr-0042-grader-authority-at-calibration.md),
> [ADR-0043](adr-0043-deepeval-harness-kept-http-discarded.md),
> [ADR-0046](adr-0046-replays-retain-evidence-not-telemetry.md), and
> [ADR-0052](adr-0052-per-class-release-thresholds-real-sweep.md)

## Context

`python -m evals` still ran the harness built for the abandoned glossary agent:
50 scenarios written for a deleted prompt surface, DeepEval capture, a Gemma judge, calibration
corpora, August replays, and roughly 2,800 lines of manuals for deleted modules
([#758](https://github.com/Park-Hip/InternHunterAgent/issues/758), row 7 of
[#617](https://github.com/Park-Hip/InternHunterAgent/issues/617)).
It kept passing because the CI step re-scored a retained August capture, so it tested the harness,
not the agent.
The Claude sessions reading `evals/README.md`, `evals/pipeline.md`, and this directory could not
tell which parts were current.

The behavior baseline decided in #708 is a different instrument: 36 questions over a frozen
production snapshot, scored on the SQL they generate.
The #708 run already produced a 31/32 result without the scenario harness.
The judge was also not in use: `docs/reference/agent-behavior.md` records hand marking until hand
review becomes too slow.

## Decision

The evaluation instrument is the text-to-SQL baseline plus the credential-free SQL guard gate.
Both are plain Python, and neither calls a judge.

1. **Delete track C.** The v1 scenarios, capture-and-score runner, metrics, judge, report
   formatter, dataset registry, calibration corpora, replays, committed calibration runs,
   `archive/`, `pipeline.md`, `authoring/`, the observed scenario matrix, and their tests are
   removed. Git history is the archive.
2. **Drop DeepEval.** Its dependency, the `eval` pytest marker, and the CI replay step are
   removed. Judge-provider packages and keys used only by the deleted judge leave with it.
3. **Keep the baseline and the gate.** `baseline_sql.py`, `datasets/baseline.yaml`, the snapshot
   manifest, `sql_check.py`, the fixture loader and reader role, `sql_gate.py`, and
   `datasets/sql_guard.yaml` remain.
4. **Each dataset owns its own cases.** There is no cross-dataset scenario registry. The guard
   corpus is reviewed SQL statements; the baseline is questions with reference SQL and a split.
5. **The evaluation path is deterministic or offline.** The gate needs the fixture and no
   credential. The baseline generation needs a serving-model credential once, and every later
   scoring run is offline.
6. **Milestone runs stay, for the baseline only.** A baseline milestone run is one committed
   directory under `evals/runs/` with a lineage manifest, the generated SQL, and the recorded
   scores. `uv run python -m evals --rescore <run dir>` recomputes `sql_accuracy` from that
   evidence and refuses a mismatch. There is no agent-run milestone: the runner that captured
   turns was part of the deleted harness.

## What still holds from earlier records

- **ADR-0016 (three layers).** Outcome, trajectory, and component layers are still distinguished:
  the baseline measures SQL outcome, the gate pins the validator and executor boundary, and unit
  tests hold the component contracts. A wrong answer still reads differently from a routing or
  guard failure.
- **ADR-0017 (judge provider separate from serving).** No judge runs today, so the rule has no
  active subject. It stays the rule if a judge is reintroduced: a judge must not share the serving
  provider.
- **ADR-0018 (offline before online).** The offline baseline exists and remains the only
  evaluation; production-trace scoring, sampled goldens, and judge matrices stay out of scope.
- **ADR-0037 (frozen fixture baselines).** The seeded 24-row fixture and the frozen snapshot still
  fix the data a measurement reads.
- **ADR-0041 (one source of truth).** The principle survives per dataset: `sql_guard.yaml` owns
  the gate cases and `baseline.yaml` owns the baseline questions.
- **ADR-0042 (grader authority at calibration).** The calibration corpus and the judge are gone,
  so there is no handoff to administer. Reference SQL reviewed against the snapshot is the
  authority the baseline scores against.
- **ADR-0046 (replays retain evidence).** No replay remains to freeze. A baseline milestone run
  saves its generated SQL and prompt hashes so it can be re-scored without a model call, which is
  the part of the record that still applies.
- **ADR-0052 (per-class release thresholds).** The corpus and the judge it measured are deleted,
  so no threshold is enforced. A future release bar is a new decision with its own evidence.

## Consequences

- `uv run python -m evals` runs the SQL guard gate.
  `evals/README.md` and [the evaluate how-to](../how-to/evaluate.md) describe only the gate, the
  baseline, and the fixture.
- CI no longer re-scores a capture.
  The `checks` job runs the offline suite, and the separate `sql-guard-gate` job loads the fixture,
  runs the gate's own tests, and then runs the gate.
- The `scenario-id` documentation check is deleted with the registry it read.
  Documents no longer name `HLP-`, `HON-`, or `SAF-` cases as live references.
- The replay-backed milestone run added in #757 is deleted, because replay capture left with the
  harness. The baseline milestone run `evals/runs/2026-10-19-baseline-v1/` remains committed.
- `config/settings.yaml` keeps `eval.fixture` and drops `eval.judge` and `eval.capture`.
  The unused Groq, Google, and OpenRouter settings fields and their judge-only packages are
  removed.
- The judge-dependent docs in `docs/reference/configuration.md` and
  `docs/modules/model-config.md` now name the baseline or the gate instead.

## Verification

| Check | Method | Expected result |
| --- | --- | --- |
| The deleted modules are gone | `git grep -n "evals\.\(run\|metrics\|judge\|report\|datasets\)\b\|calibration_v[78]\|deepeval"` | Nothing outside historical records |
| The suite passes | `uv run pytest` | Green |
| Docs resolve | `uv run python scripts/docs_lint.py` | Exit 0 |
| The gate still gates | `uv run python -m evals` against the loaded fixture | Every reviewed case passes |
| The baseline is untouched | `uv run python -m evals.baseline_sql score <run> --database-url <snapshot URL>` | The recorded pass counts reproduce |

## Rollback

Revert this change.
The deleted files remain in git history, and no migration, stored state, or external contract is
involved.

## Superseded in part

[ADR-0067](adr-0067-agent-run-milestones-and-deterministic-answer-checks.md) replaces item 6 of this
record: an agent-run milestone is now allowed.
The rest of this record remains active.
