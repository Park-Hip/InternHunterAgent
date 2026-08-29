# Operate

> **Eviction:** An operational procedure leaves when the deployed configuration or provider workflow
> it governs is retired and the replacement runbook is verified.

Deploy, observe, recover, ingest, and keep the service running.
Architecture rationale lives in [architecture.md](../architecture.md); configuration in
[reference/configuration.md](../reference/configuration.md).

## Topology

The serving agent runs one worker; the in-process rate limit means what it says because of it.
The production image is slim, non-root, and auto-deployed to Render on every push to `main`.

| Surface | Current operation | Configuration / check |
|---|---|---|
| API | Render web service, Docker runtime, Singapore, Free plan | Deploys `main`; `WEB_CONCURRENCY=1`; health: `/api/v1/health` |
| Database | Neon PostgreSQL 17 | Alembic head `c9d3e6f7a2b1`; use the direct host for migrations and cron |
| Tracing | Langfuse Cloud Hobby, JP | Render receives the Langfuse credentials as dashboard secrets |
| Public URL | `https://internhunteragent.onrender.com` | `/api/v1/health` for liveness; `/api/v1/ready` for database readiness |

The web service is declared in tracked [`render.yaml`](../../render.yaml).
It pins the service to `main`, uses `autoDeploy: true`, and declares required environment-variable
names.
It never contains secret values.

## Environment variables

| Variable | Where set | Render mode | Ingestion workflow | Notes |
|---|---|---|---|---|
| `DEEPSEEK_API_KEY` | `.env`; Render dashboard | Secret, `sync: false` | Not used | Serves the agent (D-045). Required whenever a profile selects `deepseek`, which both do. |
| `GROQ_API_KEY` | `.env`; Render dashboard | Secret, `sync: false` | Literal unused placeholder | The selectable second serving arm; unused while both profiles are `deepseek`. Ingestion does not call an LLM. |
| `OPENROUTER_API_KEY` | `.env` only | Deliberately undeclared | Not used | Eval-judge fallback key (OpenRouter arm of `build_judge()`); not declared for Render. The active judge runs on Google AI Studio via `GOOGLE_API_KEY`. |
| `GOOGLE_API_KEY` | `.env` only | Deliberately undeclared | Not used | Active eval-judge key (`gemma-4-31b-it` via Google AI Studio); not declared for Render. |
| `DATABASE_URL` | `.env`; Render dashboard | Secret, `sync: false` | GitHub `DATABASE_URL` secret | Cron and migrations use Neon's direct, non-pooled host. |
| `LANGFUSE_SECRET_KEY` | `.env`; Render dashboard | Secret, `sync: false` | Literal unused placeholder | Required by app settings; not read by ingestion. |
| `LANGFUSE_PUBLIC_KEY` | `.env`; Render dashboard | Secret, `sync: false` | Literal unused placeholder | Required by app settings; not read by ingestion. |
| `LANGFUSE_BASE_URL` | `.env`; Render dashboard | Dashboard value, `sync: false` | Not used | Local default targets a local Langfuse endpoint. |
| `LANGFUSE_TRACING_ENVIRONMENT` | `.env`; `render.yaml` | Tracked `production` value | Not used | Defaults to `local`; allowed values are `local`, `production`, and `evaluation`. |
| `LANGFUSE_RELEASE` | Optional `.env`; eval driver | Deliberately undeclared | Eval driver supplies its current git SHA | Optional local release override; Render's automatic `RENDER_GIT_COMMIT` takes precedence. |
| `HEALTHCHECKS_URL` | Optional `.env` only | Deliberately undeclared | GitHub `HEALTHCHECKS_URL` secret | Dead-man ping URL; not declared for Render. |
| `WEB_CONCURRENCY` | Render `render.yaml` | Tracked value | Not used | Fixed at `1` for the Free web service. |
| `PORT` | Render `render.yaml` | Tracked value | Not used | Fixed at `8000`. |

`sync: false` in `render.yaml` means Render must supply the value in its dashboard.
It does not synchronize or store the value in the repository.

No provider key is required to boot. `src/core/config.py` requires only `DATABASE_URL` and the
two `LANGFUSE_*` keys; each provider branch validates its own key and names the profile that
selected it. A deploy therefore fails on the first agent call, not at startup, if the key for the
provider named in `config/settings.yaml` is missing.

## Deploy flow

1. Merge or push the reviewed change to `main`.
2. Render auto-deploys the Docker service declared by `render.yaml`.
3. Confirm the Render deployment succeeds, then check `/api/v1/health` and `/api/v1/ready`.
4. If the deployment needs secrets, add or rotate them in the Render dashboard, never in git.

`render.yaml` controls the deploy branch, Docker paths, region, plan, health path, non-secret
values, and the presence of dashboard-managed secrets.
It does not create or update secret values in Render.

## Langfuse model definitions

The version-controlled pricing definitions live in
[`config/langfuse_models.yaml`](../../config/langfuse_models.yaml).
The committed DeepSeek V4 Flash rates were checked against both the
[English pricing page](https://api-docs.deepseek.com/quick_start/pricing/) and the
[Chinese pricing page](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) on 2026-08-21.

Validate the YAML locally without Langfuse credentials before reviewing or provisioning a change:

```bash
uv run python scripts/provision_langfuse_models.py --validate
```

The default command provisions missing definitions and refuses to overwrite a mismatched existing
definition.
Use `--check-remote` to compare the committed definitions with Langfuse without creating models.
Both provisioning modes require `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and
`LANGFUSE_HOST` or `LANGFUSE_BASE_URL`.
Run provisioning deliberately after confirming the pricing source and the target Langfuse project.

## Langfuse prompt registry

`config/prompts.yaml` is the reviewed source of truth for every model-visible prompt.
After a reviewed prompt change is merged or deployed, run the registry command with the Langfuse
credentials for the target project:

```bash
uv run python scripts/register_langfuse_prompts.py
```

The command assigns the `production` label and records the checked-out git commit on a changed
prompt version.
An exact rerun creates no new version.
Use `--dry-run` to validate and list the YAML inputs without credentials or a Langfuse request.
The running agent always uses the YAML text.
It only fetches the matching registered prompt reference to link the SQL generation observation.
If that optional lookup fails, SQL generation continues without a Langfuse prompt link.

## Database operations

### Initialise a local database

Start local Postgres, then apply the canonical Alembic migration chain. Alembic is the
sole executable schema baseline: there is no hand-maintained initialization SQL.

```bash
docker compose up -d postgres
uv run alembic upgrade head
```

### Reset local development data

This deletes the local schema and all current local rows, then rebuilds it from the
canonical Alembic revision chain. Never point this command at Neon or any production
database.

```bash
./scripts/reset_local_db.ps1
uv run python -m src.services.ingestion.loader
```

`reset_local_db.ps1` drops the local objects via `scripts/reset_db.sql` (a drop-only
script with no schema DDL) and then applies `uv run alembic upgrade head`.

### Apply a schema migration

Use Alembic for schema changes outside the local reset workflow:

```bash
uv run alembic current
uv run alembic upgrade head
```

The repository migration head is `c9d3e6f7a2b1`. Until this change is deployed, production
remains at `b7e2f4a91c3d`.
For Neon, set `ALEMBIC_DATABASE_URL` to the direct, non-pooled Neon connection URL before
running Alembic.
Do not use a `-pooler` host for migrations.
The guarded production adoption sequence remains in
[the cron activation runbook](cron-activation-runbook.md), section 3 D6.

For breaking-schema changes that require an incompatible type or semantic shift, follow the
[expand–migrate–contract procedure](../reference/schema.md#expandmigratecontract-procedure).
That procedure must complete before any destructive migration or contraction step; it ensures
the frozen agent-visible contract stays consistent across prompts, fixtures, and evaluations.

## Ingestion cron

The schedule is currently disabled: the two `schedule:` / `cron:` lines in
`.github/workflows/ingestion.yml` remain commented out.
Manual `workflow_dispatch` is available.
This is a gated pause, not the intended steady state: an active schedule is a required MVP
capability under [architecture.md](../architecture.md), so the demo runs below specification until the
gates clear.

Do not enable the schedule or set its secrets from this document.
The activation gates, their evidence, order, and sign-off state are maintained in
[T0020.4 Cron Activation Runbook](cron-activation-runbook.md).
The workflow's `DATABASE_URL` must use Neon's direct, non-pooled host because it writes data
and runs schema safety checks against production.

### Ingestion-run summaries

Every attempt appends one immutable row to `ingestion_runs`, retained indefinitely for operational
trend analysis. It records UTC `started_at` / `finished_at`, the source, and one of three outcomes:
`completed`, `safety_aborted`, or `failed`. Counters are stage-complete facts: `fetched`, the raw
upsert totals, normalization `skipped`, `clean_loaded`, `expired_count`, and `pages_failed` are
written only after the relevant stage completes. A not-yet-reached or incomplete stage is `NULL`,
never a synthetic zero.

The row contains no raw payload, posting identifier, URL, title, company, exception message, or
traceback. Failures retain only a controlled `failure_phase` and code (`safety_check_failed` or
`unexpected_error`). The writer is deliberately best-effort: failure to store a summary is logged
but cannot mask or change the ingestion outcome or CLI exit code. The table is operational history,
not raw or clean job history; it has no API endpoint, retention sweeper, or effect on raw/clean
upsert semantics.

### VietnamWorks robots preflight

Before a VietnamWorks job API request, ingestion retrieves
`https://ms.vietnamworks.com/robots.txt` using the configured honest user agent and evaluates
`/job-search/v1.0/search`. A parsed policy is cached only in that source instance for five minutes.
A timeout, non-2xx response, malformed policy, or matching disallow rule fails closed: no job API
request or data write occurs, `ingestion.compliance_gate_blocked` logs the safe reason, and the
normal `ingestion.aborted` path exits non-zero. The dead-man healthcheck is not pinged on this
failed run, consistent with existing failed-ingestion behavior.

The archived `www.vietnamworks.com` robots capture does not authorize the `ms.vietnamworks.com`
API host. If the preflight reports `robots_unavailable`, `robots_malformed`, or
`robots_disallowed`, do not retry around it. Inspect the current policy, obtain maintainer review
for any material source-policy change, and retain the fail-closed configuration until permission is
clear.

### Unattended inactivity recovery

GitHub automatically disables a public repository's scheduled workflows after 60 days of
repository inactivity. The unattended REST recovery job (`scripts/recover_ingestion_workflow.py`,
issue #325) re-enables `ingestion.yml` and dispatches exactly one ingestion run when the workflow
state is `disabled_inactivity`. The maintainer approved this externally automated recovery in
`.crew/325-approved-plan.md`; it supersedes issue #298's manual-calendar-reminder posture while
retaining that issue's bans on synthetic commits and on no-op dispatches while the workflow is
already active. The superseding decision is recorded in full in the
[cron activation runbook](cron-activation-runbook.md), §8.

The job is idempotent and least-privileged by construction. It reads the workflow state and
performs no mutation while the state is `active`. Only `disabled_inactivity` triggers a write:
one enable call followed by one dispatch call, then the outcome is recorded. Every API or
dispatch failure is logged to stderr, pings the healthcheck failure endpoint, and exits non-zero.
A successful recovery or active no-op pings the base healthcheck endpoint, so a missed scheduler
tick is also visible. Repeated invocations are idempotent: a recovered workflow is observed
`active` on the next cycle and treated as a no-op.

The recovery credential is a repository-scoped GitHub App installation token (or fine-grained PAT)
with exactly `Actions: write` for this repository only. `contents: write` is forbidden: the
checked-in credential contract declares only `{"actions": "write"}`, the implementation calls
only Actions REST endpoints, and its focused tests reject `contents: write` without using real
credentials. The maintainer verifies the installed token's effective repository and permissions in
GitHub during provisioning; a bearer token cannot self-report its scope to the script. The job
writes no commits and never dispatches while the workflow is active.

The selected external host is a Render Cron Job (not cron-job.org, which can only issue HTTP
requests). The scheduler, owner, credential provisioning, alerting, and rollback procedure are
documented in [cron-activation-runbook.md §8](cron-activation-runbook.md). Do not provision the
external host, credential, or healthcheck from this document; provisioning is a maintainer action.

## Operational gotchas

- Runtime settings require `DATABASE_URL` and the required provider and tracing variables before the
  API can start.
- The ingestion workflow deliberately supplies literal unused provider and tracing placeholders,
  because ingestion needs configuration validation but makes no provider or tracing call.
- Rebuild the API image with `docker compose build --no-cache api` after changing copied YAML
  configuration so Docker cannot reuse a stale configuration layer.
- On native Windows, run the API through Docker rather than `uv run uvicorn`; the async checkpointer
  pool is incompatible with the default Proactor event loop.
- `pages_failed` is an operator-visible ingestion summary field, but it does not yet alter exit
  status; a page exhausted after retries is retried by the next scheduled run.
- The VietnamWorks preflight is the per-run access gate; the 2026-07-16 human review is
  point-in-time evidence and must be repeated if source behavior or terms change materially.
- Serving and ingestion deliberately maintain separate exact `clean_jobs` column lists to preserve
  layer isolation; update both with every migration or the startup guard will fail safely.
- `render.yaml` is the tracked deployment record, while the existing Render service remains
  dashboard-managed unless the maintainer deliberately performs a Blueprint sync.
- A failed Langfuse initialization logs a startup warning and disables tracing for that process;
  serving continues and the incident response table is the recovery path.
- The evaluation driver intentionally enables Langfuse in the `evaluation` environment.
  Each capture can therefore consume Langfuse Hobby-plan event ingestion and retained trace storage.
  Run the smallest scenario selection needed, and disable tracing explicitly only when an offline
  capture does not need trace, dataset-run, or score linkage.

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
GitHub issues (keep-alive windowing and cold starts) and the cron activation runbook.

## Incident response

| Symptom | First response |
|---|---|
| API unavailable | Check Render deploy logs, then `/api/v1/health` and `/api/v1/ready`. |
| Demo answers nothing while `/health` and `/ready` are green | Suspect a stale build first, not the model provider. Compare the deployed `app.js`, `styles.css`, and `index.html` against `main` with `git hash-object`; a mismatch means the running commit is not `main`, and a deploy is the fix. A `500` returned in milliseconds is too fast to be a model call. |
| Database readiness fails | Check Neon availability and `DATABASE_URL`; do not reset production. |
| Ingestion fails | Inspect the GitHub Actions run and follow the activation runbook before retrying. |
| Schema mismatch | Stop the ingestion/deploy path and run the deliberate Alembic procedure above. |
| Missing traces | Verify Langfuse dashboard credentials and `LANGFUSE_BASE_URL` in Render. |

For active risks and maintainer-owned actions, use GitHub Issues.
