# Repository Current State

> **Last verified:** 2026-08-13; see [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

- Repository baseline: `main` at `410c628`.
- Active ticket branch: `codex/t0025.7-instrument-acceptance` at `83e1ce7`.
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
T0025.0 now builds the frozen evaluation fixture through Alembic, keeping its schema aligned with
the serving contract.
T0025.1 restored the 29-scenario registry and 2026-07-14 observed-answer artifact.
It also removed the stale 18-case golden dataset in favor of in-memory generation from the registry.
T0025.2 open-coded all 73 recovered final answers and recorded the ranked failure modes in
[`evals/v1_error_analysis.md`](../evals/v1_error_analysis.md).
It confirmed eight empty-answer `INFRA` outcomes across six IDs and the separate
HON-ZERO-RESULTS-1 database-error outcome without assigning any failure to routing or SQL
generation.
T0025.8 renamed the registry onto the self-describing `SAF`, `HON`, and `HLP` taxonomy.
The registry now keeps requirements, settled decisions, and viewer names in explicit fields.
T0025.3 added the in-process scenario driver with persisted three-seam records, manifests,
retry events, quota-safe partial runs, and resume support.
T0025.4 added the dependency-free local trace viewer with persistent operator notes and the
first-upstream-failure review rule.
T0025.5 added reference SQL, explicit non-query exemptions, and deterministic fixture-backed
execution-accuracy grading over persisted seam records.
The native driver fingerprints the fixture, disables Langfuse, and owns provider retries.
T0025.6 added deterministic structural and textual grading, a judge-score adapter, four-outcome
handling, class-split summaries, a six-scenario holdout, and no-model replay of the historical
answer artifact.
The 18-entry behavior glossary and `prompt_version: v1` are now loaded from `config/prompts.yaml`.
T0025.7 now captures the scenario-registry hash, clean or dirty worktree state, per-turn latency,
provider telemetry, and finish reasons without changing the current configuration.
Its first clean-worktree live attempt stopped at the Groq TPM limit before a completed turn, so M25
remains open and T0025.7 must be rerun before T0025.9's real-output grader audit and replay gate.
The stale backlog in [`Tickets.md`](Tickets.md) was reconciled on 2026-08-13; only the cosmetic
custom-domain follow-up remains intentionally deferred until after v1.0.

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

- `stash@{0}` is unverified and retained. It is believed superseded but has not been compared
  line by line.
- The M15 scenario registry and observed answers are restored.
  The legacy HTTP runner remains archived because T0025.3 will use its orchestration only as a
  pattern around the in-process harness.
- The historical answer artifact is answer-only, so structural grading remains `INFRA` until a
  T0025.3 run provides tools, SQL, and T0025.5 execution results.

## Folder structure

```text
alembic/       database migrations
config/        runtime, ingestion, prompt, and vocabulary configuration
docs/          living documentation, serving design, offline-pipeline design, and archives
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
- `uv run python -m evals.driver --output evals/runs/run.json` - capture the scenario registry.
- `uv run python -m evals.driver --resume --output evals/runs/run.json` - resume a partial run.
- `uv run python -m evals.driver diff left.json right.json` - verify run comparability.
- `uv run python -m evals.viewer evals/runs/run.json --output evals/runs/run-viewer.html` - generate
  the local trace viewer.
- `uv run python -m evals.viewer --sample` - generate a two-turn viewer sample without model quota.
- `uv run python -m evals.execution_accuracy evals/runs/run.json` - grade persisted SQL seams.
  The command uses frozen fixture references.
- `uv run ruff check .` - lint the repository.
- `uv run mypy` - type-check `src`.
- `uv run alembic current` and `uv run alembic upgrade head` - inspect or migrate a database.
- `docker compose up -d` - start local Postgres and the API.
- `uv run python scripts/docs_lint.py` - run every documentation convention check.

## Build and test status

| Check | Most recent recorded result |
|---|---|
| `python scripts/docs_lint.py` | Passed locally on 2026-08-13 (all ten checks) |
| `pytest -q evals/test_scenarios.py` | 7 passed on 2026-08-13 |
| `uv run pytest -q` | 418 passed, 1 skipped, 30 live eval tests deselected, and 4 subtests passed on 2026-08-13 |
| `uv run ruff check src tests` | Passed on 2026-08-13 |
| `uv run python -m pytest evals/test_driver.py evals/test_viewer.py -q` | 22 passed on 2026-08-13 |
| `uv run pytest -q evals/test_scenarios.py evals/test_execution_accuracy.py evals/test_driver.py` | 16 passed on 2026-08-13 |
| `uv run ruff check evals/execution_accuracy.py evals/scenarios.py evals/test_execution_accuracy.py` | Passed on 2026-08-13 |
| `python -m py_compile evals/driver.py src/agents/runtime/provider.py src/agents/tracing/langfuse.py` | Passed on 2026-08-13 |
| `uv run ruff check evals/driver.py evals/harness.py evals/viewer.py evals/test_driver.py` | Passed on 2026-08-13 |
| `uv run ruff check evals/driver.py evals/test_driver.py` | Passed on 2026-08-13 |
| `uv run pytest -q evals` | 47 passed, 30 live eval tests deselected on 2026-08-13 |
| `uv run pytest -q tests/agents/runtime/test_prompts.py` | 10 passed on 2026-08-13 |
| `uv run ruff check evals/grader.py evals/holdout.py evals/test_grader.py evals/driver.py evals/execution_accuracy.py evals/scenarios.py` | Passed on 2026-08-13 |
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

T0025.7 - rerun the clean current-configuration capture after Groq TPM headroom recovers.
