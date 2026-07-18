# Deployment Research Plan — InternHunterAgent

> **Status:** Research **skeleton** / pre-design. This is an *outline of what to research*,
> not the findings. Each section states the question, what to search the web for, and the
> decision it will drive. Fill the "Findings" / "Decision" blanks as the research is done.
> Output feeds a future deployment design doc and `docs/Tickets.md` deploy tickets.
>
> **Constraint (standing):** hosting cost must be **free or minimal** — prefer free tiers;
> flag anything that risks a recurring bill.

---

## 0. What we are deploying (context — fill before researching)

So every option is judged against the *actual* system, list the moving parts first:

- **Serving path:** FastAPI app + LangChain agent (Groq LLM via API) + Langfuse tracing.
- **Datastore:** Postgres (`clean_jobs` served read-only to the agent; LangGraph
  checkpointer also uses Postgres).
- **Offline job:** scheduled data-ingestion (see `data-ingestion-stage.md`,
  `job-site-comparison.md`) — runs on a cron, writes `raw_jobs` → `clean_jobs`.
- **External deps that must be reachable from prod:** Groq API, Langfuse (cloud or
  self-hosted), the job-board source endpoints.
- **Expected traffic:** Demo / portfolio — single user or very low QPS. Scale-to-zero
  is acceptable; a cold start of 30–60 s is tolerable.

> The deploy target is **3 workloads, not 1**: (a) the web API, (b) the Postgres DB,
> (c) the scheduled ingestion job. Each section below should answer for all three.

---

## 1. Hosting platform for the FastAPI app

**Question:** Where does the always-on (or scale-to-zero) web API run, cheapest?

**Research / web searches:**
- `Render vs Railway vs Fly.io vs Koyeb free tier 2026 FastAPI`
- `free tier always-on web service no cold start 2026`
- `Hugging Face Spaces Docker FastAPI free hosting limits`
- `Google Cloud Run free tier scale to zero FastAPI cost`
- `fly.io free allowance 2026 changes`

**Compare on:** free-tier hours/limits, cold-start / spin-down behavior, Docker support,
custom domain + HTTPS included, RAM/CPU ceiling, region (latency to Vietnam users),
egress limits, does it sleep on idle.

**Findings:**

| Platform | Free limits (2026) | Spin-down / cold start | Docker support | Egress free | Vietnam latency | Verdict |
|---|---|---|---|---|---|---|
| **Render** | 750 instance-hours/workspace/month; 512 MB RAM on free instance | Spins down after **15 min** idle; restarts in **~1 min** | Yes — build from Dockerfile | 100 GB/month | Singapore region available (lower latency to VN than US-East) | **Best free option** for this project |
| **Railway** | $5 one-time trial credit, expires in 30 days; then Hobby plan at **$5/month** | No spin-down (always-on while credits/plan active) | Yes | Included in plan | US/EU regions | **Not free** — eliminated permanent free tier in 2023; not viable |
| **Fly.io** | Free tier removed 2024. New users get a **2-VM-hour / 7-day trial only**; minimum ~$5/month after | No spin-down on paid; legacy free users kept 3 VMs | Yes | Legacy: 100 GB; paid: varies | 30+ regions globally | **Not free** for new users; eliminated in 2024 |
| **Koyeb** | Was: 512 MB RAM / 0.1 vCPU / 2 GB SSD, 1 free instance. **⚠️ New signups for free Starter tier closed after Mistral AI acquisition (Feb 2026)** | Scaled to zero after 1 hr; cold start unknown | Yes | 100 GB/month | Frankfurt or Washington DC only | **No longer available** for new users; do not plan around it |
| **HuggingFace Spaces** | CPU Basic: 2 vCPU, 16 GB RAM — free. **Write access to `/tmp` only** (no persistent storage). 250 MB unzipped package size cap | No spin-down on CPU Basic; always-on | Yes — Docker Spaces | Not specified | US only | Viable for stateless API demo; no persistent disk is a limitation if any file state is needed |
| **Google Cloud Run** | 2M requests/month, 360K GB-seconds memory, 180K vCPU-seconds — **always-free tier**. Must link billing account (bill stays $0 within limits). Scale to zero when idle | Scales to zero; cold start on first request (typically **100–500 ms** for warm containers, longer for cold) | Yes — deploy from Dockerfile or source | 1 GB/month free egress to internet (then $0.08–$0.12/GB) | Closest region: `asia-southeast1` (Singapore) | Strong option — generous always-free tier, no spin-down penalty, best latency to VN via Singapore |

**Summary for this project:**
- **Render free tier** is the simplest path: connect GitHub, deploy Dockerfile, get `*.onrender.com` + auto TLS. 750 hrs/month is enough for a low-QPS demo (one service running ~24 hrs/day ≈ 720 hrs). Cold start of ~1 min after 15-min idle is acceptable.
- **Google Cloud Run** is the more scalable free option: true scale-to-zero with faster cold starts, a richer free quota, and Singapore region for better Vietnam latency. Requires linking a billing account (charge only if limits exceeded).
- Railway, Fly.io, and Koyeb are **not genuinely free** for new users in mid-2026.
- HuggingFace Spaces is viable only if the API is stateless and has no disk-write needs outside `/tmp`.

Sources:
- [Render free tier policy (render.com)](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [Railway free tier history (saaspricepulse.com)](https://www.saaspricepulse.com/blog/railway-pricing-history)
- [Fly.io free tier 2026 (saaspricepulse.com)](https://www.saaspricepulse.com/blog/flyio-free-tier-2026)
- [Koyeb free tier 2026 — Mistral acquisition note (srvrlss.io)](https://www.srvrlss.io/provider/koyeb/)
- [HuggingFace Spaces Docker (huggingface.co)](https://huggingface.co/docs/hub/en/spaces-sdks-docker)
- [Google Cloud Run free tier 2026 (lalatenduswain.medium.com)](https://lalatenduswain.medium.com/building-cloud-native-apps-for-free-in-2026-the-complete-developers-guide-to-google-cloud-s-3d93b77c4adb)
- [Cloud Run pricing (cloud.google.com)](https://cloud.google.com/run/pricing)

**Decision (2026-07-16):** **Render** free tier — Dockerfile deploy from GitHub, Singapore region, `*.onrender.com` + auto-TLS. Chosen over Cloud Run for zero-config simplicity (no billing account, no `gcloud`/Artifact Registry). 15-min idle spin-down + ~1 min cold start accepted for a portfolio demo. **Live: https://internhunteragent.onrender.com** (Free instance, `WEB_CONCURRENCY=1`).

### 1a. Cold-start mitigation — keep-alive ping (decided 2026-07-16, post-deploy)

**Why revisited:** the §1 decision accepted the ~1 min cold start as "tolerable" (§0, expected traffic). Post-deploy that reads worse than modelled: because T0018.2 serves the UI **same-origin**, Render serves `index.html` too, so a cold visitor gets a **blank tab for ~60 s** rather than a slow first answer. There is no UI-side loading state possible — the UI is behind the same cold process. Registered in `docs/Known_Issues.md` § Config, startup & deployment.

**The cold start is ~all Render, not Neon.** Render: 15-min idle spin-down, ~1 min restart (§1). Neon: 5-min suspend, ~300–500 ms resume, p95 ~2.6 s (§3). Neon is a rounding error; **swapping the DB or the stack would buy nothing** — the question was raised and closed on these numbers.

**Decision:** external scheduler (cron-job.org or UptimeRobot free) pinging **`GET /api/v1/health`** every 10–14 min on a **~07:00–23:00 ICT window**. Not yet applied — it is dashboard config, deliberately **not** its own ticket (2026-07-16); it folds into the ingestion milestone, which already defers external ping + dead-man's-switch (§9A) and needs the same machinery.

**Three constraints that shape it:**
1. **`/health`, never `/ready`.** `/ready` runs `SELECT 1` → holds Neon awake → 0.25 CU × 730 h ≈ **182 CU-h vs the 100 CU-h/month free cap** (§3). Pinging the wrong endpoint would break Neon's free tier to fix Render's. Same reasoning as the §9A decision to point Render's own health check at `/health`. *(Render's internal health checks do not prevent spin-down — only inbound external traffic does.)*
2. **Window it; do not run 24/7.** Render grants **750 free instance-hours/workspace/month**, and exhausting them *"suspends all of your Free web services until the start of the next month"* ([docs](https://render.com/docs/free)). 24/7 in a **31-day month = 744 h — a 6-hour margin** (this corrects the "≈ 720 hrs" estimate in the §1 summary above, which assumed a 30-day month and understates the risk). One overlapping redeploy or a second Free service crosses it, and the demo goes dark until the calendar flips. A 16 h/day window ≈ **496 h/month** — no cliff.
3. **Not GitHub Actions.** Free for public repos but UTC-only, auto-disables after 60 days idle (§8), and scheduled runs routinely drift 10+ min under load — fatal against a 15-min window. External scheduler is the right tool and stays out of the repo.

**Policy check (does the ping violate Render's terms?) — checked 2026-07-16 against Render's own docs + AUP, not blog posts:**
- **No written rule prohibits it.** Render's free-tier docs describe the spin-down in detail and never mention pinging, keep-alives, or uptime monitors. The AUP names no such practice.
- **One AUP clause has a foothold:** *"intentionally misuse the Service to avoid payment or financial responsibility."* A keep-alive's purpose is to obtain always-on behaviour Render sells at $7/mo. Render's support line is that the supported fix for cold starts is a paid instance. The companion clause — *"impose an unreasonable or disproportionately large load… especially for the purpose of evading payment"* — does **not** apply: one request per 10 min is negligible.
- **Counter-argument (arithmetic):** Render *grants* 750 h/month, and 24/7 for a 31-day month is 744 h. **The grant exceeds always-on.** Were continuous free uptime the abuse that clause targets, the allowance would sit below 730 h. Render also enforces the allowance by automatic metering, which reads as a designed budget rather than a trap.
- **The "uncommonly high volume of traffic" suspension clause** in the free docs concerns **outbound** traffic a service *initiates* — not inbound pings. Does not apply.
- **No documented bans for it.** The most-cited public suspension case (`SunsetMkt/Stop-Using-Render.com`) was an AUP block over two Bing-proxy projects — unrelated to pinging or free-tier usage patterns.
- **Verdict: low-risk and unsupported, not prohibited.** Recorded here as a deliberate decision rather than done quietly. The windowed (not 24/7) shape also keeps us clear of the "avoid payment" reading, since it demonstrably does not replicate an always-on paid instance. **Escape hatch if Render ever tightens: Starter $7/mo**, inside the §10 ceiling.

**To verify once applied:** whether the checkpointer's idle pool connections alone keep Neon from suspending. If they do, Neon stays awake whenever Render is awake and the CU-hour math bites regardless of endpoint. Watch Neon compute-hours for ~24 h after enabling.

Sources (policy check): [Render — Deploy for Free](https://render.com/docs/free) · [Render — Acceptable Use Policy](https://render.com/acceptable-use) · [Render — Terms of Service](https://render.com/terms) · [Stop-Using-Render.com suspension writeup](https://github.com/SunsetMkt/Stop-Using-Render.com)

---

## 2. Containerization & build

**Question:** How is the app packaged and built for that platform?

**Research / web searches:**
- `uv Docker production image FastAPI multi-stage build 2026`
- `uv sync --frozen --no-dev Dockerfile best practice`
- `distroless vs slim python image size security 2026`
- `platform X build from Dockerfile vs nixpacks vs buildpacks`

**Compare on:** image size, build time on the host's free builder, does the platform build
the Dockerfile or need its own buildpack, reproducibility (`uv.lock`).

**Findings:**

**Recommended Dockerfile pattern (2026 uv + multi-stage):**

The canonical uv + FastAPI multi-stage Dockerfile (from `astral-sh/uv-docker-example` and
the uv docs) works as follows:

```dockerfile
# --- builder stage ---
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project   # cache deps layer
COPY . .
RUN uv sync --frozen --no-dev                         # install project itself

# --- runtime stage ---
FROM python:3.12-slim
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
RUN adduser --disabled-password worker && chown -R worker /app
USER worker
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Key points:
- **`uv sync --frozen --no-dev`** uses `uv.lock` for reproducible installs (~10–100× faster than pip).
- **Two-layer cache**: copying `pyproject.toml` + `uv.lock` before source files means dep layer is only rebuilt when dependencies change.
- **Non-root user** (`worker`) is non-negotiable in 2026 for most platforms' security policies.
- **BuildKit cache mounts** (`--mount=type=cache,target=/root/.cache/uv`) can speed up local builds further but are optional for hosted CI.

**Image size options:**

| Base image | Approx. uncompressed size | Security (CVE count) | Debuggability | Verdict for this project |
|---|---|---|---|---|
| `python:3.12` (full) | ~1 GB | High CVE count | Easy | Too large; avoid |
| `python:3.12-slim` | ~149 MB | Medium (~107 CVEs) | Has shell/package manager | **Good default for MVP** |
| `gcr.io/distroless/python3-debian12` | ~66 MB | Low (~53 CVEs; 32 packages) | No shell — hard to debug | Good for security-conscious prod; harder to troubleshoot |
| Alpine (`python:3.12-alpine`) | ~50 MB | Very low | musl-libc can break C-ext deps | Avoid unless all deps are pure Python |

Recommendation for InternHunterAgent MVP: **`python:3.12-slim` runtime** (simple, debuggable, reasonable size). Migrate to distroless if the project later needs security hardening.

**Platform build compatibility:**

| Platform | Dockerfile support | Nixpacks / buildpack fallback | Notes |
|---|---|---|---|
| Render | Yes — detects `Dockerfile` automatically | Nixpacks as fallback (auto-detects Python) | Dockerfile preferred for uv |
| Google Cloud Run | Yes — `gcloud run deploy --source .` uses Cloud Build | Google Buildpacks as fallback | `gcloud` CLI handles the build + push |
| HuggingFace Spaces | Yes — `Dockerfile` in repo root | None | Port must be 7860 |
| Railway | Yes | Nixpacks default | Dockerfile takes priority if present |
| Fly.io | Yes | None | `fly.toml` controls; `Dockerfile` auto-detected |

Sources:
- [uv Docker integration docs (astral.sh)](https://docs.astral.sh/uv/guides/integration/docker/)
- [uv FastAPI integration docs (astral.sh)](https://docs.astral.sh/uv/guides/integration/fastapi/)
- [Multi-stage uv Dockerfile deep dive (medium.com/@benitomartin)](https://medium.com/@benitomartin/deep-dive-into-uv-dockerfiles-by-astral-image-size-performance-best-practices-5790974b9579)
- [Distroless Python with uv 2026 (nerdleveltech.com)](https://nerdleveltech.com/distroless-python-containers-with-uv-tutorial)
- [Docker image size comparison (chainguard.dev)](https://www.chainguard.dev/supply-chain-security-101/best-python-docker-image-top-options-compared)

**Decision (2026-07-16):** **`python:3.12-slim` Dockerfile at `docker/Dockerfile`**, built with `uv sync --frozen --no-dev`, non-root `app` user. The `CMD` binds a fixed `--port 8000`; Render routes to it via a **`PORT=8000` env var** (tells Render's proxy which port the container listens on). Distroless deferred. Render built + pushed the image in ~1 min on its own builder.

---

## 3. Managed Postgres in production

**Question:** Where does prod Postgres live (free, no surprise pause)?

**Research / web searches:**
- `Neon vs Supabase free Postgres 2026 idle pause storage limits` *(partly done — Neon
  0.5 GB, no weekly pause; Supabase pauses after 1 week)*
- `free Postgres tier connection limits pgbouncer serverless`
- `Neon scale to zero cold start latency Postgres`
- `does platform X bundle a free Postgres add-on 2026`

**Compare on:** storage cap (our data is tiny, <50 MB), connection pooling (serverless
Postgres + FastAPI = pooling matters), idle/pause policy, backups, region.

**Findings:**

| Provider | Free storage | Idle / pause policy | Connection pooling | Region | Notes |
|---|---|---|---|---|---|
| **Neon** | 3 GiB per branch / project (updated 2026; was 0.5 GB) · 100 CU-hours compute/month | Suspends after **5 min** idle; resumes in **~300–500 ms** (median cold start; 95th pct ~2.6 s; team targeting sub-1 s by end 2026) | Built-in PgBouncer via `-pooler` hostname suffix (up to 10,000 client connections in transaction mode) | AWS us-east-1, eu-central-1, ap-southeast-1 (Singapore) | **No weekly pause.** 100 projects per account. |
| **Supabase** | 500 MB · 2 projects max | **Pauses entire project after 1 week of inactivity** (policy tightened Feb 2026); requires manual unpause from dashboard — not safe for a daily cron setup | PgBouncer included; pooled connection string required for serverless | AWS us-east-1 + several others | Also bundles auth/storage/realtime — overkill for this project |
| **Render Postgres (free)** | 1 GB | **Expires after 30 days** then 14-day grace, then deleted | None bundled | Oregon (US-West) | Temporary by design; **not viable for a permanent free DB** |
| **Railway Postgres** | Counted against $5/month credit allowance; pauses when credits run out | Pauses end of month when credits exhausted | Not bundled | US-West | Not reliably free; tied to paid plan |

**Key numbers for InternHunterAgent:**
- Our dataset is <50 MB (112 AI/Data jobs per run × daily = still well under 50 MB even after months of data). Neon's 3 GiB free cap is approximately **60×** our expected data size — no storage risk.
- FastAPI + LangGraph checkpointer will hold persistent connections. Use Neon's `-pooler` hostname in the DSN for all application connections (transaction mode pooling). Keep a direct (non-pooled) connection only for migrations.
- Neon's 5-minute suspend is compatible with a daily cron (cron wakes the DB, runs its queries, DB suspends again). Cold start of ~500 ms is acceptable.
- Neon cold-start note: if both the API (Render, scale-to-zero) and the DB (Neon, suspend) are cold simultaneously, the first request after extended idle could see a 1–2 min compound delay (API spin-up + DB wake). This is acceptable for a portfolio demo but worth documenting.
- Supabase's weekly-pause behavior would cause the daily ingestion cron to fail silently after 7 idle days — a silent data loss risk. Eliminated from consideration.

**Local vs. deploy DSN strategy:**
- Local dev: `DATABASE_URL` in `.env` → local Postgres (Docker Compose or `brew services`)
- CI/testing: Neon branch (Neon supports per-branch DBs for free) or in-memory SQLite shim if tests allow
- Production: Neon pooler DSN injected as `DATABASE_URL` env var on the hosting platform

Sources:
- [Neon vs Supabase 2026 (getautonoma.com)](https://getautonoma.com/blog/supabase-vs-neon)
- [Neon vs Supabase free tier deep dive (agentdeals.dev)](https://agentdeals.dev/neon-vs-supabase)
- [Neon connection pooling docs (neon.com)](https://neon.com/docs/connect/connection-pooling)
- [Neon cold-start latency benchmarks (neon.com)](https://neon.com/docs/guides/benchmarking-latency)
- [Render Postgres free tier (kuberns.com)](https://kuberns.com/blogs/render-postgres-pricing-setup-limits/)

**Decision (local vs deploy DSN strategy, 2026-07-16):** `DATABASE_URL` in SQLAlchemy `postgresql+psycopg://…` form everywhere; the checkpointer strips `+psycopg` itself (`src/core/checkpointer.py`). Local = Docker Postgres on `:5433`. Prod = **Neon direct (non-pooled) endpoint** (PG17, Singapore) — for a single low-QPS instance the pooler's PgBouncer prepared-statement subtlety isn't worth it, and direct sits well within Neon's connection cap. Snapshot loaded via the direct **plain** `postgresql://…` DSN (no `+psycopg`, which is a SQLAlchemy-only prefix). Neon Auth left OFF (no end-user auth in this app).

---

## 4. Scheduling the ingestion job in production

**Question:** What runs the daily ingestion cron in prod, free?

**Research / web searches:**
- `GitHub Actions scheduled workflow private repo cost 2026` *(partly done — ~$0.002/min;
  free for public repos; UTC-only; auto-disables after 60 days idle)*
- `Render cron job free tier 2026`
- `cloud scheduler free tier cron serverless 2026`
- `run scheduled Python job free no server`

**Compare on:** cost at daily cadence, secret handling, max runtime, observability of a
failed run, whether it can reach the DB + source sites.

**Findings:**

| Option | Cost at daily cadence | Secret handling | Max runtime | Observability | Internet access to job-boards | Verdict |
|---|---|---|---|---|---|---|
| **GitHub Actions (public repo)** | **$0** — unlimited free minutes for public repos | GitHub encrypted secrets; referenced as `${{ secrets.NAME }}` | 6 hours per job | Full logs in Actions UI; email/Slack notification on failure | Yes — outbound internet from GitHub-hosted runners | **Best option** |
| **GitHub Actions (private repo)** | 2,000 Linux min/month free → **~$0 for daily 10-min cron** (300 min/month used, well within quota). Overage: $0.006/min (reduced from $0.008 in Jan 2026) | Same as above | 6 hours per job | Same as above | Yes | **Still free** for this workload size |
| **Render Cron Job** | **Minimum $1/month** (billing is per second of execution, with a floor). Not in free tier. | Render env vars (set in dashboard) | Limited by instance timeout | Render dashboard logs | Yes | **Not free** — skip |
| **GCP Cloud Scheduler** | 3 free jobs/month on always-free tier; can trigger Cloud Run job or Cloud Function | GCP Secret Manager | Limited by triggered service | Cloud Logging | Yes | Viable only if already on Cloud Run; adds GCP IAM complexity |
| **Self-hosted cron (e.g., on a VPS)** | Depends on VPS; cheapest ~$4/month (Oracle Cloud free tier ARM VMs exist but are capacity-constrained) | Manual env-file management | Unlimited | systemd journal | Yes | Overkill for this project |

**GitHub Actions specifics for this project:**
- **Schedule syntax:** `cron: '0 2 * * *'` = 02:00 UTC daily (09:00 Vietnam time / ICT = UTC+7). UTC-only — no timezone support.
- **60-day auto-disable:** GitHub automatically disables scheduled workflows if the repo has no commits/PRs/issues for 60 consecutive days. Prevention: add a `keepalive-workflow` action (uses GitHub API to touch the repo every 45 days) or ensure regular development activity. See [marketplace action](https://github.com/marketplace/actions/keepalive-workflow).
- **Network:** GitHub-hosted runners have full outbound internet access (→ VietnamWorks API, ITviec via cloudscraper all reachable). The scraping IP will be a GitHub Actions IP, **not** the API server's IP — a useful separation.
- **Secrets available in cron:** `DATABASE_URL` (Neon DSN), `GROQ_API_KEY` (if LLM is used in ingestion, else not needed), stored in GitHub repo or environment secrets.
- **Estimated runtime:** current scrape_spike.py runs in under 30 seconds. Even with full multi-source ingestion, a daily job should complete in <10 minutes. 2,000 min/month budget is ~200× the expected use.

Sources:
- [GitHub Actions billing docs (docs.github.com)](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [GitHub Actions 2026 pricing changes (resources.github.com)](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/)
- [GitHub Actions 60-day auto-disable (github.com/orgs/community)](https://github.com/orgs/community/discussions/57858)
- [Keepalive Workflow action (github.com marketplace)](https://github.com/marketplace/actions/keepalive-workflow)
- [Render cron job pricing (render.com)](https://render.com/docs/cronjobs)

### 4.1 Ingestion-pipeline prerequisites for an *unattended* scheduled run (added 2026-07-03)

The findings above answer *where* the cron runs. They do **not** answer whether the
pipeline is safe to run *unattended*. The current pipeline (`src/services/ingestion/`)
was built for a **human-supervised, manual** CLI run (`research/data-ingestion-stage.md §8`
decision 4: "batch, re-runnable script; no scheduler in MVP"). Admitting a scheduler
changes the **failure-cost calculus** — nobody is watching the run — and that forces
pipeline changes that are *architectural, not tactical*. These are the gaps found by
reading the current `sources/vietnamworks.py`, `loader.py`, `clean_store.py`, and
`raw_store.py` against `docs/Code_Review_Notes.md` → DN-1:

| # | Current behavior | Safe manually, unsafe unattended because… | Required change | Tracked |
|---|---|---|---|---|
| 1 | `_post`'s `raise_for_status()` aborts the whole run on one transient 429/5xx; `loader.run_ingestion` consumes the source via `list(source.fetch())`, so **nothing** persists | a human sees the error and re-runs; a silent cron just loses that day's run | per-page `try/continue` + light retry/backoff | §4.2 #5 (deferred → T0012) |
| 2 | `replace_clean_jobs` does `TRUNCATE clean_jobs` then rebuilds from the **in-memory fetch batch** | once #1 lands, a *partial* run now **succeeds** and silently **shrinks** the served table to whatever came through — a human notices a 50→8 drop, a cron does not | **superseded by §4.2:** drop `TRUNCATE` → accumulate-upsert with time-based `is_active` soft-expiry, so a partial run cannot shrink the table | §4.2 #1–#2 / DN-1 |
| 3 | `content_hash` is written to `raw_jobs` but **never read**; every run re-transforms the whole batch | wasteful-but-harmless when a human runs it occasionally; pure repeated waste at daily cadence | use `content_hash` as a delta to skip unchanged rows | DN-1 move 4 |
| 4 | `raw_jobs` upsert and `clean_jobs` rebuild are **separate transactions** | a crash between them desyncs the two tables; a human re-runs, a cron leaves them desynced until the next day | folds into #2 (rebuild clean from raw atomically) | DN-1 move 1/5 |
| 5 | robots.txt / ToS for `ms.vietnamworks.com` is **unverified** (§11, `data-ingestion-stage.md §0.1`) | a one-off manual fetch is low-exposure; a daily unattended job against a host whose ToS forbids automated access is a *standing, repeated* violation | resolve the §11 robots/ToS gate **before** the first scheduled run | §11 |

**What is already safe (no change needed).** Idempotency is sound: upsert on
`(source, external_id)` means a re-run refreshes rather than duplicates; and the
empty-fetch guard (`replace_clean_jobs([])` returns 0 and *skips* `TRUNCATE`) already
prevents a *fully-failed* run from wiping the table. The dangerous case is the
**partial** success (#2) — total failure is already handled.

**Reconciliation with the permanent exclusion (drives the `Full_Design_Document.md`
edit in the design pass).** Full_Design §2 permanently excludes *"autonomous or
background execution — no cron jobs, queues, or schedulers."* That law targets
**in-request** background execution *inside the serving path* (a queue/scheduler that
makes a request do work out-of-band). An **external** scheduler (GitHub Actions)
invoking the **offline** ingestion CLI — which the serving path is forbidden from ever
importing (Full_Design §3 ingestion-layer law) — puts *no* scheduler in the request
pipeline. §3 already anticipates exactly this: *"turning ingestion into a scheduled job
is a separate decision that must be reconciled against that exclusion, not assumed."*
The (b) design pass should amend §2 to scope the exclusion explicitly to *in-request*
background execution and permit an out-of-band scheduled ingestion trigger,
cross-referencing §3 — **not** delete the exclusion.

**Sequencing conclusion (superseded — see §4.2).** The original worry — that resilience
must not ship before a "clean-from-raw" rebuild, or a partial run shrinks the table — is
**dissolved** by the §4.2 decision to *accumulate* (drop `TRUNCATE`) with **time-based**
`is_active` expiry: with nothing wiped and expiry measured in days, a partial or failed
run is inherently harmless, so resilience becomes *completeness*, not *correctness*. The
whole Ingestion Deploy stage is now sequenced **after** the Model Evaluation milestone
(`docs/Tickets.md` T0011 → T0012). A healthchecks.io dead-man's switch (§9) plus the
sharp-drop yield assertions in `job-site-comparison.md` remain the unattended-run safety
net that alerts on a missed or suspiciously-small run.

**Decision (2026-07-03):** **External scheduler admitted.** The daily ingestion cron
runs on **GitHub Actions** (public repo → free/unlimited minutes; secrets via Actions
secrets; UTC cron `0 2 * * *` = 09:00 ICT; add a keepalive action to defeat the 60-day
auto-disable), invoking the offline ingestion CLI. Reconciled against Full_Design §2 as
*external / out-of-band*, not *in-request* (see above). **Gated on** the pipeline-readiness
changes #1–#4 landing first (the §4.2 accumulate/lifecycle decisions; sequenced after the T0011 Evaluation milestone) **and** the §11 robots.txt/ToS
verification. Runs live behind a dead-man's switch + yield assertions (§9).

### 4.2 Ingestion-pipeline redesign decisions (recorded 2026-07-03; pending the Model Evaluation milestone)

These decisions were reached in design discussion on 2026-07-03 but are **deliberately not
yet ticketed**: the Ingestion Deploy Readiness milestone is **sequenced after the Model
Evaluation milestone** (`docs/Tickets.md` T0011 → T0012), because the pipeline's honesty
guarantee (the agent staying truthful about stale postings) rests on model behavior that
must be *measured* first. Recorded here so the reasoning survives the ticket removal.

1. **Load semantics — accumulate, never wipe.** Drop the `TRUNCATE` in
   `clean_store.replace_clean_jobs`; use the already-written
   `ON CONFLICT (source, external_id) DO UPDATE` so `clean_jobs` accumulates and each
   posting refreshes in place. (That upsert is currently *dead code* behind the TRUNCATE.)
   This retires §4.1's row-2 shrink hazard at the root — nothing is wiped, so a partial
   run cannot shrink the table.
2. **Staleness — `is_active` soft-expiry, time-based (invariant).** Add `is_active` (bool),
   `first_seen_at`, `last_seen_at`. A posting is expired (`is_active = false`, **never
   deleted**) when `last_seen_at < now() - expire_after_days` (config) — **time-based,
   never "not seen this run."** Time-based is the invariant that makes a partial/failed
   scrape harmless: a missed posting simply isn't refreshed; only `expire_after_days`
   *consecutive* misses expire it. `is_active` is the **only** new agent-visible column;
   `first_seen_at`/`last_seen_at` stay internal bookkeeping (exposing a `last_seen_at`
   "freshness" proxy would repeat the `posted_date` fabrication trap — `Known_Issues.md`).
3. **`is_active` in agent queries — include-all default + always-on honesty (nudge, not a
   view).** The agent queries **all** postings by default (no `WHERE is_active = true`),
   which is correct for aggregates/counts ("how many AI-Engineer jobs need Python") that
   want the whole corpus; it filters to active only when the user signals it ("still open",
   "can I apply"). **Independently**, whenever a *list* result contains `is_active = false`
   rows, the agent hedges ("N of these may no longer be open") — honesty is always-on,
   keyed on the returned column, not gated on the user asking. Aggregate/scalar answers
   have no per-row status to hedge, and including expired postings in a count is the desired
   market view. This **rules out** a hide-inactive DB view (which would erase the corpus for
   analytics and leave nothing to be honest about). Enforcement is a **prompt nudge** —
   best-effort, like the existing role/salary/`id`-first nudges — **which is exactly why the
   Evaluation milestone (T0011) must confirm the model honors it before this ships.**
4. **Migrations — adopt Alembic.** The T0009.9 "`reset_db.sql` is enough because both tables
   are reproducible" rationale **breaks on deploy**: a scheduled, accumulating `raw_jobs`
   keeps postings that have since dropped out of search and are **no longer re-fetchable**,
   so the data becomes irreplaceable — the exact "deployed data becomes irreplaceable"
   trigger the docs pre-committed to. Adopt Alembic: baseline-migrate the current schema,
   then migrate the lifecycle columns. `reset_db.sql` is retained for local dev only.
5. **Resilience — per-page `try/continue` + light retry/backoff.** In
   `VietnamWorksSource._collect`, guard each `_post` per page; retry with backoff, then
   skip-and-log. With time-based expiry (#2) this is now *completeness* (salvage the good
   pages), not *correctness* (a failed run is already harmless). Per-**source** isolation
   (an orchestrator/registry) stays deferred — that is multi-source, which is future.
6. **Scheduler & scope — external GitHub Actions, ingestion-only.** Per §4.1's decision.
   This milestone is **ingestion-only**; the web-API deploy (§1/§2/§7) is a separate later
   milestone. The `Full_Design_Document.md` §2/§3 external-scheduler reconciliation lands
   with this milestone (see §4.1).
7. **Deferred within the redesign (explicitly out of scope, MVP discipline):**
   rebuild-clean-**from-`raw_jobs`** phase split — *not* required by `is_active`
   (accumulate-upsert from the fetch batch already gives lifecycle); the source
   **orchestrator/registry** (multi-source); the `content_hash` **delta** (nightly
   re-transform of ~50–100 rows is cheap); and folding the `raw_jobs` + `clean_jobs` writes
   into **one transaction** (an idempotent nightly re-run heals a rare desync for the MVP).

---

## 5. Secrets & configuration management

**Question:** How are Groq key, Langfuse keys, and the DB DSN injected safely?

**Research / web searches:**
- `platform X environment variables secrets management free tier`
- `GitHub Actions secrets vs environments for scheduled jobs`
- `pydantic-settings env var production 12-factor config`
- `keep API keys out of Docker image best practice 2026`

**Compare on:** env-var injection, secret rotation, no secrets in the image/repo, parity
between the API host and the cron host, mapping to existing `config/settings.yaml` +
`pydantic-settings`.

**Findings:**

**The 12-factor pattern (applicable to both Render web service and GitHub Actions cron):**

All secrets are injected as environment variables at runtime — never baked into the Docker
image, never committed to the repo. `pydantic-settings` reads env vars with higher priority
than `.env` files, so the same `Settings` class works in all environments.

**Secrets inventory for InternHunterAgent:**

| Secret | Where it lives in prod | Where it lives in cron | Local dev |
|---|---|---|---|
| `DATABASE_URL` (Neon pooler DSN) | Render env var (dashboard) | GitHub Actions secret | `.env` (git-ignored) |
| `GROQ_API_KEY` | Render env var | GitHub Actions secret (only if LLM used in ingestion) | `.env` |
| `LANGFUSE_PUBLIC_KEY` | Render env var | GitHub Actions secret (if tracing ingestion) | `.env` |
| `LANGFUSE_SECRET_KEY` | Render env var | GitHub Actions secret | `.env` |
| `LANGFUSE_HOST` | Render env var (or non-secret config) | GitHub Actions env or secret | `.env` / `config/settings.yaml` |

**Injection pattern per workload:**
- **API (Render):** set env vars in the Render dashboard service settings. They are injected into the container at startup. Never pass via `CMD` or Dockerfile `ENV`.
- **Cron (GitHub Actions):** store secrets under `Settings → Secrets and variables → Actions` in the GitHub repo. Reference as `env: GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}` in the workflow YAML.
- **Local dev:** `.env` file in project root (added to `.gitignore`). `pydantic-settings` auto-loads it via `model_config = SettingsConfigDict(env_file=".env")`.

**Mapping to `config/settings.yaml` + `pydantic-settings`:**
- `config/settings.yaml` holds **non-secret** config (scraper URLs, pagination caps, tech keyword dict, rate-limit delays, model names). These are safe to commit.
- `pydantic-settings` `BaseSettings` subclass reads env vars at startup; env vars **override** `.env` file values which **override** any defaults. Secrets never touch `settings.yaml`.
- Fail-fast at startup: mark secret fields as required (no default). If `DATABASE_URL` is missing, the app crashes immediately with a clear error rather than failing silently on first DB call.

**Secret rotation:** Render and GitHub Actions both support updating env vars / secrets without redeploying (Render redeploys on env-var change by default; GitHub Actions reads secrets fresh each run). No secret rotation tooling needed for an MVP demo.

Sources:
- [FastAPI + pydantic-settings twelve-factor guide (medium.com)](https://medium.com/@hadiyolworld007/fastapi-pydantic-settings-twelve-factor-secrets-and-config-without-footguns-7990e2f20919)
- [pydantic-settings docs (pydantic.dev)](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)
- [GitHub Actions secrets docs (docs.github.com)](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions)

**Decision (2026-07-16):** All secrets injected as **Render dashboard env vars** at runtime — never in the image (`.dockerignore` excludes `.env`) or the repo. Five required, read by `src/core/config.py`: `GROQ_API_KEY`, `DATABASE_URL`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` — **note the code reads `LANGFUSE_BASE_URL`, not `LANGFUSE_HOST`** (§6's earlier draft was wrong). `GOOGLE_API_KEY` omitted (eval-judge only, never on the request path). Plus the non-secret `PORT=8000`. Enter raw values in Render (no surrounding quotes — unlike a `.env` file, Render does not strip them).

---

## 6. Langfuse hosting (tracing in prod)

**Question:** Langfuse Cloud free tier vs self-host — which for prod tracing?

**Research / web searches:**
- `Langfuse Cloud free tier limits 2026 events ingestion`
- `self-host Langfuse docker resource requirements`
- `Langfuse cloud vs self-hosted cost small project`

**Compare on:** free event/trace volume, data residency, whether self-hosting adds a 4th
workload (and its cost), ease vs the cloud free tier.

**Findings:**

**Langfuse Cloud — Hobby (free) tier:**

| Limit | Value |
|---|---|
| Monthly units (traces + observations + scores) | **50,000 units/month** |
| Data retention | 30 days |
| Users | 2 |
| Support | Community (GitHub, Discord) |
| Time-limited? | No — permanent free tier |
| Cost | $0 |

A "unit" = 1 trace + 1 per observation (LLM call, span, event) + 1 per score. A typical
single-user agent session (1 trace, ~3–5 LLM observations, 0–1 scores) = ~5–6 units.
At 50,000 units/month ÷ 6 units/session ≈ **8,333 sessions/month** before the cap is hit.
For a portfolio demo with one user, this is more than sufficient — months of heavy use
would not approach the limit.

**Self-hosted Langfuse v3 — resource requirements:**

| Component | Min spec (stable) | Recommended |
|---|---|---|
| All containers combined | 2 vCPU / 4 GB RAM | 4 vCPU / 8 GB RAM |
| v3 services | 6 containers: web UI, worker, PostgreSQL, **ClickHouse**, Redis, MinIO | — |
| Idle RAM (homelab measurement) | ~1.5 GB (ClickHouse dominates) | — |
| VPS cost estimate | ~$6–12/month (2 vCPU / 4 GB; e.g., Hetzner CX22) | Adds a **4th paid workload** |

**Verdict:**

| Option | Monthly cost | Complexity | Data residency | Trace volume |
|---|---|---|---|---|
| **Langfuse Cloud Hobby** | **$0** | Zero — just set 3 env vars | Langfuse EU/US servers | 50K units/month — ample for demo |
| Self-host (v3 Docker Compose) | ~$6–12/month VPS | High — 6 containers, ClickHouse maintenance | Your own server | Unlimited |

For a single-user portfolio demo, **Langfuse Cloud Hobby** eliminates an entire infrastructure concern for free and the 30-day retention window is adequate. Self-hosting only makes sense if data residency is a requirement or if trace volume exceeds 50K units/month.

Sources:
- [Langfuse pricing (langfuse.com)](https://langfuse.com/pricing)
- [Langfuse pricing teardown 2026 (dev.to)](https://dev.to/beton/langfuse-pricing-teardown-2026-2pi9)
- [Langfuse self-hosting containers docs (langfuse.com)](https://langfuse.com/self-hosting/deployment/infrastructure/containers)
- [Langfuse v3 self-hosting discussion (github.com/orgs/langfuse)](https://github.com/orgs/langfuse/discussions/5669)
- [Langfuse pricing breakdown (cekura.ai)](https://www.cekura.ai/blogs/langfuse-pricing)

**Decision (2026-07-16):** **Langfuse Cloud Hobby, JP region** (`LANGFUSE_BASE_URL=https://jp.cloud.langfuse.com`). Zero infra, 50k units/month — ample for a demo. Self-host ruled out (adds a paid 4th workload with ClickHouse). Verified live: `trace_url` resolves from the streamed `metadata` event to the JP project.

---

## 7. Domain, HTTPS & networking

**Question:** Public URL, TLS, and CORS for the API.

**Research / web searches:**
- `platform X custom domain free HTTPS automatic TLS`
- `free subdomain for hobby project 2026`
- `FastAPI CORS production config`

**Compare on:** included HTTPS, custom-domain support on free tier, default `*.platform`
URL acceptability for a portfolio demo.

**Findings:**

**Default subdomains + automatic HTTPS by platform:**

| Platform | Default subdomain | Auto TLS (HTTPS) | Custom domain on free tier | Notes |
|---|---|---|---|---|
| **Render** | `<service-name>.onrender.com` | Yes — auto-provisioned + renewed | Included (workspace allowance; $0.25/domain beyond that) | Services keep both the `.onrender.com` URL and any custom domain |
| **Google Cloud Run** | `<service>-<hash>-<region>.run.app` | Yes — Google-managed certs | Yes — custom domain mapping free (cert auto-provisioned) | Stable URL if `--no-traffic` revision management used |
| **HuggingFace Spaces** | `<user>-<space>.hf.space` | Yes | Not supported on free tier | URL is stable as long as the Space exists |
| Koyeb (legacy free) | `<app>.koyeb.app` | Yes — auto TLS | 10 domains free | **Closed to new signups (Feb 2026)** |

**For a portfolio demo:** the default `*.onrender.com` or `*.run.app` subdomain is
entirely acceptable. A custom domain is a cosmetic upgrade, not a blocker.

**FastAPI CORS configuration for production:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.vercel.app"],  # specific origins, not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```
- Never use `allow_origins=["*"]` with `allow_credentials=True` (CORS spec forbids it).
- For a demo with no browser frontend, CORS may not be required at all.
- If the API is consumed via curl / Postman only, skip the middleware entirely.

**HTTPS note:** all candidate platforms (Render, Cloud Run, HuggingFace) provision and
renew TLS certificates automatically. No manual cert management needed.

Sources:
- [Render custom domains docs (render.com)](https://render.com/docs/custom-domains)
- [Koyeb domains docs (koyeb.com)](https://www.koyeb.com/docs/run-and-scale/domains)
- [FastAPI CORS middleware docs (fastapi.tiangolo.com)](https://fastapi.tiangolo.com/deployment/docker/)
- [Koyeb free tier + Mistral acquisition (srvrlss.io)](https://www.srvrlss.io/provider/koyeb/)

**Decision (2026-07-16):** Default **`internhunteragent.onrender.com`** subdomain + Render auto-TLS; no custom domain (cosmetic, deferred). **CORS stays unused** — the UI is served same-origin from the same FastAPI container, so `api.cors.allowed_origins` stays `[]` and the CORS middleware is never exercised. Recorded here as the deploy rationale for the empty origins list.

---

## 8. CI/CD (build, test, deploy)

**Question:** How does a push become a deploy?

**Research / web searches:**
- `GitHub Actions deploy to Render/Railway/Fly on push 2026`
- `platform X auto-deploy from GitHub free`
- `run pytest in CI before deploy gate`

**Compare on:** auto-deploy-on-push, ability to gate on `pytest`, preview environments,
rollback. Aligns with the repo's branch-per-ticket flow.

**Findings:**

**Platform native auto-deploy vs GitHub Actions deploy step:**

| Platform | Native auto-deploy from GitHub | Gate on pytest | Rollback | Free CI build time |
|---|---|---|---|---|
| **Render** | Yes — connect GitHub repo + branch; deploys on every push automatically | Not natively; add a GH Actions pytest step that must pass before merge (branch protection) | Manual via Render dashboard (redeploy previous deploy) | Render builds on their infra; GitHub Actions (free) runs tests |
| **Google Cloud Run** | Via GitHub Actions + `gcloud run deploy`; no native GH integration | Yes — add `pytest` step before the deploy step in the Actions workflow | `gcloud run services update-traffic --to-revisions=PREV=100` | Free for public repos |
| **Railway** | Yes — auto-deploys; can wait for GH Actions to pass before triggering | Yes (with branch protection) | One-click rollback in Railway dashboard | Requires paid plan |
| **Fly.io** | Via `flyctl deploy` in a GH Actions workflow | Yes | `fly releases rollback` | Requires paid plan |

**Recommended CI/CD pattern for this project (Render + GitHub Actions):**

```
main branch ← PRs from feature/* branches
  ↓
[GitHub Actions: PR check]
  └── pytest (unit tests)
  └── docker build --check (syntax only, no push)
  ↑ branch protection: require this to pass before merge

[After merge to main]
  └── Render native auto-deploy triggered automatically
      (Render builds the Dockerfile, deploys the container)
```

Or, for Cloud Run:
```
[After merge to main → GitHub Actions deploy workflow]
  └── pytest
  └── docker build + push to GCR / Artifact Registry
  └── gcloud run deploy
```

**Aligning with branch-per-ticket flow (from CLAUDE.md):**
The repo uses `feature/t####-<name>` branches that merge to `main`. Branch protection on
`main` requiring the `pytest` Actions job to pass enforces the gate. Render's
auto-deploy on push to `main` then triggers automatically — no separate deploy step needed.

**Preview environments:** Render supports preview environments on paid plans only. For free
tier: no preview environments. Test locally + on a dev branch before merging.

Sources:
- [Render GitHub auto-deploy (render.com)](https://render.com/articles/fastapi-production-deployment-best-practices)
- [Railway GitHub autodeploys docs (docs.railway.com)](https://docs.railway.com/deployments/github-autodeploys)
- [Fly.io continuous deployment with GitHub Actions (fly.io)](https://fly.io/docs/launch/continuous-deployment-with-github-actions/)
- [Railway vs Render 2026 (thesoftwarescout.com)](https://thesoftwarescout.com/railway-vs-render-2026-best-platform-for-deploying-apps/)

**Decision (2026-07-16):** **Render native auto-deploy on push** to `feature/t0018.4-deploy`. A `pytest` merge-gate on `main` is **deferred (out of T0018.4 scope)** — noted for a later CI ticket (`pre-deploy-refinement-plan.md §6i`). Rollback = redeploy a previous deploy from the Render dashboard. No preview environments (free tier).

---

## 9. Observability & health (beyond Langfuse)

**Question:** How do we know prod is up and the cron succeeded?

**Research / web searches:**
- `FastAPI health check endpoint readiness liveness`
- `free uptime monitoring cron dead-man-switch 2026` (e.g. healthchecks.io, UptimeRobot)
- `structured logging structlog production aggregation free`

**Compare on:** uptime ping, cron dead-man's-switch (alert if the daily run *didn't*
happen), log retention on the host, ties to the ingestion health checks already designed
in `job-site-comparison.md`.

**Findings:**

**A. FastAPI health check endpoint:**

Minimal pattern (does not rate-limit health probes):
```python
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "version": settings.app_version}
```
For readiness (checks DB reachability):
```python
@app.get("/ready", include_in_schema=False)
async def ready(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
```
Important: **never rate-limit `/health` or `/ready`** — throttling probe traffic causes
false-positive failures in platform health checks and load balancers.

**B. Uptime monitoring (is the API up?):**

| Tool | Free tier | Check interval | Cron dead-man support | Alert channels |
|---|---|---|---|---|
| **UptimeRobot** | 50 monitors | 5 minutes | Yes (heartbeat monitors) | Email, Slack, webhook |
| **healthchecks.io** | 20 checks; 3-month log history | Configurable window | **Yes — primary use case (dead man's switch)** | Email, Slack, webhook, PagerDuty |

Recommendation: use **UptimeRobot** (free, 50 monitors) to ping `GET /health` every 5 min
for API uptime. Use **healthchecks.io** (free, 20 checks) as the cron dead-man's switch.

**C. Cron dead-man's switch (did the daily job run?):**

Pattern:
1. Create a healthchecks.io check with `period=24h, grace=2h`.
2. At the end of the ingestion job (if all health-check assertions pass), `curl -fsS --retry 3 <check-url>`.
3. If the curl is not received within 26 hours (24 + 2 grace), healthchecks.io sends an email alert.

This maps directly to the health checks already designed in `job-site-comparison.md`:
> HTTP success rate, total + per-keyword yield, IT→AI/Data ratio, field-completeness %,
> delta vs. previous run.

Emit these as structured log lines in the cron script; ping healthchecks.io only if all
assertions pass. A sharp-drop assertion failure or a missing ping both produce an alert.

**D. Structured logging:**

Use **`structlog`** for JSON log output in the FastAPI app:
- `fastapi-structlog` package (released Jan 2026) provides structlog middleware + correlation IDs out of the box.
- In production, set `LOG_LEVEL=INFO` and configure structlog to output JSON (not colorized console).
- **Log aggregation:**
  - Render: streams stdout logs; accessible in dashboard for 7 days (free tier). No external aggregation needed for MVP.
  - Google Cloud Run: logs auto-shipped to Cloud Logging (50 GB/month free). Structured JSON logs appear as parsed fields in Cloud Logging — searchable, free for this scale.
- The cron job (GitHub Actions) logs are preserved in the Actions run history for 90 days (free tier) — no separate aggregation needed.

Sources:
- [FastAPI health check best practices (render.com)](https://render.com/articles/fastapi-production-deployment-best-practices)
- [healthchecks.io free tier (quietpulse.xyz)](https://quietpulse.xyz/blog/free-cron-monitoring-tools-for-developers)
- [UptimeRobot free plan (uptimerobot.com)](https://uptimerobot.com/)
- [fastapi-structlog package (pypi.org)](https://pypi.org/project/fastapi-structlog/)
- [Structured logging with structlog + FastAPI (ouassim.tech)](https://ouassim.tech/notes/setting-up-structured-logging-in-fastapi-with-structlog/)
- [Best cron monitoring tools 2026 (apistatuscheck.com)](https://apistatuscheck.com/blog/best-cron-job-monitoring-tools-2026)

**Decision (2026-07-16):** In-app **`GET /api/v1/health`** (liveness — Render health-check target) + **`GET /api/v1/ready`** (`SELECT 1`, DB-gated, returns 503 on failure, excluded from the `slowapi` limiter). Health check pointed at `/health` (not `/ready`) so Render probes don't keep Neon awake. External **UptimeRobot ping + healthchecks.io dead-man's-switch deferred** to the ingestion milestone (no cron ships here). structlog stdout + Render's 7-day log stream suffice for the demo.

---

## 10. Scaling, limits & cost ceiling

**Question:** What breaks first, and what would force a paid tier?

**Research / web searches:**
- `free tier egress bandwidth limits comparison 2026`
- `Groq API rate limits free tier 2026`
- `when does platform X start charging hobby project`

**Compare on:** the binding free-tier limit (RAM? egress? DB storage? Groq quota?), the
first paid step, and a hard "do-not-exceed" cost line.

**Findings:**

**Free-tier ceilings for each component (June 2026):**

| Component | Free limit | Expected monthly use | Headroom | First paid step if exceeded |
|---|---|---|---|---|
| **Render web service** | 750 instance-hours/month; 512 MB RAM; 100 GB egress | Demo: ~100–300 hrs (spins down idle). RAM: FastAPI + LangChain ~150–300 MB peak | ~2.5–7.5× hours; 2 GB expected egress | $7/month Starter (0.5 vCPU / 512 MB, always-on) |
| **Neon Postgres** | 3 GiB storage; 100 CU-hours compute | <50 MB data; compute: seconds/day (tiny queries + daily cron) | ~60× storage; >99× compute | $19/month Launch plan (10 GiB, 300 CU-h/month) |
| **GitHub Actions (public repo)** | Unlimited minutes | Daily 10-min cron + occasional CI = ~500 min/month | Unlimited | $0 — always free for public repos |
| **GitHub Actions (private repo)** | 2,000 Linux min/month | ~500 min/month | ~4× | $4/month (additional 1,000 min bundles) |
| **Groq API (free tier)** | 30 RPM / 6,000 TPM / **1,000 RPD** (requests per day) | Demo: 10–50 agent sessions/day × 2–4 LLM calls each = 20–200 calls/day | 5–50× (depending on session frequency) | Pay-as-you-go: Llama 3.1 8B = $0.05/M tokens; Llama 3.3 70B = $0.59/M input tokens |
| **Langfuse Cloud Hobby** | 50,000 units/month | ~6 units/session × 50 sessions/day × 30 days = 9,000 units | ~5.5× | $29/month Core plan (100K units) |

**Binding limit analysis:**
- At **very low traffic** (1–5 sessions/day): all components stay well within free tiers. Total cost = $0.
- At **moderate traffic** (~50–100 sessions/day): Groq's 1,000 RPD is the first limit hit if sessions use multiple LLM calls. Mitigation: switch to a cheaper/higher-quota model, or add response caching.
- At **high traffic** (~200+ sessions/day): Render instance hours and Groq RPD both become binding.

**Do-not-exceed cost line:** this is a portfolio/demo project. Suggested hard ceiling: **$10/month**. The first paid upgrade most likely to be needed is either Render paid tier ($7/month, eliminates cold starts) or Groq pay-as-you-go (charged per token, very low at demo scale).

**Egress summary:**
- Render: 100 GB/month free. A FastAPI JSON response is ~1–10 KB. 100 GB ÷ 10 KB = 10M responses before paying egress. This will never be the binding limit.
- Google Cloud Run: 1 GB/month free egress to internet; then $0.08–$0.12/GB. For a demo, still not the binding limit.

Sources:
- [Render pricing 2026 (saaspricepulse.com)](https://www.saaspricepulse.com/tools/render)
- [Neon pricing 2026 (vela.simplyblock.io)](https://vela.simplyblock.io/articles/neon-serverless-postgres-pricing-2026/)
- [Groq free tier limits 2026 (grizzlypeaksoftware.com)](https://www.grizzlypeaksoftware.com/articles/p/groq-api-free-tier-limits-in-2026-what-you-actually-get-uwysd6mb)
- [Groq rate limits docs (console.groq.com)](https://console.groq.com/docs/rate-limits)
- [Langfuse pricing (langfuse.com)](https://langfuse.com/pricing)
- [Egress bandwidth comparison 2026 (gpuperhour.com)](https://gpuperhour.com/reference/data-egress)

**Decision (cost ceiling, 2026-07-16):** **$10/month hard ceiling; actual expected $0.** Render Free + Neon Free (PG17) + Langfuse Hobby + Groq free tier all sit within limits at demo QPS. First likely paid step if ever needed: Render Starter ($7/mo, kills the 15-min cold start) or Groq pay-as-you-go (per-token, tiny at demo scale).

---

## 11. Security & compliance (lightweight)

**Question:** Minimum responsible posture for a public demo.

**Research / web searches:**
- `FastAPI production security checklist 2026`
- `rate limiting FastAPI free` (abuse protection on a public endpoint)
- `scraping ToS robots.txt legal hosting Vietnam` (ingestion runs from prod IP)

**Compare on:** public-endpoint abuse protection, secrets hygiene (§5), and the
scraping-from-prod-IP ToS/robots question raised in `job-site-comparison.md`.

**Findings:**

> **2026-07-13 T0016 decision delta:** The generic security checklist below has been narrowed for the current API-only, no-auth, read-only portfolio demo. T0016 keeps Swagger/ReDoc/OpenAPI public by default via `api.docs_enabled: true`, with `api.docs_enabled: false` as the locked-down switch for `/docs`, `/redoc`, and `/openapi.json`. CORS and in-process rate limiting are implemented; frame-protection headers remain deferred until FastAPI serves same-origin HTML.

**A. FastAPI production security checklist (minimum for a public demo):**

| Control | Implementation | Cost |
|---|---|---|
| HTTPS enforced | Platform auto-TLS (Render / Cloud Run) — no action needed | $0 |
| Secrets out of image/repo | env vars only (§5) | $0 |
| Rate limiting per IP | `slowapi` library (in-process, Redis optional) | $0 |
| CORS restricted | `CORSMiddleware` with specific origins (§7) | $0 |
| Input validation | Pydantic models on all request bodies (already enforced by FastAPI) | $0 |
| `/docs` exposure is deliberate | T0016 keeps `/docs`, `/redoc`, and `/openapi.json` public for the portfolio demo by default; set `api.docs_enabled: false` to hide all three | $0 |
| UI-specific security headers | Add frame-protection headers only if FastAPI later serves same-origin HTML | $0 |
| Health endpoints not rate-limited | Exclude `/api/v1/health` from `slowapi` limiter | $0 |

**B. Rate limiting for the public API endpoint:**

`slowapi` is the standard free in-process rate limiter for FastAPI (wraps the `limits` library):
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/agent/chat")
@limiter.limit("10/minute")
async def query_agent(request: Request, ...):
    ...
```
- Per-IP, per-endpoint limits. No Redis required for a single-instance deploy.
- Recommended limit for a demo: 10 req/min per IP (well above any legitimate single-user use; blocks simple abuse scripts).
- Redis backend needed only for multi-instance rate limiting — not relevant at this scale.

**C. Scraping from prod IP — ToS / robots.txt:**

The ingestion cron runs on **GitHub Actions**, not on the API server. This means:
- The scraping IP is a **GitHub-hosted runner IP** (one of GitHub's outbound IP ranges), not the Render/Cloud Run API server IP.
- The two concerns (API hosting and scraping) are naturally separated at the IP level.

Robots.txt status per source (from `data-ingestion-stage.md`):
- **TopCV:** `robots.txt` permits scraping of listing/detail paths (confirmed by VietJobs academic dataset). ✅
- **VietnamWorks:** the API endpoint used (`ms.vietnamworks.com`) is undocumented and **serves no robots.txt at all** (HTTP 404); `www.vietnamworks.com/robots.txt` permits the paths in question and sets no `Crawl-delay`; the ToS carries no automated-access clause. ✅ **Checked 2026-07-16 (T0019.1)** — see the *Decision — VietnamWorks robots.txt / ToS* record at the end of this section for the evidence, the recommended verdict, and the one caveat that survives it.
- **ITviec:** `robots.txt` allows everything except `/subscriptions/new`; our paths (`/segments/viec-lam-ai-data`, `/it-jobs/*`) are permitted. ✅

General 2026 legal posture for scraping public job postings:
- Scraping public, non-personal, factual job-posting data is **generally defensible** in most jurisdictions. The main legal risks concentrate at: personal data, auth bypass, copyrighted content reproduction at scale, server overload, and explicit ToS breach.
- ToS violations are typically **civil** (breach of contract), not criminal, for publicly accessible data (the CFAA does not criminalize ToS breach for public sites in the US after *hiQ v. LinkedIn*).
- Vietnam has no specific web scraping law. PDPD (Personal Data Protection Decree, 2023) applies to personal data — job postings (company name, role, description) are not personal data.
- ~~**Action required before production:** fetch and read `robots.txt` for VietnamWorks API host; review VietnamWorks ToS.~~ **Done 2026-07-16 (T0019.1)** — see the Decision record below. Keep scraping volume low and polite (already designed: 0.6 s delay, daily cadence — no `Crawl-delay` directive exists to honor, so this stands unchanged).

Sources:
- [FastAPI security guide (davidmuraya.com)](https://davidmuraya.com/blog/fastapi-security-guide/)
- [Rate limiting FastAPI (patrykgolabek.dev)](https://patrykgolabek.dev/guides/fastapi-production/rate-limiting/)
- [Is web scraping legal 2026 (browserless.io)](https://www.browserless.io/blog/is-web-scraping-legal)
- [Job board scraping legal risks 2026 (jobboardly.com)](https://www.jobboardly.com/blog/job-board-scraping-complete-guide-2025)
- [Web scraping ethics + robots.txt (medium.com/@ridhopujiono)](https://medium.com/@ridhopujiono.work/web-scraping-2-ethics-legality-robots-txt-how-to-stay-out-of-trouble-39052f7dc63f)
- [Scraping job postings 2026 (cavuno.com)](https://cavuno.com/blog/job-scraping)

**Decision (2026-07-16):** Posture per **T0016** — credential-less CORS (moot same-origin), per-IP rate limit (`15/minute`, `/health` + `/ready` excluded), 2000-char input cap, `/docs` deliberately public. Frame protection now active: **`X-Frame-Options: DENY`** on all responses (T0018.2, verified live). Scraping ToS/robots is **N/A for this deploy** — it ships a static corpus snapshot with no cron; that question re-enters at the ingestion milestone.

**Decision — VietnamWorks robots.txt / ToS (T0019.1, 2026-07-16):** RECOMMENDED VERDICT:
**favorable** — **pending maintainer confirmation.** *(This is the ingestion-milestone re-entry the
2026-07-16 decision above anticipated; it supersedes that decision's final sentence only.)*

- `ms.vietnamworks.com/robots.txt` → **HTTP 404**. **Absent** — this host serves no robots.txt at
  all. The 404 body is a JSON gateway error (`{"message":"no route matched with those values"}`),
  not a robots file, despite its `text/plain` content-type. There are therefore **no crawl
  directives of any kind** governing the `/job-search/` path on the host the pipeline actually
  fetches from. **This is silence — not permission and not refusal** — so the verdict rests on the
  ToS. Archived: `research/experiments/vietnamworks_robots_2026-07-16.txt`. Crawl-delay: **none**.
- `www.vietnamworks.com/robots.txt` → **HTTP 200** (`Last-Modified: 11 May 2026`). One
  `User-agent: *` group; **no `Disallow: /`**, no rule matching `/job-search/`, **no `Crawl-delay`**.
  Disallows only profile / login / apply / print / AJAX / ad / hrinsider-pagination paths — none of
  which the pipeline touches. Context only: this is the content host, not the API host the pipeline
  uses. Archived: `research/experiments/vietnamworks_www_robots_2026-07-16.txt`.
- **ToS** (https://www.vietnamworks.com/thoa-thuan-su-dung, last updated **unknown** — no date shown
  on the page; Vietnamese only): **no clause on automated access found.** The terms `robot`,
  `spider`, `crawler`, `crawl`, `scrape`, `API`, `giao diện lập trình`, `dịch ngược`
  (reverse-engineer), `trích xuất` (extract) and `hàng loạt` (bulk) return **zero matches** in the
  document. Sections reviewed in full: §3 (refusal of service), §4 (terms of use), §5 (user rights
  & responsibilities), §7 (intellectual property), §9 (compliance & violations). The single clause
  using "tự động" (automated) governs **bulk account registration**, not content access — *"Các tài
  khoản được đăng ký một cách tự động và/hoặc có hệ thống với số lượng lớn … được xem là vi phạm"*
  ("Accounts registered in an automated and/or systematic manner in large numbers … shall be deemed
  a violation") — and the pipeline registers no account (`userId: 0`). Excerpt archived with
  verbatim Vietnamese + labeled translations:
  `research/experiments/vietnamworks_tos_excerpt_2026-07-16.md`.
- **Applying the decision rule:** neither trigger fires. robots.txt does not disallow `/job-search/`
  (it does not exist on the API host, and the www host permits it), and the ToS does not explicitly
  prohibit automated access or scraping. Absence of robots.txt is not a disallow; absence of a ToS
  clause is not a prohibition. → **favorable.**
- **⚠️ Caveat the maintainer must weigh (does not trigger the rule, but is the one real finding).**
  ToS §7 (intellectual property) restricts what may be done with content *once obtained*, on an axis
  the decision rule does not test: *"bạn không được quyền thay đổi, sao chép, mô phỏng, truyền, phân
  phối, công bố, tạo ra các sản phẩm phái sinh, hiển thị hoặc chuyển giao, hoặc khai thác nhằm mục
  đích thương mại bất kỳ phần nào của nội dung"* ("you are not entitled to modify, copy, reproduce,
  transmit, distribute, publish, create derivative works from, display or transfer, or commercially
  exploit any part of the content"), with a carve-out permitting copies **"để dùng nội bộ"** ("for
  internal use"). This says nothing about *how* content is fetched — so it is not an automated-access
  prohibition and does not make the verdict unfavorable — but it does bear on **storing postings in a
  DB and displaying them on a public demo**. Note this is a *retention/display* question that the
  already-deployed static snapshot raises **today**, independently of any cron: T0019.6 changes how
  often the corpus refreshes, not whether it is republished. It is therefore not a reason to park the
  cron, but it is a live question for the project's public posture. Registered in
  `docs/Known_Issues.md`. Also recorded, non-binding: §3 lets the Company refuse *service* to those
  who use its information other than for their own recruitment purposes — an account-directed remedy
  (we hold no account), which nonetheless signals intent on non-recruitment reuse.
- **Consequence:** **T0019.6 unblocks once .2–.5 land**, subject to maintainer confirmation of this
  verdict. Conditions to honor: **(1)** no `Crawl-delay` directive exists on either host, so the
  existing `0.6 s` delay + daily cadence stands unchanged — **nothing for T0019.4/.6 to implement**;
  **(2)** keep the pipeline off the paths `www`'s robots.txt disallows (profile / login / apply /
  print / AJAX) — it touches none of them today, and any future source work must preserve that;
  **(3)** this verdict is a **point-in-time fetch** — the API host has no robots.txt *now*; if one
  appears, this gate must be re-run before the cron continues (registered in `Known_Issues.md`).
  The unfavorable branch (`research/ingestion-milestone-plan.md` §1D — park T0019.6, degrade the
  milestone, re-open the source question) is **not** triggered and stays on the shelf.

---

## 12. Synthesis — recommended deployment topology

_Fill last._ One diagram + one paragraph: chosen host for the API, the DB, the cron; the
secret flow; the deploy trigger; and the total monthly cost (target: **$0 → minimal**).
Then hand off to a deployment **design doc** + deploy tickets.

**Confirmed topology (2026-07-16, T0018.4 first deploy):** API on **Render** (Docker `docker/Dockerfile`, Singapore, Free instance) · Postgres on **Neon** (PG17, direct DSN, Singapore, 50+50 rows loaded) · cron **none — ships a static corpus snapshot** (ingestion is a separate later milestone) · Langfuse on **Cloud Hobby (JP)** · CI via **Render auto-deploy on push** (pytest merge-gate deferred).
**Secret flow:** five env vars set in the Render dashboard (never in image/repo) + `PORT=8000`; `DATABASE_URL` in `postgresql+psycopg://…` form.
**Live URL:** https://internhunteragent.onrender.com — verified end-to-end (SSE streaming, Neon query, Groq answer, Langfuse `trace_url`, `/docs`, `X-Frame-Options: DENY`) on 2026-07-16.
**Total expected cost:** **$0/month** (hard ceiling $10).
**Known operational caveat:** the Free instance spins down after 15 min idle, and because the UI is same-origin a cold visitor waits ~60 s for the *page itself*. Mitigation decided but not yet applied — a windowed keep-alive ping of `/api/v1/health` (**§1a**, incl. the Render-policy check and the 750-instance-hour constraint). Both the cold start and the hours cliff are registered in `docs/Known_Issues.md` § Config, startup & deployment. Escape hatch: Render Starter $7/mo (§10).
