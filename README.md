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

The script is idempotent (`CREATE TABLE IF NOT EXISTS`) — re-running it is safe and a no-op.

### 3. Configure the app

Set `DATABASE_URL` in your environment, for example:

```bash
DATABASE_URL=postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter
```
