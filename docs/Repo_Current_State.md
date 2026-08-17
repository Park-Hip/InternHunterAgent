# Repository Current State

> **Last verified:** 2026-08-17 against the checked-out commit, active registers, and
> [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

- Repository baseline: `main` at `49852ae`, the first integration pass of 2026-08-17 (PR #54),
  on top of T0031.1 (PR #53), M30's scoping plan (PR #52), M29 (PR #51), M27 (PR #50, 2026-08-16),
  M28 (PR #49), and M25/M26 (PR #48); PR #47 was closed as superseded by #48.
- Unmerged work: `feature/t0024.6-persona-scope` carries T0024.1 and T0024.6, built 2026-08-13,
  never reviewed, and invisible until 2026-08-17 - see [Known Issues](Known_Issues.md).
  `feature/t0031.2-generate-registers` is open at the baseline; M29 and M30 are merged.
- Numbers, milestone scopes, and the frozen register list live in
  [`roadmap.yaml`](roadmap.yaml) as of T0031.1; this snapshot is written only by integration.
- Worktrees: three finished ones were pruned on 2026-08-17. `t0031-parallel-docs-workflow` stayed,
  locked by a dead pid; `t0024.1-behavior-glossary` stayed, holding the unmerged M24 work.
- `main` is the deployment source of truth and deploys the public service.
- Live demo: <https://internhunteragent.onrender.com>, re-probed 2026-08-17: a real answer with a
  Langfuse trace in 10.6 s, and its static assets hash-match `main`.
- Deployment, database, cron, and incident procedures: [Operations.md](Operations.md).

## Completed milestones

Completed ticket plans are preserved in the [ticket archive](archive/Tickets_Archive.md).

M0-M20 are complete, covering the foundation, agent runtime, data ingestion, evaluation harness,
security, streaming, deployment, and reconciliation work. M21 is complete through T0021.4, the
pass that carved the model-honesty work out into M24, and M22 - Docs Hygiene & Documentation
System - is complete (T0022.1-.14). M24 is in progress on an unreviewed branch, not planned.

M25-M29 are complete, entered through [`evals/README.md`](../evals/README.md) and recorded in full
in [Completion Reports](Completion_Reports.md): the evaluation instrument and its CI replay gate,
which makes no model, judge, or outbound call (M25); workspace hygiene, with the deterministic
tests in `tests/evals/` and every grading expectation owned by the registry (M26); the
`deepseek-v4-flash` serving default per the pre-registered rule **D-045**, measured at 29 of 29
scenarios in 5m20s for about $0.04 (M27, [the arm record](../evals/t0027_deepseek_arm.md));
documentation ownership enforced by the `scenario-id` check, explained end to end in
[`evals/Operating_Manual.md`](../evals/Operating_Manual.md) (M28); and the graded trace viewer,
where `--grade` puts a turn's verdict, its failing checks, the run header, and telemetry on one
screen (M29). None of M26, M28, or M29 changed a verdict, rule, or threshold.

M30 - Evaluation Evidence Durability is scoped, not built: the plan (T0030.1-.3) is merged, but no
ticket under it has landed. It closes the `[MED · DECISION]` T0025.10 left open in
[Known Issues](Known_Issues.md), triggered by the 2026-08-16 loss of the T0027.3 DeepSeek capture,
whose per-turn evidence is gone even though its findings survive in
[the arm record](../evals/t0027_deepseek_arm.md).

M31 - Parallel Agent Workflow is complete through T0031.1 (PR #53, 2026-08-17) and changes no
runtime behavior. A ticket records its outcome in [`entries/`](entries/README.md) and the
integration step folds it into the registers. T0031.2-.4 - the generator, the derived snapshot,
and the CI enforcement - are planned, so that fold is hand work today.

## Archive tags

These tags preserve branches that are no longer active. <!-- lint-allow-amendment -->

| Tag | Commit | What it preserves |
|---|---|---|
| `archive/t0015.2-behavior-glossary` | `62f2089` | The original complete 18-string `behavior_glossary` source. |
| `archive/t0015.4-scenario-matrix` | `eba3e1f` | The 29-scenario matrix, runner, fixture, and observed results for re-measurement. |
| `archive/t0015.6-provider-ab` | `45d333c` | The deferred provider/reasoning A/B phase and Windows event-loop factory. |
| `archive/stash-t0019.6-docs` | `b7a291e` | The former T0019.6 documentation stash and its original ten files. |
| `archive/docs-pre-prune` | `cb9ee2b` | The dead documentation surface and self-hosted Langfuse stack. |
| `archive/serving-outage-2026-08-13` | `1e073e3` | The original 2026-08-13 outage diagnosis, folded into the registers without a ticket number. |

## Carried work

- `stash@{0}` is unverified and retained; believed superseded, not compared line by line.
- The primary worktree holds an uncommitted `docs/Tickets.md` draft, and an untracked research plan
  beside it, scoping serving reliability, operational telemetry, and a production evaluation loop as
  T0027-T0029 - numbers already spent. Superseded as written; re-numbering it through
  [`roadmap.yaml`](roadmap.yaml) is the only way it lands. This is the drift T0031.1 prevents.
  Its §1.1 also concludes the 2026-08-13 outage was a model-provider failure, which the direct
  probes recorded in [Resolved Issues](Resolved_Issues.md) disprove: that section is wrong, not
  merely stale.
- The legacy HTTP runner stays archived; the driver took its orchestration as a pattern only and
  runs the agent in-process (D-043). The 2026-07-14 answer artifact is answer-only, so replaying it
  still grades `INFRA` at the structural tier - only a driver capture carries tools and SQL.
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
| `python scripts/docs_lint.py` | Passed on 2026-08-17 (all eleven checks, exit 0) |
| `uv run pytest -q` | 474 passed, 2 skipped, 30 live eval tests deselected, and 4 subtests passed on 2026-08-17 |
| `uv run ruff check .` | Passed on 2026-08-17 |
| `uv run mypy` | Success: no issues in 43 source files on 2026-08-17 |
| `uv run python -m evals.replay` | Exit 0 on 2026-08-17 against the frozen evidence |

Every skip is environmental: the migration round-trip needs `SCRATCH_DATABASE_URL`, and skill
parity needs the gitignored `.claude/` copy; the default suite deselects live eval tests by design.
An earlier run the same day reported 466 passed and 10 skipped in 279s with the fixture Postgres on
5433 down - the extra skips and the wall time are the hang [Known Issues](Known_Issues.md) records.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md). Closed entries and their
resolution records: [Resolved Issues](Resolved_Issues.md).

## Next recommended ticket

T0030.1 - give the replay format a writer. The DeepSeek capture loss that motivated M30 is a live
risk, and every further captured run stays exposed to it until `freeze` exists.

T0031.2 and T0031.3 are the competing pick, and this integration is the evidence for them: folding
one entry into five registers by hand, re-measuring two caps, and rewriting this snapshot is the
recurring cost T0031.1 deferred rather than removed.

T0023 - the release path - remains open: `schedule:` is restored on `main` as of T0020.4, so the
last row in [the activation runbook](T0020.4_Cron_Activation_Runbook.md) §7 is to watch the first
unattended 02:00 UTC run, and T0023 still owes its DoD sweep and terms posture. M24 owns the
behavior failures M25 and T0027.3 measured, triaged in [Known Issues](Known_Issues.md) as 23 real
behavior and 10 grader phrasing artifacts.
