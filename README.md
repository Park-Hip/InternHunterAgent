# InternHunterAgent

## Local Database Foundation

This ticket adds a local Postgres foundation for the clean jobs dataset.

### 1. Start Postgres

From the repository root:

```bash
docker compose up -d
```

The service exposes Postgres on host port `5433` (mapped to the container's `5432`) and defaults to the `internhunter` database.

### 2. Seed the `clean_jobs` table

Use `psql` from your machine if it is installed:

```bash
psql -h localhost -p 5433 -U internhunter -d internhunter -f scripts/init_clean_jobs.sql
```

If you prefer to run the seed from inside the container:

```bash
docker compose exec -T postgres psql -U internhunter -d internhunter < scripts/init_clean_jobs.sql
```

### 3. Configure the app

Set `DATABASE_URL` in your environment, for example:

```bash
DATABASE_URL=postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter
```
