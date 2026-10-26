# Evaluate agent behavior

Two plain-Python checks remain: the credential-free SQL guard gate, and the text-to-SQL baseline
that scores generated SQL offline.
There is no model judge and no retained-capture runner; both were deleted with the legacy harness
([ADR-0066](../decisions/adr-0066-evaluation-is-the-baseline-and-the-sql-guard-gate.md)).

| Check | Needs | Produces |
| --- | --- | --- |
| SQL guard gate | The fixture database | One JSON report and a shell exit code |
| Text-to-SQL baseline | A serving-model credential, then a frozen snapshot for scoring | Generated SQL, then a score report |

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

## The text-to-SQL baseline

The baseline generates SQL once and scores it offline as often as needed.
`generate` sends the first turn of every scored question through the product's own `generate_sql`
and saves the SQL with the prompt hashes, the model, and the timestamp.
`score` executes the saved SQL and the reference SQL against the frozen snapshot; it makes no model
calls.

```sh
uv run python -m evals.baseline_sql generate --out evals/runs/baseline/<name>.json
uv run python -m evals.baseline_sql score evals/runs/baseline/<name>.json --database-url <snapshot URL>
```

The scoring step verifies the loaded snapshot against the committed manifest before it scores
anything and refuses on a mismatch.
It reports pass counts for the `dev` and `held-out` splits and prints each non-pass with its reason.

## Milestone runs

A baseline milestone run is the committed evidence behind a reported number.
It is one immutable directory, `evals/runs/<date>-<label>/`, written by the command that produces the evidence:

```sh
# Layer 1 text-to-SQL run over the baseline dataset
uv run python -m evals.baseline_sql generate --milestone baseline-v1
uv run python -m evals.baseline_sql score evals/runs/2026-10-26-baseline-v1 \
  --database-url "$BASELINE_DATABASE_URL"

# Re-score a committed run without a model call (a SQL metric still needs its database)
uv run python -m evals --rescore evals/runs/2026-10-26-baseline-v1 \
  --database-url "$BASELINE_DATABASE_URL"
```

A baseline run is written by `generate` and completed by `score`; until `score` runs, its manifest says `status: generated` and re-scoring refuses it.

The directory holds three files:

| File | Contents |
| --- | --- |
| `manifest.yaml` | The lineage: commit (and whether the tree was dirty), prompt versions, model and temperature, the relevant settings, the dataset digest, and the snapshot manifest checksum from [#756](https://github.com/Park-Hip/InternHunterAgent/issues/756). The manifest also digests the other two files. |
| `captures.json` | The evidence scoring reads: each question and the SQL generated for it. A baseline run never stores the rows it returned. |
| `scores.json` | The scores the run recorded, grouped by metric exactly as the CLI prints them. |

`--milestone` refuses to overwrite an existing run: a date and label identify one run, and a re-score must not silently replace its evidence.
`.gitignore` keeps every other file under `evals/runs/` local, and unignores only directories whose name starts with an ISO date.

**Re-scoring contract.** `--rescore` recomputes `sql_accuracy` from `captures.json` and requires each score, reason, and detail to match `scores.json` exactly.
A missing row, an extra row, or a changed score is a mismatch and exits nonzero.
The manifest digest is verified first, so editing the evidence is a refusal rather than a silent re-score of different data.

**Content rights ([#757](https://github.com/Park-Hip/InternHunterAgent/issues/757)).** A baseline run stores the generated SQL only, never the rows it read.
The full snapshot dump stays private ([#756](https://github.com/Park-Hip/InternHunterAgent/issues/756)).
Each manifest records this decision under `retention` so a reviewer does not have to infer it.

## Restoring the baseline snapshot

The baseline questions run against a frozen production snapshot
(`internhunter_snapshot_20261018`, 367 rows).
The dump is stored privately; restore it into a fresh database with:

```sh
uv run python scripts/restore_snapshot.py --dump <path-to-dump> --database-url <snapshot URL>
ALEMBIC_DATABASE_URL="<snapshot URL>" uv run alembic upgrade head
uv run python -m evals.snapshot_manifest --database-url <snapshot URL>
```

The second command brings the restored dump to the schema revision the manifest names.
The third command verifies the loaded rows against the committed manifest
(`evals/datasets/baseline_manifest.yaml`) and refuses to score on a mismatch.
