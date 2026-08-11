# Manual Verification Guide

The canonical home for manual-verification checklists that remain open or require a fresh run.
Completed-ticket checklists are preserved in
[`archive/Manual_Verification_Archive.md`](archive/Manual_Verification_Archive.md).
Dated live-pass logs remain in
[`archive/Manual_Verification_History.md`](archive/Manual_Verification_History.md).

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

## Archived checklist index

- T0000
- T0001
- T0002
- T0003
- T0004
- T0005
- T0006.1
- T0006.2
- T0006.3
- T0006.4
- T0006.5
- T0006.6
- T0006.7
- T0006.8
- T0006.9
- T0006.10
- T0007.1
- T0007.2
- T0007.3
- T0007.4
- T0008.1
- T0008.2
- T0009.1
- T0009.2
- T0009.3
- T0009.4
- T0009.5
- T0009.6
- T0009.7
- T0009.9
- T0010.1
- T0010.2
- T0010.3
- T0010.4
- T0010.5
- T0010.6
- T0010.7
- T0011.1
- T0011.2
- T0011.3
- T0011.4
- T0011.6
- T0012.4
- T0012.5
- T0012.6
- T0012.7
- T0012.8
- T0012.10
- T0014.1
- T0014.2
- T0016.1
- T0016.2
- T0016.3
- T0016.4
- T0017.1
- T0017.2
- T0018.1
- T0018.2
- T0018.3
- T0019.2
- T0019.3
- T0019.4
- T0019.5
- T0019.6
- T0019.7
- T0019.8
- T0019.9
- T0019.10
