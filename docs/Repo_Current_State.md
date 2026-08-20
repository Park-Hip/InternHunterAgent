# Repository Current State

> **Last verified:** 2026-08-19 against the checked-out commit, active registers, and
> [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

<!-- generated:snapshot:begin -->
- Checked out: `main` at `03b43ff` - Merge pull request #81 from Park-Hip/codex/t0033.4-demo-ui
  (2026-08-19).
- Branches not merged into `main`: 15 - `codex/t0033.2-behavior-glossary`, `codex/t0033.2-pr`,
  `codex/t0033.3-pr`, `codex/t0033.3-vietnamese-evals`, `codex/t0033.4-demo-ui`, `codex/t0033.5-pr`,
  `codex/t0033.5-tool-literals`, `feature/t0022.10-prune-dead-docs`,
  `feature/t0024.1-behavior-glossary`, `feature/t0024.6-persona-scope`,
  `feature/t0031-parallel-agent-docs`, `feature/t0038-grader-correctness`,
  `integration/t0031.4-publish`, `merge/t0024.6-with-main`, `merge/t0025.7-with-main`.
- Worktrees: 23.
<!-- generated:snapshot:end -->

The block above is refreshed by `scripts/docs_build.py --snapshot`. It reports the clone it was
run in, so it is the one generated region the linter does not gate: branch and worktree facts
differ between a developer machine and CI, and a check that must pass on both cannot read them.

- Numbers, milestone scopes, and the frozen register list live in
  [`roadmap.yaml`](roadmap.yaml) as of T0031.1.
- `t0031-parallel-docs-workflow` is locked by a dead pid.
- `main` is the deployment source of truth and deploys the public service.
- Live demo: <https://internhunteragent.onrender.com>, re-probed 2026-08-17: a real answer with a
  Langfuse trace in 10.6 s, and its static assets hash-match `main`. Re-probed again by the
  integration step the same day: `/api/v1/health` and `/api/v1/ready` both `200` warm, the latter
  reporting `data_snapshot_date: 2026-08-17` with `provenance: measured`. Note the health routes
  live under the `/api/v1` prefix; bare `/health` and `/ready` are `404` and are not the check.
- Deployment, database, cron, and incident procedures: [Operations.md](Operations.md).

## Milestones

Status and named open obligations are maintained in [`roadmap.yaml`](roadmap.yaml).
Completed historical plans and reports are preserved in [`archive/`](archive/).

<!-- generated:milestones:begin -->
Complete: M0, M6-M22, M24-M38 - 33 of 35 milestones.

| Milestone | Title | Status |
|---|---|---|
| M39 | Fixture Test Reliability | claimed |
| M23 | v1.0 Release Cut | planned |
<!-- generated:milestones:end -->

**Nothing is in progress.** M33 closed on 2026-08-19, leaving M23 - the v1.0 release cut - as the
only milestone still planned.

**M33** shipped Vietnamese across the whole user-facing surface in five tickets merged the same
day: the output-language rule and query vocabulary with a `prompt_version` bump (`.1`, PR #77), the
19-entry behavior glossary with the grader anchor terms that validate against it (`.2`, PR #78),
the Vietnamese eval registry with row-aware purity grading (`.3`, PR #79), the tool literals and
error strings (`.5`, PR #80), and the demo UI (`.4`, PR #81). Neither recorded risk materialised:
`.2` re-stated `t0024.4-v3-obligations.json` in the same commit, so the replays never landed red,
and `.4` answered its typography question by reordering the stack rather than self-hosting a face -
`Times New Roman`, `Georgia`, `DejaVu Serif`, serif keeps `src/api/static` font-file-free and
CSP-clean, with body line-height at `1.7` for stacked diacritics.

Two M33 obligations went unmet and carry forward without ticket numbers: the D4 prerequisite
(`--arm A0 --runs 3`, so `.1`'s wording shipped unmeasured against its control) and a full
29-scenario Vietnamese capture, which `.3` left ungraded as a quota decision rather than a code
change.

**M24** closed with its whole mechanism shipped and its gate short of a clean pass. The obligation
seam exists end to end: `detect_obligations` over the validated SQL and result set (`.2`, PR #68),
a `MANDATORY CAVEATS` block both tools render, the caveat-relay contract in the system prompt with
`prompt_version` at `v3` (`.3`, PR #69), and a frozen replay that re-grades with no model call
(`.4`, PR #70). `T0024.5` was allocated, measured out by `.4`, and never built. The gate reads
**11 PASS / 7 FAIL over 18 turns**: `HON-CURRENCY-1` went 0/3 to 3/3, which is the design's
motivating failure closed, while `HON-CREATED-ON-1` and `HON-ABSENT-FIELD-1` each fail 3/3 and no
`v2` control was captured. Read the milestone as a measured honesty limitation, not as honesty
enforced; the four residuals are filed in [Known Issues](Known_Issues.md).

**M37** was allocated and closed the same day against the 2026-08-18 nightly, which was cancelled
at the workflow's 15-minute ceiling rather than failing: every VietnamWorks request hung for its
full timeout, so a whole-source outage needed ~26 minutes to give up and `main()` never reached its
own abort path. `api.max_elapsed_seconds: 600` now bounds the whole fetch, verified against a real
non-routable blackhole at 21.8s against an unbounded worst case of 336s.

**M38** closed before M33. Its corrected rules resolve glossary and registry anchors, expose honesty
seam 3 when seam 2 fails, and re-grade the frozen v3 obligation replay at 15 PASS / 3 FAIL without
a new capture. The judge remains off pending broader v3 human agreement.

**M35** closed last, and closes the labelling half of M24's missing control: `prompt_version` is
now recorded in the capture manifest, required by `freeze_capture`, validated at replay
`schema_version` 2, and drawn in the viewer's run header. An unlabelled capture cannot become a
labelled-looking replay. The three committed replays were backfilled from the prompt version in the
commit each capture ran at - sound for `t0025.7-acceptance` (`v1`, from a `git_sha` at a clean
worktree), an inference from the adding commit for the other two.

**M32** and **M36** also closed on 2026-08-18: M32 made the model-facing string surface knowable
without changing a word of it, and M36 broke the M31 check deadlock that left a ticket branch
adding an archived per-ticket entry with no passing state.
M33 and M35 were allocated out of the T0032.4
spike's triage. **M34** then closed its serving-path defect on 2026-08-18: the message-count cap
became a six-turn window that retains complete user turns. **M30** closed on 2026-08-17 - the
`freeze` command, the surviving T0025.7
capture at `evals/replays/t0025.7-acceptance.json`, and **D-046** on what a replay keeps; the
T0027.3 DeepSeek capture that motivated it was already lost and stays lost. Per-milestone detail
is in the [documentation archive](archive/).

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
- An untracked research plan remains in the primary worktree, scoping serving reliability,
  operational telemetry, and a production evaluation loop as T0027-T0029 - numbers already spent.
  Superseded as written; re-numbering it through [`roadmap.yaml`](roadmap.yaml) is the only way it
  lands, and it is the drift T0031.1 prevents. Its §1.1 also concludes the 2026-08-13 outage was a
  model-provider failure, which the direct probes in
  [Resolved Issues](archive/Resolved_Issues.md) disprove:
  that section is wrong, not merely stale.
- The primary worktree carries untracked browser-capture screenshots and a `.playwright-mcp/` log
  directory, plus an unstaged `AGENTS.md`/`CLAUDE.md` edit adding the `docs_build.py` step to the
  completion-report rules. None are the integration step's to commit; all three trip `docs_lint`
  locally and none reach CI.
- The legacy HTTP runner stays archived; the driver took its orchestration as a pattern only and
  runs the agent in-process (D-043). The 2026-07-14 answer artifact is answer-only, so replaying it
  still grades `INFRA` at the structural tier - only a driver capture carries tools and SQL.
- `evals/runs/` stays ignored: raw captures are uncommitted by design (**D-046**), and their
  sanitized projections live in `evals/replays/`. `evals/Instrument_Report.md` carries no
  `<!-- lint-allow-link-path -->`, so its references resolve in a bare checkout. One marker
  survives in [the arm record](../evals/t0027_deepseek_arm.md), naming the lost T0027.3 capture:
  it cannot be repointed, because nothing to point at exists.

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
is for is in [Design](Design.md).

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
- `uv run python -m evals.driver freeze <run>.json --grade <grade>.json -o evals/replays/<arm>.json`
  - freeze a completed capture into committed, sanitized evidence (T0030.1).
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
- `uv run python scripts/docs_build.py` - run the remaining documentation maintenance checks.
  The `--snapshot` option refreshes the clone-local git block under
  [Current branch](#current-branch).

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
- `scripts/sync_agent_instructions.py` - Keep AGENTS.md byte-for-byte identical to CLAUDE.md.
- `scripts/vietnamese_prompt_spike.py` - Measure Vietnamese prompt variants against the
  fixture-backed production agent.
<!-- generated:scripts:end -->

## Build and test status

| Check | Most recent recorded result |
|---|---|
| `python scripts/docs_lint.py` | Exit 1 on 2026-08-19 in this clone, on untracked leftovers only - the superseded production-readiness plan [Carried work](#carried-work) records, plus browser-capture screenshots and a `.playwright-mcp/` log directory left in the working tree, and an uncommitted edit to `AGENTS.md` and `CLAUDE.md`. All are untracked or unstaged, so CI never sees them and every other check passed. Naming its path here reproduced the same finding from the other direction, which is why this row describes it instead. The `frozen` findings an integration session also sees are the check working: it fires on any write to a frozen register, and the integration step is the one writer allowed to make them |
| `python scripts/docs_build.py --check` | Exit 0 on 2026-08-19; every generated region current |
| `uv run pytest -q` | 558 passed, 9 skipped, 30 deselected, and 45 subtests passed on 2026-08-19, in 4 m 31 s. The nine skips and the runtime are both the fixture Postgres being unreachable in this clone, not a regression; CI ran the same suite green on all five M33 heads |
| `uv run ruff check .` | Passed on 2026-08-19 |
| `uv run mypy` | Success: no issues in 44 source files on 2026-08-19 |
| `uv run python -m evals.replay` | Exit 0 in CI on 2026-08-19 on each of the five M33 heads, which is where the frozen evidence is actually re-graded. Not re-run locally by the integration step that published M33: Docker Desktop was not running, so nothing listened on 5433 - the recorded precondition rather than a result |

The skips are environmental: the migration round-trip needs `SCRATCH_DATABASE_URL`, and the rest
need the fixture Postgres. The default suite deselects live eval tests by design. A run with the
fixture Postgres unreachable reports nine skips and takes minutes instead of seconds - the hang
[Known Issues](Known_Issues.md) records, and the shape of the 2026-08-19 run above.

Only the tracked `skills/plan/SKILL.md` is authoritative; the gitignored
`.claude/` copy drifted once and was fixed on 2026-08-18.

Two command traps, both measured on 2026-08-17. A bare `python -m pytest` cannot import `slowapi`
and fails collection on 23 modules, so use `uv run`. And a fresh worktree has no `.env`, since it
is gitignored and therefore per-worktree; without the runtime variables set, ten modules fail
collection with `ConfigLoadError`. The dummy values in
[`ci.yml`](../.github/workflows/ci.yml) are enough.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md). Closed entries and their
resolution records: [Resolved Issues](archive/Resolved_Issues.md).

## Next recommended ticket

**M23** - the v1.0 release cut - is the only milestone left, and with M33 closed the sequencing
argument for deferring it is spent. What it owes is its DoD sweep and terms posture; decision
**D9** wants a read on trustworthy honesty numbers, which the two items below are the cheapest
route to.

M33's two unmet obligations, recorded above, are both measurement rather than code and neither has
a ticket; the Vietnamese capture needs a quota decision before it needs an implementer.

Two more things sit beside those, both small and both about M24's residue rather than new
capability.
`KI-2026-08-18-absent-field-grader-stale` is the cheapest useful work in the repository right now:
until the absent-field scenario's expectations are reconciled with the truthful listing-expiry
answer T0024.2 introduced, two of M24's seven failures cannot be read as either pass or defect. And
with M35 landed, re-capturing the missing `v2` control
(`KI-2026-08-18-honesty-gate-has-no-control`) would now produce a correctly labelled baseline at
M27's measured 5m20s for about $0.04.

The protocol gate is built and running in CI (`registry`, `scope`, `frozen`), but the `docs` job
that runs it is advisory rather than required - `KI-2026-08-18-docs-job-not-required`, a maintainer
decision rather than a ticket.

This section and the build-status table are maintained as recorded facts.

T0023's cron precondition is satisfied: `Nightly ingestion` ran unattended on `schedule` four
nights running (2026-08-14 through 08-17, the last at 03:02 UTC), meeting the last row of
[the activation runbook](archive/T0020.4_Cron_Activation_Runbook.md) §7 and the D-038 live schedule
requirement. Of the behavior failures M25 and T0027.3 measured - triaged in
[Known Issues](Known_Issues.md) as 23 real behavior and 10 grader phrasing artifacts - M24 closed
the honesty subset it scoped and left the helpfulness ones untouched and unowned.
