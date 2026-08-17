# Repository Current State

> **Last verified:** 2026-08-17 against the checked-out commit, active registers, and
> [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

- Repository baseline: `main` at `3ea785a`, which merged M30's scoping plan as PR #52 on
  2026-08-17, carrying M29 (PR #51, same day) and, beneath it, M27 (PR #50, 2026-08-16), M28
  (PR #49), and M25/M26 (PR #48); PR #47 was closed as superseded by #48.
- Active ticket branch: none. `feature/t0029-viewer-readability` and
  `feature/t0030-evidence-durability` are both merged, and neither worktree is active.
- `main` is the deployment source of truth and deploys the public service.
- Live demo: <https://internhunteragent.onrender.com>.
- Deployment, database, cron, and incident procedures: [Operations.md](Operations.md).

## Completed milestones

Completed ticket plans are preserved in the [ticket archive](archive/Tickets_Archive.md).

M0-M20 are complete, covering the foundation, agent runtime, data ingestion, evaluation harness,
security, streaming, deployment, and reconciliation work.

M21 is complete through T0021.4, and the same pass carved the model-honesty work out into M24.
M22 - Docs Hygiene & Documentation System is complete (T0022.1-.14).

M25 - Evaluation Instrument is complete as of 2026-08-13 (T0025.0-.10), entered through
[`evals/README.md`](../evals/README.md) and gated by a CI replay of committed three-seam evidence
that makes no model, judge, or outbound call; its acceptance run measured 13 of 19 turns on the
free tier, T0027.3 has since measured all 29.
M26 - Evaluation Workspace Hygiene is complete (T0026.1-.3) and changed no verdict; its
deterministic tests live in `tests/evals/`, and the scenario registry owns every grading
expectation.
M27 - DeepSeek Provider Integration is complete (T0027.1-.4, 2026-08-14 to 2026-08-15). Both
profiles use `deepseek-v4-flash` per the pre-registered rule (**D-045**); the measured arm captured
29 of 29 scenarios and 77 turns in 5m20s for about $0.04. Evidence:
[the arm record](../evals/t0027_deepseek_arm.md).
M28 - Evaluation Documentation Ownership is complete (T0028.1-.4) and changes no verdict, rule, or
threshold. The Fact Ledger names an owner for evaluation facts, enforced by a `scenario-id` lint
check, and [`evals/Operating_Manual.md`](../evals/Operating_Manual.md) explains the instrument end
to end.

M29 - Evaluation Readability is complete through T0029.1 and changes no verdict, rule, or threshold.
`evals/viewer.py` joins an optional `--grade` report per turn, so one screen carries the verdict and
tier, each failing check beside its seam, a grade filter, a run header, and labelled telemetry.

M30 - Evaluation Evidence Durability is scoped, not built: the plan (T0030.1-.3) is merged, but no
ticket under it has landed. It closes the `[MED · DECISION]` T0025.10 left open in
[Known Issues](Known_Issues.md), triggered by the 2026-08-16 loss of the T0027.3 DeepSeek capture,
whose per-turn evidence is gone even though its findings survive in
[the arm record](../evals/t0027_deepseek_arm.md).

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
  checkout. References to it carry `<!-- lint-allow-link-path -->`: they resolve on a developer
  machine but fail the documentation gate, which lints a bare checkout.

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
- `uv run python -m evals.viewer <run>.json --grade <run>-grade.json` - the local trace viewer,
  with each turn's verdict joined when `--grade` is given.
- `uv run python -m evals.viewer --sample` - generate a two-turn viewer sample without model quota.
- `uv run python -m evals.execution_accuracy <run>.json` - grade SQL seams on frozen references.
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
| `uv run pytest -q` | 472 passed, 2 skipped, 30 live eval tests deselected, and 4 subtests passed on 2026-08-16 |
| `uv run ruff check .` | Passed on 2026-08-16 |
| `uv run pytest -q tests/evals` | 93 passed on 2026-08-16 |
| `git diff --check` | Clean on 2026-08-16 |
| `uv run python -m evals.replay` | Exit 0 on 2026-08-16, unchanged by the viewer work |
| `uv run mypy` | Success: no issues in 43 source files on 2026-08-16 |

Every skip is environmental: the migration round-trip needs `SCRATCH_DATABASE_URL`, the eight
evaluation fixture tests need the local fixture Postgres on 5433, and skill parity needs the
gitignored `.claude/` copy. The default suite deselects live eval tests by design.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md).
Closed entries and their resolution records: [Resolved Issues](Resolved_Issues.md).

## Next recommended ticket

T0030.1 - give the replay format a writer. The DeepSeek capture loss that motivated M30 is a live
risk, and every further captured run stays exposed to it until `freeze` exists.
T0023 - the release path - is the other open ticket: `schedule:` is restored on `main` as of
T0020.4, so the last open row in
[the activation runbook](T0020.4_Cron_Activation_Runbook.md) §7 is to watch the first unattended
02:00 UTC run; the pipeline ran green against production three times on 2026-08-13. T0023 still
owes its DoD sweep and terms posture. M24 owns the behavior failures M25 and T0027.3 measured,
triaged as 23 real behavior and 10 grader phrasing artifacts in
[Known Issues](Known_Issues.md); M29 is the screen that makes that triage repeatable. M26-M29 are
closed, so only M30 stands between here and the release sequence.
