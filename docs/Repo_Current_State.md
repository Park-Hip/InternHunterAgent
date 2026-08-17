# Repository Current State

> **Last verified:** 2026-08-17 against the checked-out commit, active registers, and
> [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

<!-- generated:snapshot:begin -->
- Checked out: `feature/t0031.3-derive-state` at `bcb0409` - feat(T0031.3): derive the current-state
  snapshot (2026-08-17).
- Branches not merged into `main`: 7 - `feature/t0022.10-prune-dead-docs`,
  `feature/t0024.1-behavior-glossary`, `feature/t0024.6-persona-scope`,
  `feature/t0031-parallel-agent-docs`, `feature/t0031.3-derive-state`, `merge/t0024.6-with-main`,
  `merge/t0025.7-with-main`.
- Worktrees: 7.
<!-- generated:snapshot:end -->

The block above is refreshed by `scripts/docs_build.py --snapshot`. It reports the clone it was
run in, so it is the one generated region the linter does not gate: branch and worktree facts
differ between a developer machine and CI, and a check that must pass on both cannot read them.

- Numbers, milestone scopes, and the frozen register list live in
  [`roadmap.yaml`](roadmap.yaml) as of T0031.1.
- `feature/t0024.6-persona-scope` carries the unreviewed T0024.1 and T0024.6 work from 2026-08-13,
  recorded in [Known Issues](Known_Issues.md). `t0031-parallel-docs-workflow` is locked by a dead
  pid.
- `main` is the deployment source of truth and deploys the public service.
- Live demo: <https://internhunteragent.onrender.com>, re-probed 2026-08-17: a real answer with a
  Langfuse trace in 10.6 s, and its static assets hash-match `main`.
- Deployment, database, cron, and incident procedures: [Operations.md](Operations.md).

## Milestones

Status is read from [`roadmap.yaml`](roadmap.yaml), which owns milestone identity. What each
milestone delivered is in [Completion Reports](Completion_Reports.md); completed ticket plans are
preserved in the [ticket archive](archive/Tickets_Archive.md).

<!-- generated:milestones:begin -->
Complete: M0, M6-M22, M25-M29 - 23 of 27 milestones.

| Milestone | Title | Status |
|---|---|---|
| M24 | Honesty Enforcement (obligation seam) | in-progress |
| M30 | Evaluation Evidence Durability | in-progress |
| M31 | Parallel Agent Workflow | in-progress |
| M23 | v1.0 Release Cut | planned |
<!-- generated:milestones:end -->

M24 is in progress on an unreviewed branch rather than planned. M30 is scoped and unbuilt: its
plan is merged and no ticket under it has landed, so the `[MED · DECISION]` T0025.10 left open in
[Known Issues](Known_Issues.md) is still open.

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

Declared in `pyproject.toml`, which is authoritative for the version specifier; what each package
is for is in [Tech Stack](Tech_Stack.md).

<!-- generated:dependencies:begin -->
Runtime (18): `alembic`, `beautifulsoup4`, `cloudscraper`, `fastapi`, `httpx`, `langchain`,
`langchain-deepseek`, `langchain-google-genai`, `langchain-groq`, `langfuse`,
`langgraph-checkpoint-postgres`, `lxml`, `psycopg`, `pydantic-settings`, `slowapi`, `sqlalchemy`,
`structlog`, `uvicorn`

Development (6): `deepeval`, `mypy`, `pytest`, `pytest-asyncio`, `pytest-mock`, `ruff`
<!-- generated:dependencies:end -->

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
- `uv run python -m evals.replay` - replay committed evidence with no model or judge call. It does
  still need a reachable Postgres: without one the execution seam grades `INFRA` and the replay
  fails on an outcome mismatch rather than skipping.
- `uv run ruff check .` - lint the repository.
- `uv run mypy` - type-check `src`.
- `uv run alembic current` and `uv run alembic upgrade head` - inspect or migrate a database.
- `docker compose up -d` - start local Postgres and the API.
- `uv run python scripts/docs_lint.py` - run every documentation convention check.
- `uv run python scripts/docs_build.py` - regenerate the register regions from `docs/entries/`
  and this file's derived regions; `--check` fails instead of writing, and `--snapshot` also
  refreshes the git block under [Current branch](#current-branch).

### Maintenance scripts

<!-- generated:scripts:begin -->
- `scripts/audit_fields.py` - Field audit of the captured VietnamWorks sample - tech_stack tags +
  job_level.
- `scripts/build_tech_vocabulary.py` - No module docstring.
- `scripts/deepseek_provider_spike.py` - Throwaway spike (T0027.1): decide whether DeepSeek can
  serve this agent at all.
- `scripts/docs_build.py` - Render the derived documentation registers from the per-ticket entry
  files.
- `scripts/docs_lint.py` - Check repository documentation hygiene without external dependencies.
- `scripts/eval_judge_spike.py` - Throwaway spike (T0011.1): pick a DeepEval judge that reliably
  returns schema-valid JSON.
- `scripts/scrape_itviec_spike.py` - Scraping spike - ITviec AI/Data IT jobs via cloudscraper.
- `scripts/scrape_spike.py` - Scraping experiment - VietnamWorks AI/Data IT jobs.
- `scripts/scrape_topcv_spike.py` - Scraping spike - TopCV internship listings via cloudscraper.
- `scripts/scrape_topdev_spike.py` - Scraping spike - TopDev AI/Data IT jobs via RSC payload
  parsing.
<!-- generated:scripts:end -->

## Build and test status

| Check | Most recent recorded result |
|---|---|
| `python scripts/docs_lint.py` | Passed on 2026-08-17 (all twelve checks, exit 0) |
| `python scripts/docs_build.py --check` | Exit 0 on 2026-08-17; every generated region current |
| `uv run pytest -q` | 488 passed, 10 skipped, 30 deselected, and 4 subtests passed on 2026-08-17 |
| `uv run ruff check .` | Passed on 2026-08-17 |
| `uv run mypy` | Success: no issues in 43 source files on 2026-08-17 |
| `uv run python -m evals.replay` | Exit 0 on 2026-08-17 against the frozen evidence, with a database up; re-run on T0031.3's branch failed with `INFRA` mismatches and no Postgres listening |

Every skip is environmental: the migration round-trip needs `SCRATCH_DATABASE_URL`, and skill
parity needs the gitignored `.claude/` copy; the default suite deselects live eval tests by design.
The 10 skips and the 277s wall time above are the fixture Postgres on 5433 being down, which is the
hang [Known Issues](Known_Issues.md) records; with it up the same suite reports 2 skips in seconds.
A bare `python -m pytest` is not the command: it cannot import `slowapi` and fails collection on 23
modules. Use `uv run`.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md). Closed entries and their
resolution records: [Resolved Issues](Resolved_Issues.md).

## Next recommended ticket

T0030.1 - give the replay format a writer. The DeepSeek capture loss that motivated M30 is a live
risk, and every further captured run stays exposed to it until `freeze` exists.

T0031.3 has landed, so this section is now the only part of this file a human writes. What is left
by hand elsewhere is `Tickets.md` and the judgement of where a raised issue belongs - and only the
second is a judgement. T0031.4, the registry, scope, and frozen lint checks, is the remaining M31
ticket.

T0023 - the release path - remains open: `schedule:` is restored on `main` as of T0020.4, so the
last row in [the activation runbook](T0020.4_Cron_Activation_Runbook.md) §7 is to watch the first
unattended 02:00 UTC run, and T0023 still owes its DoD sweep and terms posture. M24 owns the
behavior failures M25 and T0027.3 measured, triaged in [Known Issues](Known_Issues.md) as 23 real
behavior and 10 grader phrasing artifacts.
