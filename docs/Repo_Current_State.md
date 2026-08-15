# Repository Current State

> **Last verified:** 2026-08-15 against the checked-out commit, active registers, and
> [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

- Repository baseline: `main` at `5ebbe33`, which merged M25 and M26 as PR #48 on 2026-08-15.
  PR #47 was closed as superseded: every commit it carried was already contained in #48.
- Active ticket branch: `feature/t0029-viewer-readability`, branched from the merged M28 work.
- The M29 branch is checked out in the worktree `.claude/worktrees/t0029-viewer-readability`; the
  M28 branch remains in `.claude/worktrees/t0028-evals-docs`.
- `main` is the deployment source of truth and deploys the public service.
- Live demo: <https://internhunteragent.onrender.com>.
- Deployment, database, cron, and incident procedures: [Operations.md](Operations.md).

## Completed milestones

Completed ticket plans are preserved in the [ticket archive](archive/Tickets_Archive.md).

M0-M20 are complete, covering the foundation, agent runtime, data ingestion, evaluation harness,
security, streaming, deployment, and reconciliation work.

M21 is complete through T0021.4.
The same pass carved the model-honesty work out of M21 into M24 - Honesty Enforcement.
M22 - Docs Hygiene & Documentation System has phase 1 (T0022.1-.9) merged to `main` on
2026-08-11 via PR #41.
T0022.10 through T0022.14 are complete.

M25 - Evaluation Instrument is complete as of 2026-08-13 (T0025.0-.10): the frozen Alembic-built
fixture, the 29-scenario registry, the in-process driver with manifests and resume, the trace
viewer, execution accuracy, the deterministic three-tier grader, and a CI replay that makes no
model, judge, or outbound call.
Acceptance is partial by design: 13 of 19 attempted turns measured, all 13 agreeing with the human
labels, and two scenarios still await a paid-tier decision ([Known Issues](Known_Issues.md)).

M26 - Evaluation Workspace Hygiene is complete (T0026.1-.3) and changes no verdict.
`evals/` holds the instrument plus the two live test modules, its deterministic tests live in
`tests/evals/`, [`evals/README.md`](../evals/README.md) is the entry point, and the scenario
registry owns every grading expectation rather than the grader.

M28 - Evaluation Documentation Ownership is complete (T0028.1-.4) and changes no verdict, rule, or
threshold. The Fact Ledger names an owner for evaluation facts, enforced by a `scenario-id` lint
check; [`Agent_Behavior_Spec.md`](Agent_Behavior_Spec.md) §4a-4c links to the registry instead of
duplicating it; the two dated snapshots sealed into `evals/archive/` and the grader audit and
holdout report merged into [`evals/Instrument_Report.md`](../evals/Instrument_Report.md); and
[`evals/Operating_Manual.md`](../evals/Operating_Manual.md) now explains the instrument end to end.

M29 - Evaluation Readability is complete through T0029.1 and changes no verdict, rule, or threshold.
`evals/viewer.py` takes an optional `--grade` report and joins it per turn, so one screen carries
the verdict and tier, each non-passing check beside the seam it judges, a grade filter kept distinct
from capture status, a manifest-built run header, and telemetry as labelled fields.

## Archive tags

These tags preserve branches that are no longer active. <!-- lint-allow-amendment -->

| Tag | Commit | What it preserves |
|---|---|---|
| `archive/t0015.2-behavior-glossary` | `62f2089` | The original complete 18-string `behavior_glossary` source. |
| `archive/t0015.4-scenario-matrix` | `eba3e1f` | The 29-scenario matrix, runner, fixture, and observed results for re-measurement. |
| `archive/t0015.6-provider-ab` | `45d333c` | The deferred provider/reasoning A/B phase and Windows event-loop factory. |
| `archive/stash-t0019.6-docs` | `b7a291e` | The former T0019.6 documentation stash and its original ten files. |
| `archive/docs-pre-prune` | `cb9ee2b` | The dead documentation surface and self-hosted Langfuse stack. |

## Carried work

- `stash@{0}` is unverified and retained; believed superseded, not compared line by line.
- The legacy HTTP runner stays archived. The driver took its orchestration as a pattern only and
  runs the agent in-process (D-043).
- The 2026-07-14 answer artifact is answer-only, so replaying it still grades `INFRA` at the
  structural tier. Only a driver capture carries tools, SQL, and execution results.
- `evals/runs/` is ignored, so the 13-turn labelled capture behind
  [`evals/Instrument_Report.md`](../evals/Instrument_Report.md) is not reproducible from a clean
  checkout.

## Folder structure

```text
alembic/       database migrations
config/        runtime, ingestion, prompt, and vocabulary configuration
docs/          living documentation, serving design, offline-pipeline design, and archives
docker/        application container image definition
evals/         DeepEval harness, fixtures, and scenario data (see evals/README.md)
scripts/       local maintenance and documentation checks
src/           API, application service, agent runtime, tracing, and ingestion services
tests/         automated tests, including tests/evals for the deterministic eval modules
```

## Dependencies

Runtime and development dependencies are maintained in [Tech Stack](Tech_Stack.md).
The authoritative package declarations are in `pyproject.toml`.

## Available scripts

- `uv run uvicorn src.api.app:app --reload` - run the API locally.
- `uv run pytest -q` - run the default suite, excluding live eval tests.
- `uv run pytest -m eval` - run the credentialed live eval tests.
- `uv run python -m evals.driver --output evals/runs/run.json` - capture the scenario registry.
- `uv run python -m evals.driver --resume --output evals/runs/run.json` - resume a partial run.
- `uv run python -m evals.driver diff left.json right.json` - verify run comparability.
- `uv run python -m evals.viewer evals/runs/run.json --grade evals/runs/run-grade.json` - generate
  the local trace viewer, with each turn's verdict joined when `--grade` is given.
- `uv run python -m evals.viewer --sample` - generate a two-turn viewer sample without model quota.
- `uv run python -m evals.execution_accuracy evals/runs/run.json` - grade persisted SQL seams.
  The command uses frozen fixture references.
- `uv run python -m evals.replay` - replay committed evidence with no model or judge call.
- `uv run ruff check .` - lint the repository.
- `uv run mypy` - type-check `src`.
- `uv run alembic current` and `uv run alembic upgrade head` - inspect or migrate a database.
- `docker compose up -d` - start local Postgres and the API.
- `uv run python scripts/docs_lint.py` - run every documentation convention check.

## Build and test status

| Check | Most recent recorded result |
|---|---|
| `python scripts/docs_lint.py` | Passed locally on 2026-08-15 (all eleven checks) |
| `uv run pytest -q` | 461 passed, 2 skipped, 30 live eval tests deselected, and 4 subtests passed on 2026-08-15 |
| `uv run pytest -q tests/agents/runtime/test_prompts.py` | 10 passed on 2026-08-13 |
| `uv run ruff check .` | Passed on 2026-08-15 |
| `uv run pytest -q tests/evals` | 93 passed on 2026-08-15 |
| `git diff --check` | Clean on 2026-08-15 |
| `uv run python -m evals.fixtures.loader` then `uv run python -m evals.replay` | Passed on 2026-08-15 |
| `uv run python -c` glossary loader check | `v1`, 18 tokens loaded on 2026-08-13 |
| `uv run mypy src` | Success: no issues in 43 source files on 2026-08-15 |
| CI gate, PR #48 | Passed on 2026-08-15 in 1m07s (docs, checks) |

Every skip is environmental. One migration round-trip test requires `SCRATCH_DATABASE_URL`, and
eight evaluation fixture tests require the local fixture Postgres on port 5433.
The default suite deselects live eval tests by design.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md).
Closed entries and their resolution records: [Resolved Issues](Resolved_Issues.md).

## Next recommended ticket

T0023 - the release path. Two threads run into it. `schedule:` is restored on `main` as of T0020.4,
so the last open row in [the activation runbook](T0020.4_Cron_Activation_Runbook.md) §7 is to watch
the first unattended 02:00 UTC run; the pipeline ran green against production three times on
2026-08-13 (113 loaded, 0 pages failed each) and `/api/v1/ready` reports a measured `2026-08-13`.
T0023 still owes its DoD sweep and terms posture, and M24 owns the behavior failures M25 measured.
M26, M28, and M29 are closed - M28 was documentation-only and M29 changed only how a recorded run
is read - so no hygiene work stands between here and the release sequence.
