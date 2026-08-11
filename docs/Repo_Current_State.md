# Repository Current State

> **Last verified:** 2026-08-11 against the checked-out commit, active registers, and
> [`Operations.md`](Operations.md).

## Current branch

- Working branch: feature/t0022.10-prune-dead-docs (a git branch, not a directory).
- `main` is the deployment source of truth and deploys the public service.
- Live demo: <https://internhunteragent.onrender.com>.
- Deployment, database, cron, and incident procedures: [Operations.md](Operations.md).

## Completed milestones

Completed ticket plans are preserved in the [ticket archive](archive/Tickets_Archive.md).

- M0 - Foundation.
- M1 - Runnable request flow.
- M2 - ReAct agent runtime.
- M3 - Self-hosted Langfuse.
- M4 - Tracing integration.
- M5 - Hardening.
- M6 - First real SQL tool.
- M7 - Conversation memory.
- M8 - System prompt and persona refinement.
- M9 - Data ingestion.
- M10 - Pre-deploy hardening.
- M11 - Model evaluation harness.
- M12 - Hardening and known-issue fixes.
- M13 - Schema enrichment and v1 freeze.
- M14 - Pre-deploy known-issue fixes.
- M16 - Security posture.
- M17 - Streaming response delivery.
- M18 - Clickable demo and first deploy.
- M19 - Ingestion deploy readiness.
- M20 - Reconciliation and activation.

M21 has T0021.1 and T0021.2 complete; T0021.3 and T0021.4 remain unscoped.
M22 - Docs Hygiene & Documentation System has phase 1 (T0022.1-.9) merged to `main` on
2026-08-11 via PR #41.
T0022.10 is complete; T0022.11-.14 remain scoped and not started.

## Archive tags

The branches these tags replaced no longer exist.

| Tag | Commit | What it preserves |
|---|---|---|
| `archive/t0015.2-behavior-glossary` | `62f2089` | The complete 18-string `behavior_glossary` that never reached `config/prompts.yaml`. |
| `archive/t0015.4-scenario-matrix` | `eba3e1f` | The 29-scenario matrix, runner, fixture, and observed results for re-measurement. |
| `archive/t0015.6-provider-ab` | `45d333c` | The deferred provider/reasoning A/B phase and Windows event-loop factory. |
| `archive/stash-t0019.6-docs` | `b7a291e` | The former T0019.6 documentation stash and its original ten files. |
| `archive/docs-pre-prune` | `cb9ee2b` | The dead documentation surface and self-hosted Langfuse stack. |

## Carried work

- `stash@{0}` is unverified and retained. It is believed superseded but has not been compared
  line by line.
- M15's spec and 29-scenario matrix are restored; its runner remains on the archive tag.
- `behavior_glossary` is still absent from `config/prompts.yaml`; landing it changes agent output.

## Folder structure

```text
alembic/       database migrations
config/        runtime, ingestion, prompt, and vocabulary configuration
docs/          living documentation and archives
docker/        application container image definition
evals/         DeepEval harness, fixtures, and scenario data
scripts/       local maintenance and documentation checks
src/           API, application service, agent runtime, tracing, and ingestion services
tests/         automated tests
```

## Dependencies

Runtime and development dependencies are maintained in [Tech Stack](Tech_Stack.md).
The authoritative package declarations are in `pyproject.toml`.

## Available scripts

- `uv run uvicorn src.api.app:app --reload` - run the API locally.
- `uv run pytest -q` - run the default suite, excluding live eval tests.
- `uv run pytest -m eval` - run the credentialed live eval tests.
- `uv run ruff check .` - lint the repository.
- `uv run mypy` - type-check `src`.
- `uv run alembic current` and `uv run alembic upgrade head` - inspect or migrate a database.
- `docker compose up -d` - start local Postgres and the API.
- `uv run python scripts/docs_lint.py` - run every documentation convention check.

## Build and test status

| Check | Most recent recorded result |
|---|---|
| `python scripts/docs_lint.py` | Passed locally on 2026-08-10 (all checks) |
| `uv run pytest -q` | 346 passed, 1 skipped, 19 deselected, 4 subtests passed |
| `uv run ruff check src tests` | Passed |
| `uv run mypy src` | Success: no issues in 43 source files |
| CI gate, PR #39 | Passed in 44 seconds |

The migration round-trip skip requires `SCRATCH_DATABASE_URL`.
The default suite deselects live eval tests by design.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md).
Closed entries and their resolution records: [Resolved Issues](Resolved_Issues.md).

## Next recommended ticket

T0022.11 - collapse the executed research archives. T0023, the v1.0 release cut, follows M22.
