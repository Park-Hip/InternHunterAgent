# Repository Current State

> **Last verified:** 2026-08-16 against the checked-out commit, active registers, and
> [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

- Repository baseline: `main` at `42fb3ef`, which merged M28 as PR #49 on 2026-08-15. It carries
  M25 and M26 from PR #48; PR #47 was closed as superseded, every commit it carried being already
  contained in #48.
- Active ticket branch: `feature/t0027-deepseek-provider`, merged up to that baseline rather than
  stacked behind it, in the worktree `.claude/worktrees/t0027-deepseek-provider`.
- `main` is the deployment source of truth and deploys the public service.
- Live demo: <https://internhunteragent.onrender.com>.
- Deployment, database, cron, and incident procedures: [Operations.md](Operations.md).

## Completed milestones

Completed ticket plans are preserved in the [ticket archive](archive/Tickets_Archive.md).

M0-M20 are complete, covering the foundation, agent runtime, data ingestion, evaluation harness,
security, streaming, deployment, and reconciliation work.

M21 is complete through T0021.4, and the same pass carved the model-honesty work out into M24.
M22 - Docs Hygiene & Documentation System is complete (T0022.1-.14).

M25 - Evaluation Instrument is complete as of 2026-08-13 (T0025.0-.10), and
[`evals/README.md`](../evals/README.md) is its entry point. CI replays committed three-seam
evidence with no model, judge, or outbound call. Its acceptance run was partial by design - the
free tier's ceiling left 13 of 19 turns measured - and T0027.3 has since measured all 29 scenarios.

M26 - Evaluation Workspace Hygiene is complete (T0026.1-.3) and changed no verdict.
Its deterministic tests live in `tests/evals/`, the scenario registry owns every grading
expectation, and its three ticket plans joined M25's ten in the archive on 2026-08-14.

M27 - DeepSeek Provider Integration is complete (T0027.1-.4), 2026-08-14 to 2026-08-15.
`agent.<profile>.provider` selects a provider per profile, the manifest records which one produced
a run, and the measured arm captured 29 of 29 scenarios and 77 turns in 5m20s for about $0.04.
DeepSeek was selected on operational grounds at step 4 of the pre-registered rule (**D-045**): both
profiles now use `deepseek-v4-flash`, `render.yaml` declares `DEEPSEEK_API_KEY`,
`eval.driver.turn_pacing_seconds` is 0, and each provider branch validates its own key at boot.
The Groq branch stays selectable. See [the arm record](../evals/t0027_deepseek_arm.md) and
[`research/deepseek-provider-evaluation.md`](../research/deepseek-provider-evaluation.md).
**Before this reaches `main`, `DEEPSEEK_API_KEY` must exist in the Render dashboard**; without it
the deploy starts healthy and fails on the first query.

M28 - Evaluation Documentation Ownership is complete (T0028.1-.4) and changes no verdict, rule, or
threshold. The Fact Ledger names an owner for evaluation facts, enforced by a `scenario-id` lint
check; the behavior spec links to the registry instead of duplicating it; the dated snapshots are
sealed in `evals/archive/` and the audit and holdout reports merged into
[`evals/Instrument_Report.md`](../evals/Instrument_Report.md); and
[`evals/Operating_Manual.md`](../evals/Operating_Manual.md) explains the instrument end to end.

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
  checkout; references to it carry `<!-- lint-allow-link-path -->`, because they resolve on a
  developer machine and fail the documentation gate, which lints a bare checkout.

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
| `python scripts/docs_lint.py` | Passed on 2026-08-16 (all eleven checks) |
| `uv run pytest -q` | 453 passed, 10 skipped, 30 live eval tests deselected, and 4 subtests passed on 2026-08-16 |
| `uv run ruff check .` | Passed on 2026-08-16 |
| `uv run pytest -q tests/evals` | 82 passed on 2026-08-16 |
| `git diff --check` | Clean on 2026-08-16 |
| `uv run python -m evals.replay` | Exit 0 on 2026-08-16, unchanged by the provider flip |
| `uv run mypy` | Success: no issues in 43 source files on 2026-08-16 |

Every skip is environmental. One migration round-trip test requires `SCRATCH_DATABASE_URL`, eight
evaluation fixture tests require the local fixture Postgres on port 5433, and one skill-parity
check needs the gitignored `.claude/` copy.
The default suite deselects live eval tests by design.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md).
Closed entries and their resolution records: [Resolved Issues](Resolved_Issues.md).

## Next recommended ticket

T0023 - the release path. `schedule:` is restored on `main` as of T0020.4, so the last open row in
[the activation runbook](T0020.4_Cron_Activation_Runbook.md) §7 is to watch the first unattended
02:00 UTC run; the pipeline ran green against production three times on 2026-08-13 and
`/api/v1/ready` reports a measured `2026-08-13`. T0023 still owes its DoD sweep and terms posture.
M24 owns the behavior failures M25 and T0027.3 measured, and T0027.3 hands it a triaged list: of 33
failing turns, 23 are real behavior and 10 are grader phrasing artifacts recorded in
[Known Issues](Known_Issues.md). M26, M27, and M28 are closed, so no hygiene work stands between
here and the release sequence.
