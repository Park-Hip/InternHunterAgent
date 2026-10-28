# Evaluate agent behavior

The evaluation path has three parts: the credential-free SQL guard gate, the Layer 1 text-to-SQL
diagnostic, and the agent baseline run.
The agent run is the headline B2 to B5 measurement.
Its conversation runner is [`evals/agent_runner.py`](../../evals/agent_runner.py) and drives every
baseline conversation through `stream_agent_response` ([#759](https://github.com/Park-Hip/InternHunterAgent/issues/759)).
There is no model judge, and no judge provider is called.
The scenario harness and DeepEval judge were deleted with the legacy evaluation path
([ADR-0066](../decisions/adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md)).
[ADR-0067](../decisions/adr-0067-agent-run-milestones-and-deterministic-answer-checks.md) adds the
agent-run milestone and the deterministic answer checks.

| Part | Needs | Produces |
| --- | --- | --- |
| SQL guard gate | The fixture database | One JSON report and a shell exit code |
| Layer 1 text-to-SQL | A serving-model credential to generate, then a snapshot reader to score | Generated SQL, then a score report |
| Agent baseline run | A serving-model credential and the snapshot reader to capture, then the reader again to score | A committed capture, scores, and a hand-review sheet |

## The baseline case files

The baseline is four files, each with one role (#761).
[`evals/baseline_dataset.py`](../../evals/baseline_dataset.py) loads and validates all of them before a runner reads one case.

| File | Split | Cases | Purpose |
| --- | --- | --- | --- |
| [`baseline.yaml`](../../evals/datasets/baseline.yaml) | `dev` | 36 | The #708 corpus. All of it is dev: the old 12 held-out cases were used while tuning `sql_generation`, so they are regression cases now |
| [`paraphrases.yaml`](../../evals/datasets/paraphrases.yaml) | `dev` | 6 | Dev questions reworded, with the original reference SQL, to measure wording sensitivity |
| [`held_out.yaml`](../../evals/datasets/held_out.yaml) | `held-out` | 30 | Fresh questions written after the dev set was frozen. Includes the split breakdowns, the four-turn paging conversation, and the refused statements from [#745](https://github.com/Park-Hip/InternHunterAgent/issues/745) |
| [`safety.yaml`](../../evals/datasets/safety.yaml) | `safety` | 4 | Destructive, injection, and secret-exfiltration arms, plus an injection carried by posting text |

The loader is the gate, and it refuses a file rather than guessing:

- `answerable` is a quoted enum: `"yes"`, `"no"`, or `"partial"`.
  `expect.refusal` is a quoted enum too.
  PyYAML reads a bare `yes`/`no` as a boolean, so an unquoted value would silently become `True`/`False` and change what the case expects.
  The loader checks the YAML node before `safe_load` can lose that distinction.
- A case's `split` must match the file it lives in, so a held-out case cannot drift into the dev corpus by a one-word edit.
- A paraphrased case must keep the original's reference SQL, comparison mode, answerable value, and turn count, and must actually reword the first turn.
- Every reference statement must pass `validate_sql`, and an `ids` or `count` case must project exactly the column its comparison reads.
- A refused statement or safety case must carry an `expect` block and no reference SQL.

A committed run records a digest per case file, so editing a file is a refusal on re-score.
[`evals/datasets/archive/`](../../evals/datasets/archive/) keeps the byte-identical 2026-10-19 file that the existing committed run names; the loader never reads the archive as an active case file.

**Held-out is not a tuning corpus.**
While changing a prompt, the model, a tool, or the query path, generate and read only the dev files:

```sh
uv run python -m evals.baseline_sql generate --split dev --out evals/runs/baseline/dev.json
```

A held-out run is generated at a milestone, after the change is frozen.
Read its per-question failures only after that run is committed, so a fix is not made against the question that is supposed to measure the fix.
The agent runner follows the same rule: use `--split dev --out` while tuning, and a milestone run after the change is frozen.

## The SQL guard gate

This is the gate.
It needs the fixture database and nothing else: no serving model, no judge, no secret, and no
network.
It is the successor ADR-0060 required when it retired the v0 acceptance gate.

```sh
docker compose up -d postgres
uv run python -m evals.fixtures.loader
uv run python -m evals
```

The command writes `evals/runs/sql-gate-latest.json` and prints the same rows as a table.<!-- lint-allow-link-path -->
`--out` writes the report elsewhere, and `--ids R01-list-role-city,R02-count-corpus` narrows the
run.

### The fixture reader role

The fixture loader owns the `internhunter_eval` schema as `internhunter` and uses the
owner DSN only to build and seed it.
The gate's execution path must not read as that owner, because PostgreSQL lets a table owner
bypass grants.
`evals/fixtures/loader.py` therefore provisions a dedicated `internhunter_eval_reader` login role
and grants it `CONNECT`, schema `USAGE`, and column-level `SELECT` on the 16 contract columns of
`clean_jobs`.
The role holds no table-level `SELECT` and no write privilege, mirroring production's
`internhunter_agent` boundary from [#722](https://github.com/Park-Hip/InternHunterAgent/issues/722).

For the gate, `evals/env.py` binds `AGENT_DATABASE_URL` to `eval.fixture.reader_database_url`, so the
tool, the executor, and `evals/sql_check.py` all read through the restricted role.
`DATABASE_URL` stays on the owner for fixture loading.
The DSNs are non-secret and are local or CI only; the loader resets the reader password from that
config on every rebuild.

**A table rebuild re-applies the grants.**
`load_fixture()` and `reset_fixture()` drop and recreate the schema, apply the Alembic chain, seed
the 24 rows, and then call the reader provisioning step again.
That step verifies the post-condition in PostgreSQL (visible columns readable, table-level and
hidden-column `SELECT` absent) and fails the loader rather than leaving an evaluation on the wrong
side of the boundary.
If you apply Alembic directly to the fixture without the loader, run
`uv run python -m evals.fixtures.loader` afterward.
A star or hidden-column read now fails with SQLSTATE 42501 instead of returning the five hidden
ingestion columns, and the tool maps that refusal to `rejected`.

The gate runs every reviewed case in
[`evals/datasets/sql_guard.yaml`](../../evals/datasets/sql_guard.yaml) through the guard
(`validate_sql`) and then runs the reviewed SQL as written against the fixture; it scores two
deterministic metrics:

| Metric | Grades |
| --- | --- |
| `guard_correctness` | The `validate_sql` verdict against the reviewed one. A rejected case also pins the rule that must reject it, so widening the validator cannot quietly drop the guard's floor |
| `result_equivalence` | The rows the reviewed SQL returns on the fixture, against a reviewer-written reference, through `evals/sql_check.py` |

The corpus has 20 cases in five classes: `reviewed` questions the guard must accept, including the
CTE and split-column breakdowns and the `FETCH FIRST` bound; the guard's floor (`hidden` and `cost`
statements that must stay rejected); `ambiguous` accepted risks (A01-A03) that pin today's behavior
and name the risk; and one injection carried by posting text.
An accepted risk is a case, not prose: a guard that starts refusing one turns the gate red and the
[ADR-0060 risk table](../decisions/adr-0060-retire-the-agent-v0-bundle.md) has to move with it.

**The gate fails rather than skips.**
If the fixture database is unreachable it exits 2 with a message naming the command that starts it.
An unavailable database reported as green is the failure mode this gate exists to remove.

### What the gate refuses to accept

| Condition | Why it fails |
| --- | --- |
| A verdict other than the reviewed one | The reviewed statement is the case's assertion; reviewed SQL the guard rejects, or forbidden SQL it accepts, is a defect |
| A rejected case rejected by a different rule | The floor is a pass/fail condition: the self-join, `pg_sleep`, multi-table, hidden-column, and server identity rules must each still reject their own case |
| A result other than the reviewed one | The reference was reviewed, and `tests/evals/test_sql_gate.py` pins the gate's grading and its refusals |

The gate is deliberately stricter than a rate.
A percentage would let a false success be offset by an easy pass.
If a future maintainer wants a rate, that is a new decision with its own evidence.

The cross-currency false-success class used to be graded here through the obligation detector,
which [#702](https://github.com/Park-Hip/InternHunterAgent/issues/702) deleted with the caveat
machinery.
That risk now belongs to the `sql_generation` rule that every salary aggregate groups by
`salary_currency`, and the baseline measures it; R05, R06, and A02 keep the statement shapes
visible.

## Layer 1: text-to-SQL diagnostic

Layer 1 generates SQL once and scores it offline as often as needed.
`generate` sends the first turn of every scored question through the product's own `generate_sql`
and saves the SQL with the prompt hashes, the model, and the timestamp.
`--split dev` keeps held-out questions out of a tuning pass; `--split all` is the default and is
what a committed run measures.
`score` executes the saved SQL and the reference SQL against the frozen snapshot; it makes no model
calls.
Layer 1 is a component diagnostic, not the headline B2, because it never sees the agent's tool calls,
the validator verdict, or the answer.
It runs one temperature-0 generation per scored question (`eval.baseline.layer1_repeats: 1`), because
the `sql_generation` profile is deterministic.

```sh
uv run python -m evals.baseline_sql generate --out evals/runs/baseline/<name>.json
uv run python -m evals.baseline_sql score evals/runs/baseline/<name>.json --database-url <snapshot reader URL>
```

The scoring step verifies the reader role and the loaded snapshot against the committed manifest
before it scores anything and refuses on a mismatch or an owner connection.
A validator rejection is a failure and is never executed.
It reports pass counts for the `dev` and `held-out` splits and prints each non-pass with its reason.

## The agent baseline run

An agent run is the headline measurement for B2 to B5.
It drives each baseline conversation through the application service, so it includes the follow-up
turns, the tool calls, the validator, and the answer a user reads.
The runner is [`evals/agent_runner.py`](../../evals/agent_runner.py) and runs from the
`baseline_agent` command:

```sh
uv run python -m evals.baseline_agent run --milestone agent-v1 \
  --database-url "$BASELINE_DATABASE_URL"
```

It verifies the reader role and the snapshot before its first model call, asserts both serving-model
credentials, then drives `stream_agent_response` with an in-memory checkpointer so every follow-up
sees its conversation.
`--split dev --out evals/runs/baseline/agent-dev.json` is an inspection form: it writes the dev
capture without a milestone, and deterministic scoring still needs a complete milestone run.
A milestone requires every split.
The command writes the capture only; score it offline with the commands below.

### The capture point for executed SQL

The production MCP tools are discovered as usual and wrapped on the eval side.
The wrapper sees the exact tool arguments and the `ToolMessage` the production tool returns.
On success, `ToolMessage.artifact["structured_content"]` is the typed `QueryResult`, whose `sql`
field is the bounded statement `query_clean_jobs` actually executed.
That value is recorded as `executed_sql`.
The model's pre-bound `generated_sql` is not returned to a caller without a production change, so
this runner does not capture it; the scorer uses the executed statement as its basis.
A rejection arrives as an error-status message beginning with `rejected:` and is recorded as the
validator verdict.
No eval-only branch is added to the service or the tool.

### What it scores

`execution_accuracy` is B2: the exact result of the SQL behind the last `query_clean_jobs` call in a
turn.
The capture field `generated_sql` is the exact-match basis when a capture has it, because the tool's
own `LIMIT` and `OFFSET` are not the model's SQL.
The runner records `executed_sql` instead, so a run from this runner is compared on its executed
statement and records that basis.
When a truncated executed statement ends in the tool's row cap, the scorer removes that cap and
records `executed_without_cap` as the basis.
The comparison runs through the reader role and follows the question's `ids`, `count`, or `rows`
mode.
A validator rejection is a failure and is never executed.
A turn with no query call, no SQL, or a tool error fails.
A database error is `INFRA` and is not scored.

Execution accuracy applies to the 64 questions with a first-turn reference SQL, plus the 13
later-turn reference SQLs (027 to 032, the four narrow cases H20 to H23, and the three continuation
pages of H26).
The safety cases, the refused statements, the out-of-scope questions, and follow-up turns that only
need a detail call have no reference SQL, so execution accuracy does not apply there; their answers
still get the answer checks.
The safety and refused-statement cases are scored by `safety_refusal` instead.

The four answer checks use only the captured derived facts:

| Metric | Grades |
| --- | --- |
| `answer_faithfulness` | B3: every cited link exists in the captured `source_urls`, every count claim matches `count_values` or `total_rows`, a listing with rows cites a link, and a fallback answer does not claim rows |
| `result_communicated` | B4: an empty result, a cut-off list, a final page, and a continuation are each said when they apply |
| `answer_language` | B5: the answer is Vietnamese |
| `safety_refusal` | The case's `expect` block: the expected refusal is present, and no value in `forbid_any` appears in the answer. Only cases with an `expect` block get a row |

A check that does not apply is recorded with a null score and reported as not applicable.
It is excluded from the pass rate, never counted as a pass.
`safety_refusal` instead has no row on a case without an `expect` block, so it never enters that case's denominator.
Tool calls, latency, and tokens are stored per turn as instrumentation.
They are printed beside the scores and never gate one.

### The capture contract

The runner writes one capture record per question and repeat through
`milestone.write_agent_run`, which validates the complete capture before it becomes a committed run.
`captures.json` holds:

| Level | Fields |
| --- | --- |
| Capture | `schema_version`, `runner: agent`, `created_at`, `repeats`, `records`, and optional `model` and `prompt_versions` |
| Record | `id`, `split`, `need`, `repeat` (1-based), `turns` |
| Turn | `turn`, `question`, `answer`, `answer_source`, `latency_ms`, `tokens`, `tool_calls`, and optional `error` |
| Query call | `name`, `arguments`, `generated_sql`, `executed_sql`, `validator`, `result_shape`, `total_rows`, `rows_returned`, `page_offset`, `truncated`, `count_values`, `source_urls`, and optional `error` |
| Detail call | `name`, `arguments`, `rows_returned`, `source_urls`, and optional `error` |

`result_shape` is `rows`, `match_count`, or `summary`.
`total_rows` is the real match total, `rows_returned` is the page length, and `count_values` holds the
figures an aggregate row returned.
A page size never substitutes for a match total.
`truncated` is true only when a non-empty page shows part of a larger match set; an empty page past
the end is `no_more`, not `truncated`.
`answer_source` is `model` or `fallback`.
The runner records the full `request` argument, not the short form published in the public tool event.
It records `executed_sql` and leaves `generated_sql` out, for the capture-point reason above.
A validator rejection is recorded as `false`, as `{"valid": false, "reason": "..."}`, or as a string
starting with `reject`; the scorer never executes it.
Full result rows under `rows`, `raw_rows`, `jobs`, or `tool_output` are refused, because the full
production snapshot cannot be committed (#756).

### Scoring and review

```sh
# Capture a committed run: needs the serving credential and the snapshot reader.
uv run python -m evals.baseline_agent run --milestone agent-v1 \
  --database-url "$BASELINE_DATABASE_URL"

# Score a committed agent run: no model call, but the snapshot is needed.
uv run python -m evals.baseline_agent score evals/runs/<date>-<label> \
  --database-url "$BASELINE_DATABASE_URL"

# Regenerate the hand-review sheet from the committed evidence, without a database.
uv run python -m evals.baseline_agent review evals/runs/<date>-<label> \
  --out evals/runs/<date>-<label>/hand_review.md

# Re-score through the shared CLI and refuse any changed row.
uv run python -m evals --rescore evals/runs/<date>-<label> \
  --database-url "$BASELINE_DATABASE_URL"
```

`score` verifies the manifest digests, the digest of every baseline case file, the snapshot identity, and the reader role before it computes a row.
It uses the run's recorded `agent.query.max_rows`, not the current setting, so a later configuration
change cannot move a committed score.
It writes `scores.json` and, when the sheet does not exist, `hand_review.md`.
`review` needs neither a model nor a database; it reads the committed scores and renders the same
sheet.
`--rescore` needs the snapshot because execution accuracy executes the captured statements.

`hand_review.md` lists each turn's question, answer, tool facts, deterministic results, and blank
checks for the behaviors code cannot settle: invented postings, nuanced wording, concision, and
follow-up filter retention.
Annotate the sheet; do not edit `captures.json` or `scores.json`.

### Repeats

The agent run repeats every conversation `eval.baseline.agent_repeats` times (3 in the shipped
configuration).
Each repeat gets its own rows, and the report keeps them separate instead of averaging them away, so
variance stays visible.
The run records the count it used, and re-scoring follows that record rather than the live setting.
Layer 1 stays at one repeat because its profile is temperature 0.

**No agent number is reported until a real run is committed.**
The Layer 2 numbers in the behavior baseline are historical hand marks, not a result from this
scorer.

## Milestone runs

A milestone run is the committed evidence behind a reported number.
It is one immutable directory, `evals/runs/<date>-<label>/`, written by the command that produces the evidence.
Both runners share the layout:

```sh
# Layer 1 text-to-SQL run over the baseline dataset
uv run python -m evals.baseline_sql generate --milestone baseline-v1
uv run python -m evals.baseline_sql score evals/runs/2026-10-26-baseline-v1 \
  --database-url "$BASELINE_DATABASE_URL"

# Agent baseline run: capture through the service, then score offline.
uv run python -m evals.baseline_agent run --milestone agent-v1 \
  --database-url "$BASELINE_DATABASE_URL"
uv run python -m evals.baseline_agent score evals/runs/<date>-agent-v1 \
  --database-url "$BASELINE_DATABASE_URL"
uv run python -m evals.baseline_agent review evals/runs/<date>-agent-v1 \
  --out evals/runs/<date>-agent-v1/hand_review.md

# Re-score a committed run without a model call (execution still needs its database)
uv run python -m evals --rescore evals/runs/2026-10-26-baseline-v1 \
  --database-url "$BASELINE_DATABASE_URL"
```

A Layer 1 run is written by `generate` and completed by `score`; until `score` runs, its manifest says `status: generated` and re-scoring refuses it.
An agent run is written by `run` and completed by `baseline_agent score` in the same way.

The directory holds three files, plus the agent run's hand-review sheet:

| File | Contents |
| --- | --- |
| `manifest.yaml` | The lineage: commit and dirty flag, runner, prompt versions, model and temperature, the relevant settings including repeats and `agent.query.max_rows`, the digest of every baseline case file, and the snapshot manifest checksum from [#756](https://github.com/Park-Hip/InternHunterAgent/issues/756). The manifest also digests the evidence files. |
| `captures.json` | The evidence scoring reads. Layer 1 stores each question and the SQL generated for it. An agent run stores each question and repeat, every turn's answer, and the derived tool facts. Neither stores the rows it returned. |
| `scores.json` | The metric rows exactly as the CLI prints them. An agent run also stores the per-turn instrumentation. |
| `hand_review.md` | Agent run only: the deterministic facts and the blank manual checklist. |

`--milestone` refuses to overwrite an existing run: a date and label identify one run, and a re-score must not silently replace its evidence.
`.gitignore` keeps every other file under `evals/runs/` local, and unignores only directories whose name starts with an ISO date.

**Re-scoring contract.** `--rescore` recomputes `sql_accuracy` for a Layer 1 run and the four agent metrics for an agent run, and requires each score, reason, and detail to match `scores.json` exactly.
A missing row, an extra row, or a changed score is a mismatch and exits nonzero.
The manifest digest, every case-file digest, and the snapshot identity are verified first, so editing either evidence or a dataset is a refusal rather than a silent re-score of different data.
Instrumentation is reported evidence, not a gated metric: it is stored and printed, but `--rescore` does not compare it.

**Content rights ([#757](https://github.com/Park-Hip/InternHunterAgent/issues/757)).** A Layer 1 run stores the generated SQL only.
An agent run stores the answers and the derived tool facts: SQL, counts, links, and shape.
Neither stores the rows it read, so the full snapshot dump stays private ([#756](https://github.com/Park-Hip/InternHunterAgent/issues/756)).
Each manifest records this decision under `retention` so a reviewer does not have to infer it.

## Restoring the baseline snapshot

The baseline questions run against a frozen production snapshot
(`internhunter_snapshot_20261018`, 367 rows).
The dump is stored privately; restore it into a fresh database with the owner DSN:

```sh
uv run python scripts/restore_snapshot.py --dump <path-to-dump> --database-url <owner snapshot URL>
ALEMBIC_DATABASE_URL="<owner snapshot URL>" uv run alembic upgrade head
```

The second command brings the restored dump to the schema revision the manifest names.
Scoring must run as a non-owner reader, so create a dedicated role after the restore:

```sql
CREATE ROLE internhunter_snapshot_reader LOGIN PASSWORD '<password>';
GRANT CONNECT ON DATABASE <database> TO internhunter_snapshot_reader;
GRANT USAGE ON SCHEMA public TO internhunter_snapshot_reader;
REVOKE ALL PRIVILEGES ON TABLE public.clean_jobs FROM internhunter_snapshot_reader;
GRANT SELECT (
  id, title, company, role, description, tech_stack, location, source_url,
  job_level, listing_expires_on, created_on, is_internship,
  salary_min, salary_max, salary_currency, is_salary_negotiable
) ON TABLE public.clean_jobs TO internhunter_snapshot_reader;
GRANT SELECT ON TABLE public.alembic_version TO internhunter_snapshot_reader;
```

Point `BASELINE_DATABASE_URL` at that reader role.
The agent runner takes that URL as `--database-url` and binds it to `AGENT_DATABASE_URL` for the tool
path, so the captured tool reads use the same column-granted role as the offline score.
The scorer refuses a superuser, the table owner, table-level `SELECT`, a write privilege, a role that can read a hidden column, or a role that cannot read a contract column.
The reader also needs `SELECT` on `alembic_version`, because the snapshot check reads the migration revision; without it the revision cannot be verified and scoring refuses.
Verify the loaded rows and the revision with the reader URL:

```sh
uv run python -m evals.snapshot_manifest --database-url <reader snapshot URL>
```

The command reads the committed manifest (`evals/datasets/baseline_manifest.yaml`) and refuses to score on a mismatch.
