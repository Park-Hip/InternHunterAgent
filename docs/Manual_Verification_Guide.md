# Manual Verification Guide

The canonical home for manual-verification checklists that remain open or require a fresh run.
Completed-ticket checklists are preserved in
[`archive/Manual_Verification_Archive.md`](archive/Manual_Verification_Archive.md).
Dated live-pass logs remain in
[`archive/Manual_Verification_History.md`](archive/Manual_Verification_History.md).

> **Eviction:** A checklist leaves when its verification is recorded in the archive or its owning
> ticket is superseded by a replacement checklist.

## Current and unrun checklists

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
