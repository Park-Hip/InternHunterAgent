# Repository Current State

> **Last verified:** 2026-08-14; see [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

- Repository baseline: `main` at `410c628`.
- Active ticket branch: `codex/t0028-evals-docs-ownership`, stacked on
  `codex/t0026.3-registry-owned-grading`, `codex/t0026.2-eval-tests-under-tests`,
  `codex/t0026.1-evals-front-door`, `codex/t0025.10-close-m25`, and
  `codex/t0025.9-grader-audit-replay-ci` (PR #47).
- The M28 branch is checked out in the worktree `.claude/worktrees/t0028-evals-docs`.
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

M25 - Evaluation Instrument is complete as of 2026-08-13 (T0025.0-.10).
The repository now holds a frozen Alembic-built fixture, a 29-scenario registry owning probe flags,
reference SQL and tool expectations, an in-process driver with manifests and resume, a local trace
viewer, execution accuracy by executing generated against reference SQL, and a deterministic
three-tier grader. CI replays committed three-seam evidence with no model, judge, or outbound call.
Acceptance is partial by design: the free tier's admission ceiling left 13 of 19 attempted turns
measured, and the grader agrees with all 13 human labels.
`HLP-CONTEXT-1` and `HLP-COMPOUND-1` remain unmeasured pending a paid-tier decision.
The stale backlog in [`Tickets.md`](Tickets.md) was reconciled on 2026-08-13; only the cosmetic
custom-domain follow-up remains intentionally deferred until after v1.0.

M26 - Evaluation Workspace Hygiene is complete (T0026.1-.3) and changes no verdict.
`evals/` now holds the instrument plus the two live test modules, its deterministic tests live in
`tests/evals/`, and [`evals/README.md`](../evals/README.md) is the entry point.
The scenario registry owns every grading expectation, so the grader holds how a rule is applied
and none of what a scenario expects.

M28 - Evaluation Documentation Ownership is scoped and open (T0028.1-.4); see
[`Tickets.md`](Tickets.md).
T0028.1 and T0028.2 are complete: the Fact Ledger in [`README.md`](README.md) names an owner for
scenario definitions, behavior requirements, and dated graded outcomes; an eleventh lint check
(`scenario-id`) fails on any `HLP-`, `HON-`, or `SAF-` identifier absent from the registry; and
[`Agent_Behavior_Spec.md`](Agent_Behavior_Spec.md) §4a-4c now links to
[`evals/scenarios_v1.yaml`](../evals/scenarios_v1.yaml) instead of duplicating its fixture rows,
input, and expected behavior.

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
  [`evals/grader_audit.md`](../evals/grader_audit.md) is not reproducible from a clean checkout.

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
- `uv run python -m evals.viewer evals/runs/run.json --output evals/runs/run-viewer.html` - generate
  the local trace viewer.
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
| `python scripts/docs_lint.py` | Passed locally on 2026-08-14 (all eleven checks) |
| `uv run pytest -q` | 447 passed, 2 skipped, 30 live eval tests deselected, and 4 subtests passed on 2026-08-14 |
| `uv run pytest -q tests/agents/runtime/test_prompts.py` | 10 passed on 2026-08-13 |
| `uv run ruff check .` | Passed on 2026-08-13 |
| `uv run pytest -q tests/evals` | 82 passed on 2026-08-14 |
| `git diff --check` | Clean on 2026-08-13 |
| `uv run python -m evals.fixtures.loader` then `uv run python -m evals.replay` | Passed on 2026-08-13 |
| `uv run python -c` glossary loader check | `v1`, 18 tokens loaded on 2026-08-13 |
| `uv run mypy src` | Success: no issues in 43 source files on 2026-08-13 |
| CI gate, PR #39 | Passed in 44 seconds |

Every skip is environmental. One migration round-trip test requires `SCRATCH_DATABASE_URL`, and
eight evaluation fixture tests require the local fixture Postgres on port 5433.
The default suite deselects live eval tests by design.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md).
Closed entries and their resolution records: [Resolved Issues](Resolved_Issues.md).

## Next recommended ticket

T0028.3 - seal the two dated eval snapshots into `evals/archive/` and merge the two instrument
reports; independent of T0028.4 and blocks nothing else.

T0023 remains the release path once M28 closes or is preempted. Its DoD sweep, terms posture, and
live-cron gate (D-038) are the remaining blockers, and M24 owns the behavior failures M25 measured.
M28 is documentation ownership only and blocks nothing in that sequence.
