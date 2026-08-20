# Manual Verification Guide

The canonical home for manual-verification checklists that remain open or require a fresh run.
Completed-ticket checklists are preserved in
[`archive/Manual_Verification_Archive.md`](archive/Manual_Verification_Archive.md).
Dated live-pass logs remain in
[`archive/Manual_Verification_History.md`](archive/Manual_Verification_History.md).

> **Eviction:** A checklist leaves when its verification is recorded in the archive or its owning
> ticket is superseded by a replacement checklist.

> ⚠ Any checklist step that imports the project needs a worktree that can. A fresh worktree has no
> `.env` and ten test modules fail at collection with `ConfigLoadError`; copy `.env` from the
> primary worktree first. See [Known Issues](Known_Issues.md).

## Current and unrun checklists

Checklists below the marker are generated from the `## Manual verification` section of each file
under [`entries/`](entries/README.md) by `scripts/docs_build.py`, and one leaves when its entry
sets `verified: yes`. Edit the entry, not this region. Checklists after the region are
hand-written and predate `docs/entries/`. Path references inside it are exempt from `link-path`
for the same reason the entries themselves are: a checklist step may name a file it tells the
developer to create, and the text is not editable here anyway.

<!-- lint-allow-link-path:begin -->
<!-- generated:checklists:begin -->
### T0036.1: Exempt rebuilt registers from the scope check

1. On this branch, `uv run python scripts/docs_build.py` then
   `uv run python scripts/docs_lint.py --diff-base origin/main`. It must exit 0 with no output.
2. Append a line to `docs/Known_Issues.md` **outside** any `<!-- generated:...-->` region, stage
   it, and re-run the lint. Both `scope` and `frozen` must report that file. Revert the line.
3. Check out `codex/t0032.1-tool-surface`, copy this branch's `scripts/docs_lint.py` over it, run
   `docs_build.py` and then the lint with `--diff-base origin/main`. It must exit 0, where before
   this ticket it reported three registers as out of scope.

### T0035.1: Stamp prompt_version into the capture manifest and the viewer header

1. `uv run python -m evals.replay` must exit 0. Then set
   `evals/replays/t0025.9-committed.json`'s `schema_version` back to `1` and re-run: it must fail
   naming `schema_version`. Revert.
2. Delete the `prompt_version` line from the same file and re-run `evals.replay`: it must fail
   naming `prompt_version`. Revert.
3. Grade and view any capture recorded before this ticket:
   `uv run python -m evals.viewer evals/runs/<run>.json`. The run header must show
   `PROMPT VERSION not recorded` between the Git SHA and Baseline eligible. Add
   `"prompt_version": "v1"` to that run's manifest, re-render, and the same slot must read `v1`.
4. `uv run python -c "from evals import driver; print(driver.build_manifest()['prompt_version'])"`
   with the fixture Postgres up must print the value in `config/prompts.yaml` (`v3` today).

### T0033.5: Translate user-facing tool literals to Vietnamese

- Run the demo against the fixture database and force a multi-row result to confirm the Vietnamese
  result header while column names and source values remain unchanged.
- Force a truncated result and confirm the Vietnamese truncation notice.
- Submit invalid SQL through the tool and confirm the Vietnamese refusal preserves the validator
  reason.
- Request a nonexistent posting id and confirm the Vietnamese missing-posting message.
- Trigger a database failure and confirm the Vietnamese safe error without leaking the underlying
  exception.

### T0032.2: Record the model-facing string surface

- Add a temporary `return "test string"` to a tool function and run
  `uv run pytest tests/test_prompt_surface.py`.
- Confirm the inventory comparison fails and names the new literal.
- Remove the temporary literal and confirm the suite passes.
- Compare the inventory with a Langfuse trace before release to confirm every listed string reaches
  the model as expected.

### T0032.1: Finish decision 10 across the tool surface

- Configure the fixture database, the selected provider key, and Langfuse credentials.
- Start the app and ask for a role with no matching postings, such as `Do you have any COBOL jobs?`.
- Confirm the response does not contain `internship` and matches the zero-results wording.
- Ask what the assistant can help with and confirm its tool trace describes AI and data job and
  internship postings.

### T0031.4: Enforce the protocol in CI

1. `python scripts/docs_lint.py` exits 0 on a clean checkout and reports fifteen checks' worth of
   findings when something is wrong.
2. Add a path outside M31's scope, for example `touch src/scratch.py`, then run
   `python scripts/docs_lint.py --check scope`. It names the file and points at `roadmap.yaml`.
   Delete the file and it passes.
3. Hand-edit a line in `docs/Resolved_Issues.md`, then run
   `python scripts/docs_lint.py --check frozen`. It reports the register. Revert with
   `git checkout --`. Use that file rather than `Known_Issues.md`: the latter is in M31's declared
   scope, so the declared-scope rule clears it and the check correctly stays quiet.
4. Hand-edit a line **inside** a generated region of `docs/Known_Issues.md` and run
   `python scripts/docs_lint.py --check generated`. It fails, because the generator owns those
   bytes. `python scripts/docs_build.py` restores them.
5. Change a milestone id in `docs/roadmap.yaml` to a number that leaves a gap, then run
   `python scripts/docs_lint.py --check registry`. It names the skipped number. Revert.
6. `python scripts/docs_lint.py --check scope --diff-base no/such/ref` exits 0: an unresolvable
   base is silence by design.

### T0031.3: Derive the current-state snapshot

1. `python scripts/docs_build.py --check` exits 0 on a clean checkout.
2. Hand-edit a line inside the `milestones` region of `docs/Repo_Current_State.md`, then run
   `python scripts/docs_lint.py`. It fails, naming the file and telling you to run `docs_build.py`.
   Run `python scripts/docs_build.py` and the edit is reverted.
3. Change a milestone's `status:` in `docs/roadmap.yaml`, run `python scripts/docs_build.py`, and
   confirm the milestone table and the complete-count line both move. Revert.
4. Hand-edit a line inside the `snapshot` region and run `python scripts/docs_lint.py`. It still
   passes: that region is clone-local by design. `python scripts/docs_build.py --snapshot` restores
   it.
5. `python scripts/docs_build.py --check --snapshot` exits non-zero with a message explaining that
   the git region cannot be verified, rather than reporting a stale file.
6. Confirm `docs/Repo_Current_State.md` is at or under its 210-line cap: `python
   scripts/docs_lint.py --check size-cap`.

### T0031.2: Generate the registers from the entries

1. `python scripts/docs_build.py` prints `every generated region is already current`.
2. Edit one line inside a `<!-- generated:... -->` region by hand, then run
   `python scripts/docs_lint.py`. It must report a `generated` finding naming that file. Run
   `python scripts/docs_build.py` and confirm the edit is overwritten and the linter goes quiet.
   This is the check that matters: it proves a region cannot be hand-maintained.
3. Set `verified: yes` in this file, run the build, and confirm this checklist disappears from
   `docs/Manual_Verification_Guide.md`. Set it back to `no` and rebuild.
4. Open `docs/Known_Issues.md` and confirm the "Raised, not yet filed" region lists the issues
   below. Move one into a topic section, keeping its `KI-` id, rebuild, and confirm it leaves the
   region and the triage table is unchanged.
5. Confirm the text outside the regions is untouched: `docs/Completion_Reports.md` still opens on
   its hand-written preamble and still holds every report from before `docs/entries/` existed.

### T0031.1: Give parallel tickets a private write surface

1. `python scripts/docs_lint.py` exits 0 and prints nothing.
2. `python -m pytest tests/test_docs_lint.py -q` passes.
3. Add a throwaway `docs/entries/T9999.md`, re-run the linter, and confirm it reports no
   `size-cap` and no `orphan` finding for it. Delete the file.
4. Add a throwaway `docs/Scratch.md`, re-run the linter, and confirm it *does* report
   `size-cap: living document is missing from caps table`. Delete the file. This proves the
   exemption is scoped to `entries/` rather than switched off.
5. Open `docs/roadmap.yaml` and confirm M29 and M30 both list `evals/viewer.py` under `scope:`,
   which is the overlap that made them unsafe to run in parallel.
6. Ask for a ticket prompt via the `generate-ticket-prompt` skill and confirm the output names
   the allocated ticket id, the allowed paths, and the frozen registers.

### T0030.3: Decide frozen replay telemetry

1. Read D-046 in `docs/Decision_Log.md` and confirm it names both retained evidence and excluded
   per-turn telemetry.
2. Read the `replays/` row in `evals/README.md` and confirm it matches D-046.
3. Inspect `evals/replays/t0025.7-acceptance.json` and confirm it has no `trace_id`, `latency_ms`,
   token-usage, finish-reason, or tool-output field.

### T0030.2: Freeze the captures that are still exposed

1. Start the fixture database with `docker compose up -d` and rebuild it with
   `uv run python -m evals.fixtures.loader`.
2. Run `uv run python -m evals.replay --replay evals/replays/t0025.7-acceptance.json`.
3. Confirm the command exits 0 and the replay contains 13 completed turns, no `trace_id`, and no
   `latency_ms`.
4. In a clean checkout with no `evals/runs/` directory, repeat step 2.

### T0030.1: Give the replay format a writer

1. Freeze a completed capture with `uv run python -m evals.driver freeze <capture>.json --grade
   <grade>.json -o <replay>.json`.
2. Run `uv run python -m evals.replay --replay <replay>.json` and confirm it exits 0 against the
   frozen fixture.
3. Insert a non-empty `trace_id` into a copy of the capture, rerun `freeze`, and confirm it refuses
   the source path without creating output.
4. Inspect the replay and confirm it contains no `trace_id`, `latency_ms`, or token-usage field.

### T0024.3: Caveat-relay prompt contract

- Configure the fixture database, a selected-provider key, and Langfuse credentials.
- Start the app and ask a salary-ranking question that returns multiple currencies.
- Inspect the tool trace and confirm it includes a `MANDATORY CAVEATS` block.
- Confirm the final answer does not crown a cross-currency salary winner.
- Confirm the final answer preserves the caveat's uncertainty in natural language.

### T0024.2: Obligation seam and listing-expiry honesty guard

- Configure the fixture database, a selected-provider key, and Langfuse credentials.
- Start the app and ask which postings expire soon.
- Inspect the tool trace for `[LISTING_EXPIRY_NOT_DEADLINE]` with the glossary wording.
- Ask for an application deadline and confirm the final answer does not relabel listing expiry.
- Ask for a non-existent column such as applicant count.
- Confirm the tool uses the absent-field wording.
- Ask for a role with no matching postings and confirm the zero-results wording is unchanged.
<!-- generated:checklists:end -->
<!-- lint-allow-link-path:end -->

### T0027.4: Deployed demo on the DeepSeek default

The local half of this checklist passed on 2026-08-15. What remains needs a deploy, because the
serving provider changed and the Render service reads its key from the dashboard.

1. **Before merging to `main`,** add `DEEPSEEK_API_KEY` to the Render dashboard for the
   `InternHunterAgent` service. `render.yaml` declares it `sync: false`, so the repository never
   carries the value.
2. After the auto-deploy, open <https://internhunteragent.onrender.com>, ask one question, and
   confirm a real answer and a non-null `trace_url`. A healthy `/api/v1/health` proves nothing
   here: no provider key is required at boot, so a missing key surfaces only on the first query.
3. Confirm the Langfuse trace for that question records the DeepSeek model, not Groq.
4. Check the DeepSeek dashboard afterwards. Serving is metered now, at a measured ~$0.0005 per
   turn, so the spend should be cents-scale and should track demo traffic.

### T0025.4: Trace viewer and first-upstream-failure review

Generate a zero-quota sample with `uv run python -m evals.viewer --sample`, or generate a viewer
from a scenario-driver artifact with `uv run python -m evals.viewer evals/runs/run.json
--output evals/runs/run-viewer.html`.

- Open the generated HTML file locally and verify each turn shows the question, routing decision,
  generated SQL, rows returned, and final answer without expanding raw JSON.
- Use Previous/Next, the turn selector, and keyboard arrow keys to move between turns.
- Enter a note, reload the file, return to the same turn, and confirm the note remains.
- If browser site data is blocked, confirm a visible note-storage warning appears while Previous,
  Next, and the turn selector continue to work.
- Mark the earliest wrong seam only, then stop; downstream symptoms are not additional failures.
- Confirm the viewer is a local artifact and makes no request to `src/api/` or an external host.

### T0021.1: API read-path startup schema assertion

T0019.5 gave the **write** path a pre-flight `clean_jobs` contract check; the **serving**
path — the actual product — still booted unchecked and would fail mid-query on a
renamed or missing column. This ticket adds a boot-time guard (`assert_serving_schema`
in `src/api/schema_guard.py`) called inside `app.py`'s `lifespan`, after `load_settings()`
and before the checkpointer pool opens. Any schema mismatch (missing / renamed / extra
column), an absent table, or a DB-inspection failure aborts the FastAPI boot with
`SchemaGuardError` — a loud fast-fail instead of a live server that errors on the first
query.

**A. Suite green**

```
uv run pytest tests/api/test_schema_guard.py -v
uv run pytest && uv run ruff check . && uv run mypy
```

Expect `6 passed` on the targeted run; the full suite goes `329 → 335` (six net-new
cases). `mypy` must show only the two pre-existing baselined errors, no third.

**B. Layer isolation holds** *(the crux of the ticket)*

```
git grep -n "services.ingestion" src/api/schema_guard.py    # must print nothing
git grep -n "services.ingestion" src/api/                    # must print nothing
```

The serving guard imports only `src.core.*` + `sqlalchemy`. If either grep prints a
line, the ingestion package leaked into the serving path and the isolation rule is
violated.

**C. Happy boot** *(needs Docker Postgres up on the correct 22-column schema)*

```
uv run uvicorn src.api.app:app
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/v1/health
```

Expect: the app starts, logs show `api.schema_ok columns=22`, and the health curl
returns `200`.

**D. Drift fails the boot** *(scratch DB only — never Neon)*

```
docker compose exec -T postgres psql -U internhunter -d postgres \
  -c "CREATE DATABASE ih_guard TEMPLATE internhunter;"
docker compose exec -T postgres psql -U internhunter -d ih_guard \
  -c "ALTER TABLE clean_jobs RENAME COLUMN location TO location_old;"
DATABASE_URL="postgresql+psycopg://internhunter:internhunter@localhost:5433/ih_guard" \
  uv run uvicorn src.api.app:app
```

Expect: the app **fails to start**, with
`SchemaGuardError: clean_jobs schema drift detected: missing=['location'] unexpected=['location_old']`
and an `api.schema_drift` log line — **not** a started server that errors on the first
query. Clean up:

```
docker compose exec -T postgres psql -U internhunter -d postgres -c "DROP DATABASE ih_guard;"
```

> ⚠ Checks C and D require Docker Postgres and were **not run** in the implementing
> session (Docker unavailable). The six automated cases prove the diff/exception logic
> against a patched `session_factory` but not the live-DB boot end-to-end.

## Archived checklists

Completed-ticket checklists are indexed in the
[`Manual Verification Archive`](archive/Manual_Verification_Archive.md).
