# Operations

> **Last verified:** 2026-08-10 against `render.yaml`, `.env.example`,
> `.github/workflows/ingestion.yml`, and the active migration/runbook records.
> This document is the single owner of deploy topology, operational configuration, database
> procedures, cron status, and incident response.
> For service selections and their rationale, see [Tech_Stack.md](Tech_Stack.md).

## Topology

| Surface | Current operation | Configuration / check |
|---|---|---|
| API | Render web service, Docker runtime, Singapore, Free plan | Deploys `main`; `WEB_CONCURRENCY=1`; health: `/api/v1/health` |
| Database | Neon PostgreSQL 17 | Alembic head `b7e2f4a91c3d`; use the direct host for migrations and cron |
| Tracing | Langfuse Cloud Hobby, JP | Render receives the Langfuse credentials as dashboard secrets |
| Public URL | `https://internhunteragent.onrender.com` | `/api/v1/health` for liveness; `/api/v1/ready` for database readiness |

The web service is declared in tracked [`render.yaml`](../render.yaml).
It pins the service to `main`, uses `autoDeploy: true`, and declares required environment-variable
names.
It never contains secret values.

## Environment variables

| Variable | Where set | Render mode | Ingestion workflow | Notes |
|---|---|---|---|---|
| `GROQ_API_KEY` | `.env`; Render dashboard | Secret, `sync: false` | Literal unused placeholder | Required by app settings; ingestion does not call an LLM. |
| `GOOGLE_API_KEY` | `.env` only | Deliberately undeclared | Not used | Optional Gemini eval key; not declared for Render. |
| `DATABASE_URL` | `.env`; Render dashboard | Secret, `sync: false` | GitHub `DATABASE_URL` secret | Cron and migrations use Neon's direct, non-pooled host. |
| `LANGFUSE_SECRET_KEY` | `.env`; Render dashboard | Secret, `sync: false` | Literal unused placeholder | Required by app settings; not read by ingestion. |
| `LANGFUSE_PUBLIC_KEY` | `.env`; Render dashboard | Secret, `sync: false` | Literal unused placeholder | Required by app settings; not read by ingestion. |
| `LANGFUSE_BASE_URL` | `.env`; Render dashboard | Dashboard value, `sync: false` | Not used | Local default targets a local Langfuse endpoint. |
| `HEALTHCHECKS_URL` | Optional `.env` only | Deliberately undeclared | GitHub `HEALTHCHECKS_URL` secret | Dead-man ping URL; not declared for Render. |
| `WEB_CONCURRENCY` | Render `render.yaml` | Tracked value | Not used | Fixed at `1` for the Free web service. |
| `PORT` | Render `render.yaml` | Tracked value | Not used | Fixed at `8000`. |

`sync: false` in `render.yaml` means Render must supply the value in its dashboard.
It does not synchronize or store the value in the repository.

## Deploy flow

1. Merge or push the reviewed change to `main`.
2. Render auto-deploys the Docker service declared by `render.yaml`.
3. Confirm the Render deployment succeeds, then check `/api/v1/health` and `/api/v1/ready`.
4. If the deployment needs secrets, add or rotate them in the Render dashboard, never in git.

`render.yaml` controls the deploy branch, Docker paths, region, plan, health path, non-secret
values, and the presence of dashboard-managed secrets.
It does not create or update secret values in Render.

## Database operations

### Initialise a local database

Start local Postgres, then apply the idempotent schema script:

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql
```

### Reset local development data

This deletes the local schema and all current local rows.
Never point this command at Neon or any production database.

```bash
docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql
uv run python -m src.services.ingestion.loader
```

### Apply a schema migration

Use Alembic for schema changes outside the local reset workflow:

```bash
uv run alembic current
uv run alembic upgrade head
```

The current production head is `b7e2f4a91c3d`.
For Neon, set `ALEMBIC_DATABASE_URL` to the direct, non-pooled Neon connection URL before
running Alembic.
Do not use a `-pooler` host for migrations.
The guarded production adoption sequence remains in
[the cron activation runbook](T0020.4_Cron_Activation_Runbook.md), section 3 D6.

## Ingestion cron

The schedule is currently disabled: the two `schedule:` / `cron:` lines in
`.github/workflows/ingestion.yml` remain commented out.
Manual `workflow_dispatch` is available.

Do not enable the schedule or set its secrets from this document.
The activation gates, their evidence, order, and sign-off state are maintained in
[T0020.4 Cron Activation Runbook](T0020.4_Cron_Activation_Runbook.md).
The workflow's `DATABASE_URL` must use Neon's direct, non-pooled host because it writes data
and runs schema safety checks against production.

## Keep-alive and idle pools

The project targets $0/month, below its $10/month ceiling.
Render Free can cold-start, and a lightly used GitHub Actions schedule can be auto-disabled after
60 days of repository inactivity.
The separate cron-job.org keep-alive job is running on `*/12 7-22 * * *` in ICT and targets
`GET /api/v1/health`.
That is 80 pings per day across the intended waking-hours window.
The first 07:00 wake-up can time out while Render starts from its overnight sleep, and a missed
ping leaves a 24-minute gap that is long enough for the 15-minute idle timer to spin the service
down.
The job's 12-minute cadence otherwise keeps the service warm from 07:00 until about 23:03 ICT,
or roughly 498 instance-hours per month, below the 750-hour Free cap.
The recorded observation confirms the checkpointer's idle Neon pool does not keep compute awake,
so the `/health` pings do not hold Neon active between requests.
This external job is unrelated to the unavailable GitHub `keepalive-workflow` action.
The remaining cost decision and the separate ingestion-cron activation gates remain in
[Known_Issues.md](Known_Issues.md) and the cron runbook.

## Incident response

| Symptom | First response |
|---|---|
| API unavailable | Check Render deploy logs, then `/api/v1/health` and `/api/v1/ready`. |
| Database readiness fails | Check Neon availability and `DATABASE_URL`; do not reset production. |
| Ingestion fails | Inspect the GitHub Actions run and follow the activation runbook before retrying. |
| Schema mismatch | Stop the ingestion/deploy path and run the deliberate Alembic procedure above. |
| Missing traces | Verify Langfuse dashboard credentials and `LANGFUSE_BASE_URL` in Render. |

For active risks and maintainer-owned actions, use [Known_Issues.md](Known_Issues.md).
