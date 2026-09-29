# Agent v0 evaluation baseline

> **Last verified:** 2026-09-29
>
> **Eviction:** This record leaves `docs/refactor/` when the agent-v0 track reaches Stage 7 under
> [#472](https://github.com/Park-Hip/InternHunterAgent/issues/472) and a successor baseline is
> approved. Until then it is the measured reference point for every agent-v0 stage, and each later
> stage compares its own result against the numbers here.

This is the Stage 0 record for the agent-v0 track: current behavior, the evaluation baseline, the
environment limits of the machine that measured it, and the retention record for the v1 evaluation
assets.
It changes no runtime code, no prompt, no schema, and no scenario.
Every claim below is either a file path in this repository, a command output captured on
2026-09-29, or an issue reference.
Anything not evidenced by one of those three is written here as unknown, not as a finding.

## Reference commits

| Role | Commit | Note |
| --- | --- | --- |
| Baseline measured here | `7769a82` | `origin/main` at 2026-09-29, the harness rebuild from #476. |
| Last commit containing the v1 tree | `25a8a00` | `7769a82^`. The v1 harness and registry exist only here and in later history. |

The worktree for this record fast-forwarded from `25a8a00` to `7769a82` before measuring, so every
number in this document describes the current `origin/main` harness and not the superseded one.

## Serving surface, as it behaves today

### The field contract

`clean_jobs` has 22 physical columns, frozen for the serving path in
[`src/api/schema_guard.py`](../../src/api/schema_guard.py).
The agent may see 16 of them.
The remaining six are bookkeeping and lifecycle state that no tool projects.

| Group | Count | Columns |
| --- | --- | --- |
| Agent-visible | 16 | `id`, `source_url`, `title`, `company`, `role`, `description`, `tech_stack`, `job_level`, `location`, `listing_expires_on`, `created_on`, `is_internship`, `salary_min`, `salary_max`, `salary_currency`, `is_salary_negotiable` |
| Bookkeeping, not agent-visible | 3 | `source`, `external_id`, `posted_date` |
| Lifecycle, hidden | 3 | `is_active`, `first_seen_at`, `last_seen_at` |

`source_url` is nullable in the schema, so "every listed row has a link" is not a schema
guarantee.
A stage that needs it must state the disclosure rule explicitly rather than infer it.

### The legacy request path

Every ordinary question still travels this path, and no stage of the agent-v0 track may change
more than one link in it at a time.

1. The API layer receives the question and the agent runtime runs the ReAct loop.
2. The loop calls the in-process FastMCP surface, which exposes exactly two tools:
   `query_clean_jobs` and `get_job_details`.
3. `query_clean_jobs` asks the `sql_generation` model profile to write SQL.
4. The SQL is checked by a regex validator, then bounded by `agent.query.max_rows`.
5. The executor runs it against `clean_jobs` and the rows are formatted and caveated.
6. The model composes the final answer from the rendered tool text.

The `sql_accuracy` evaluation metric measures step 4 and 5 only.
It says nothing about whether the answer in step 6 is grounded, which is why the metric set also
carries judge metrics.

### Prompts, models, and limits

| Setting | Value | Source |
| --- | --- | --- |
| `system`, `schema_context`, `sql_generation` prompt versions | `v13`, `v11`, `v13` | [`config/prompts.yaml`](../../config/prompts.yaml) |
| Prompt deployment label | `production` | `agent.prompts.deployment_label` |
| ReAct deployment | `deepseek_flash` (`deepseek/deepseek-v4-flash`, temperature 0.2) | `agent.react` |
| SQL generation deployment | `deepseek_flash` (temperature 0.0) | `agent.sql_generation` |
| Judge | `google` / `gemma-4-31b-it`, separate from serving | `eval.judge` |
| Row display cap | 20 (`agent.query.max_rows`) | `agent.query` |
| Detail id cap | 3 (`agent.query.max_detail_ids`) | `agent.query` |

The checked-in prompt text is a release-pinned fallback.
The live text comes from the pinned `production` label, so a local run against
`config/prompts.yaml` is not evidence of what production served.

## Evaluation baseline

### What exists after the harness rebuild

| Item | Value |
| --- | --- |
| Harness modules | 12 Python modules under `evals/` |
| Focused tests | 7 modules under `tests/evals/`, 72 tests collected, 12 of them `eval`-marked |
| Scenario registry | [`evals/datasets/scenarios.yaml`](../../evals/datasets/scenarios.yaml), 50 scenarios |
| Scenario shape | 34 single-turn, 16 conversational |
| Requirement coverage | 29 distinct `G` identifiers |
| Declared metrics | `tool_correctness`, `sql_accuracy`, `grounded`, `on_topic`, `memory`, `rubric` |
| Fixture | [`evals/fixtures/seed_eval_db.sql`](../../evals/fixtures/seed_eval_db.sql), 24 seeded rows |
| Fixture database | `postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter_eval` |
| Serving database | Neon PostgreSQL in production, separate from the fixture, per [ADR-0031](../decisions/adr-0031-neon-direct-not-pooler.md) |

### Measured results

| Command | Date | Result |
| --- | --- | --- |
| `uv run pytest tests/evals -q` | 2026-09-29 | 60 passed, 12 deselected, 2.89s |
| `uv run python scripts/docs_lint.py` | 2026-09-29 | exit 0, no findings |
| CI on `7769a82` (`docs`, `checks`, `Migration chain & ORM sync`) | merged 2026-09-29 | all SUCCESS |

The superseded harness on `25a8a00` reported 382 passed and 9 skipped for the same command, where
every skip was a fixture-Postgres test.
The two numbers are not comparable: the rebuild removed most of the v1 test modules, so the drop
is a deletion of checks, not a change in agent behavior.
Any later stage that quotes a percentage must say which commit and which harness it measured.

The nightly ingestion schedule on `main` was failing on every run from 2026-09-10 through
2026-09-14.
That is an ingestion concern tracked outside this track and says nothing about the evaluation
baseline.

### Environment limits of this measurement

The numbers above were produced on a machine with no Docker daemon, no fixture PostgreSQL, and no
provider credentials.
That limits what this record can claim.

- No live agent capture ran, because no serving-model credential was present.
- No judge score ran, because no judge credential was present.
- No fixture-database check ran, because nothing was listening on port 5433.
  The 24-row fixture count is a read of the seed file, not an observed database.
- The 12 `eval`-marked tests are deselected by the default `addopts` and were not executed.
- The full `uv run pytest` gate was not run on this machine, at the maintainer's instruction on
  2026-09-29. The CI `checks` job on `7769a82` is the recorded full-suite result instead.

A skipped or unavailable check is not a passing check.
Later stages must state their own environment limits rather than inherit this section.

## Defects that change what this baseline means

| Issue | Effect on the baseline | Status on 2026-09-29 |
| --- | --- | --- |
| #489 | The SQL span lookup matches a sibling of the tool span. Under MCP the nested SQL generation is a child of the tool span, so the lookup finds nothing and `sql_accuracy` is silently excluded from the gate denominator while the gate still reports green. The same lookup and the same reasoning are now in [`evals/run.py`](../../evals/run.py) after the rebuild. | Open. A fix is in progress on branch `Park-Hip/fix-evals-seam-2-sql-span-lookup-is-sibling-base`. |
| #175 | `HLP-ABSTRACTION-1` and `HLP-LOCATION-SYNONYM-1` have been failing since 2026-08-13. Both IDs are in the registry. | Open, unowned. |
| New | The evaluation manuals under `evals/` still describe the deleted v1 modules and the deleted registry. `evals/README.md`, `evals/pipeline.md`, `evals/authoring/index.md`, `evals/deterministic/index.md`, `evals/calibration/index.md`, `evals/semantic/index.md`, and `evals/replay/index.md` all cite paths that no longer exist. `docs/how-to/evaluate.md` was updated by the rebuild and is correct. | Needs a new issue. A docs-only cleanup, tracked separately from this baseline. |
| New | `docs/Docs_Conventions.md` documents both lint markers on the same line. `check_link_path` opens a block on the `begin` marker and never sees the `end` marker on that line, so the link-path check is silently disabled for the rest of that file. The `scenario-id`, encoding, and stack checks are unaffected. | Needs a new issue. |

The #489 row is the most consequential.
Until it is fixed, a green `sql_accuracy` gate on the current harness is not evidence that the SQL
seam is being measured.
A stage that claims a measured SQL result before that fix lands is overstating its evidence.

## v1 retention and restoration

`#472` requires the v1 evaluation assets to survive as historical evidence.
Most of them do, because the rebuild moved the registry rather than discarding it.
One does not survive in the tree at all, so the restoration procedure is recorded here.

| v1 asset | State on `7769a82` |
| --- | --- |
| Scenario registry, 50 scenarios | Migrated to `evals/datasets/scenarios.yaml` with the same IDs. Flow-style lists were expanded, `probe` was dropped, and `grading` became `metrics`. The v1 file itself is no longer in the tree. |
| Fixture seed and loader | Present and unchanged, 24 rows. |
| Committed replays | Present, 3 files under `evals/replays/`. |
| Archived replays and calibration | Present, including `evals/archive/replays/v6-baseline-20260823.json`. |
| Scenario matrices | Present: `evals/v1_scenario_matrix.observed.json` and `evals/archive/v1_scenario_matrix.md`. |
| Calibration versions | Present, `calibration_v6` through `v8`. |
| v1 harness modules | Removed by the rebuild and recoverable only from history. |

The v1 registry file is recoverable byte for byte, and this was verified on 2026-09-29 rather than
assumed.
The two supported ways to read the v1 tree are below.
The first restores one file; the second restores the whole v1 harness read-only, and is the right
choice when a question needs the old modules.

```sh
git show 7769a82^:evals/scenarios_v1.yaml > evals/archive/scenarios_v1.yaml
```

```sh
git worktree add --detach ../iha-v1-evidence 7769a82^
```

Both were run on 2026-09-29 from this worktree and both produced the v1 tree.
The restored file must stay outside the active `evals/` package so that no loader, test, or
documentation index can pick it up as a live registry.

## Open maintainer decisions

These are not this record's to make.
They are listed here so that no later stage mistakes silence for approval.

1. **Track ordering.** The agent-v0 track is a candidate for a recorded parallel exception in
   [`active-backlog.md`](active-backlog.md), which still lists command/serving configuration
   separation as ordered item 2. The maintainer has to choose between recording the exception and
   completing that item first. No `src/` change in this track may assume the exception.
2. **v1 registry placement.** Whether the restored v1 registry becomes a committed archive file or
   stays reachable only through the two commands above.
3. **Stale evaluation manuals.** Whether the manual cleanup becomes one issue or is folded into a
   later stage that rewrites the same files.

## Verification of this record

| Check | Command | Expected result |
| --- | --- | --- |
| Documentation hygiene | `uv run python scripts/docs_lint.py` | exit 0, no findings |
| Focused evaluation suite | `uv run pytest tests/evals -q` | 60 passed, 12 deselected |
| Manual read-back | Open the files named above on `7769a82` and confirm the field lists, prompt versions, row cap, metric names, and scenario counts | Every claim matches this document |

The full `uv run pytest` gate was intentionally not run on the measuring machine.
CI on `7769a82` is the recorded full-suite result.
