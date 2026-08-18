# Repository Current State

> **Last verified:** 2026-08-18 against the checked-out commit, active registers, and
> [`Operations.md`](Operations.md).

> **Eviction:** A current-state fact leaves when the checked-out repository or active operational
> register changes; replace it with the verified current fact.

## Current branch

<!-- generated:snapshot:begin -->
- Checked out: `main` at `ce9f1f5` - docs(integration): publish M34 memory-window outcome
  (2026-08-18).
- Branches not merged into `main`: 7 - `feature/t0022.10-prune-dead-docs`,
  `feature/t0024.1-behavior-glossary`, `feature/t0024.6-persona-scope`,
  `feature/t0031-parallel-agent-docs`, `integration/t0031.4-publish`, `merge/t0024.6-with-main`,
  `merge/t0025.7-with-main`.
- Worktrees: 15.
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

Status is read from [`roadmap.yaml`](roadmap.yaml), which owns milestone identity. What each
milestone delivered is in [Completion Reports](Completion_Reports.md); completed ticket plans are
preserved in the [ticket archive](archive/Tickets_Archive.md).

<!-- generated:milestones:begin -->
Complete: M0, M6-M22, M24-M32, M34-M37 - 31 of 34 milestones.

| Milestone | Title | Status |
|---|---|---|
| M23 | v1.0 Release Cut | planned |
| M33 | Vietnamese Language Milestone | planned |
| M38 | Grader Correctness | planned |
<!-- generated:milestones:end -->

**Nothing is in progress.** Six milestones closed on 2026-08-18 and the three that remain - M23,
M33, and M38 - are planned and unstarted.

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

**M38** is planned before M33. Its research plan records the measured disagreement between the
deterministic grader and a human read of the frozen M24 honesty replay, and scopes the correction to
glossary-anchored rules, explicit seam comparison modes, and an offline re-grade.

**M35** closed last, and closes the labelling half of M24's missing control: `prompt_version` is
now recorded in the capture manifest, required by `freeze_capture`, validated at replay
`schema_version` 2, and drawn in the viewer's run header. An unlabelled capture cannot become a
labelled-looking replay. The three committed replays were backfilled from the prompt version in the
commit each capture ran at - sound for `t0025.7-acceptance` (`v1`, from a `git_sha` at a clean
worktree), an inference from the adding commit for the other two.

**M32** and **M36** also closed on 2026-08-18: M32 made the model-facing string surface knowable
without changing a word of it, and M36 broke the M31 check deadlock that left a ticket branch
adding a `docs/entries/` file with no passing state. M33 and M35 were allocated out of the T0032.4
spike's triage. **M34** then closed its serving-path defect on 2026-08-18: the message-count cap
became a six-turn window that retains complete user turns. **M30** closed on 2026-08-17 - the
`freeze` command, the surviving T0025.7
capture at `evals/replays/t0025.7-acceptance.json`, and **D-046** on what a replay keeps; the
T0027.3 DeepSeek capture that motivated it was already lost and stays lost. Per-milestone detail
is in [Tickets](Tickets.md) and the [ticket archive](archive/Tickets_Archive.md).

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
- The primary worktree's uncommitted `docs/Tickets.md` draft is gone as of 2026-08-17; the untracked
  research plan beside it remains, scoping serving reliability, operational telemetry, and a
  production evaluation loop as T0027-T0029 - numbers already spent. Superseded as written;
  re-numbering it through [`roadmap.yaml`](roadmap.yaml) is the only way it lands. This is the drift
  T0031.1 prevents. Its §1.1 also concludes the 2026-08-13 outage was a model-provider failure,
  which the direct probes recorded in [Resolved Issues](Resolved_Issues.md) disprove: that section
  is wrong, not merely stale.
- The duplicate `DEEPSEEK_API_KEY` line in `.env.example` is **gone as of 2026-08-18**, discarded
  by the integration step rather than carried a third time, along with an uncommitted
  `docs/roadmap.yaml` that was an older draft of the M37 block already merged through PR #71.
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
- `scripts/vietnamese_prompt_spike.py` - Measure Vietnamese prompt variants against the
  fixture-backed production agent.
<!-- generated:scripts:end -->

## Build and test status

| Check | Most recent recorded result |
|---|---|
| `python scripts/docs_lint.py` | Exit 1 on 2026-08-18 in this clone, on the untracked production-readiness plan only - four `link-path` findings and one `orphan`, all inside the superseded document [Carried work](#carried-work) records. It is untracked, so CI never sees it and every other check passed. Naming its path here reproduced the same finding from the other direction, which is why this row describes it instead. The `frozen` findings an integration session also sees are the check working: it fires on any write to a frozen register, and the integration step is the one writer allowed to make them |
| `python scripts/docs_build.py --check` | Exit 0 on 2026-08-18; every generated region current |
| `uv run pytest -q` | 556 passed, 1 skipped, 30 deselected, and 45 subtests passed on 2026-08-18, in 11.3 s |
| `uv run ruff check .` | Passed on 2026-08-18 |
| `uv run mypy` | Success: no issues in 44 source files on 2026-08-18 |
| `uv run python -m evals.replay` | Exit 0 on 2026-08-17 against the frozen evidence, with a database up. Not re-run by the integration step that published T0031.3: Docker was not running, so nothing listened on 5432 or 5433, which is the recorded precondition rather than a result |

The one skip is environmental: the migration round-trip needs `SCRATCH_DATABASE_URL`. The default
suite deselects live eval tests by design. A run with the fixture Postgres unreachable reports 10
skips and takes minutes instead of seconds - the hang [Known Issues](Known_Issues.md) records.

The skill-parity skip became a **failure** and was fixed on 2026-08-18: the gitignored
`.claude/` copy of the ticket-prompt skill predated T0031.1 and still told coders to take their
number from `Tickets.md`. See [Known Issues](Known_Issues.md); only the tracked
`skills/generate-ticket-prompt/SKILL.md` is authoritative.

Two command traps, both measured on 2026-08-17. A bare `python -m pytest` cannot import `slowapi`
and fails collection on 23 modules, so use `uv run`. And a fresh worktree has no `.env`, since it
is gitignored and therefore per-worktree; without the runtime variables set, ten modules fail
collection with `ConfigLoadError`. The dummy values in
[`ci.yml`](../.github/workflows/ci.yml) are enough.

## Registers

Open risks and maintainer actions: [Known Issues](Known_Issues.md). Closed entries and their
resolution records: [Resolved Issues](Resolved_Issues.md).

## Next recommended ticket

T0033.1 - the Vietnamese language milestone. M34 took the previous recommendation on 2026-08-18,
closing `KI-2026-08-17-vietnamese-spike-multiturn` after reproducing and correcting its
message-count eviction mechanism. M33 is the next planned milestone, while M23 remains the release
cut and still owes its DoD sweep and terms posture.

Two things sit beside it, both small and both about M24's residue rather than new capability.
`KI-2026-08-18-absent-field-grader-stale` is the cheapest useful work in the repository right now:
until the absent-field scenario's expectations are reconciled with the truthful listing-expiry
answer T0024.2 introduced, two of M24's seven failures cannot be read as either pass or defect. And
with M35 landed, re-capturing the missing `v2` control
(`KI-2026-08-18-honesty-gate-has-no-control`) would now produce a correctly labelled baseline at
M27's measured 5m20s for about $0.04.

**M23** (v1.0 release cut) is unblocked on the cron but should still not be taken next: its DoD
sweep owes decision **D9** a read on honesty, and that read is only worth making once those two
failures are triaged. Answer D9 against numbers, not against a milestone status line.

Whatever is taken next: M24's phrasings all resolve through `load_behavior_glossary()[TOKEN]` with
no inlined literals, which is the property M33's Vietnamese glossary was waiting on. M33 is free of
M24.

M31 and M36 closed, retiring the recommendation to build the protocol gate: `registry`, `scope`,
and `frozen` run in CI and a ticket branch can now satisfy all three. What is not retired is that
the `docs` job is advisory rather than required - `KI-2026-08-18-docs-job-not-required`, a
maintainer decision rather than a ticket.

Since T0031.3 (PR #59), this section and the build-status table are all a human writes in this
file: the table is the result of running commands rather than a reading of the tree, so deriving
it needs a recorded result the build can read. Elsewhere, `Tickets.md` and the judgement of where
a raised issue belongs are what remain by hand - and only the second is a judgement.

T0023 - the release path - is unblocked on the cron: `Nightly ingestion` ran unattended on
`schedule` and succeeded four nights running (2026-08-14 through 08-17, the last at 03:02 UTC),
which satisfies the last row of [the activation runbook](T0020.4_Cron_Activation_Runbook.md) §7 and
the D-038 live schedule requirement. What it owes is its DoD sweep and terms posture. Of the
behavior failures M25 and T0027.3 measured - triaged in [Known Issues](Known_Issues.md) as 23 real
behavior and 10 grader phrasing artifacts - M24 closed the honesty subset it scoped and left the
helpfulness ones untouched and unowned.
