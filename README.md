# InternHunterAgent

## Local Database Foundation

This ticket adds a local Postgres foundation for the clean jobs dataset.

### 1. Start Postgres

From the repository root:

```bash
docker compose up -d
```

The service exposes Postgres on host port `5433` (mapped to the container's `5432`) and defaults to the `internhunter` database.

### 2. Initialise the database schema

Use `psql` from your machine if it is installed:

```bash
psql -h localhost -p 5433 -U internhunter -d internhunter -f scripts/init_db.sql
```

If you prefer to run it from inside the container:

```bash
docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql
```

The script is idempotent (`CREATE TABLE IF NOT EXISTS`) — re-running it is safe and a no-op. Routine startup should always use `init_db.sql`, never the reset script below.

### Resetting the database schema

`init_db.sql` never wipes data (`CREATE TABLE IF NOT EXISTS` silently skips a table that already exists, even with the wrong shape), so it cannot apply a schema change on its own. When the schema changes, run the destructive reset script instead, then re-ingest:

```bash
docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql
uv run python -m src.services.ingestion.loader
```

`scripts/reset_db.sql` drops both `clean_jobs` and `raw_jobs` (`CASCADE`) and recreates them via `scripts/init_db.sql`. Both tables are fully reproducible — `clean_jobs` is rebuilt by every ingestion run and `raw_jobs` is re-fetched from the source — so this is safe, but it does discard whatever rows are currently in Postgres. Only use it when the schema shape itself has changed, not for routine restarts.

### 3. Configure the app

Set `DATABASE_URL` in your environment, for example:

```bash
DATABASE_URL=postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter
```
