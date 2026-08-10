## Current branch

> **Ticket status (2026-08-10):** `feature/t0022.2-encoding-parity-orphans` contains completed
> T0022.2 work, pending review and merge. It repairs the T0019.10 mojibake, preserves agent
> surfaces, removes the tagged `milestone/` scratchpad, and corrects the stale Langfuse README.

`main` — **`a5ff82e`**, and it is the only branch. As of **2026-08-09** the repo is quiet: no other local or remote branches, no worktrees, no open PRs. `main` is the single source of truth for what is built, what is deployed, and what is tested.

**Everything through T0021.2 has landed.** The M10–M19 chain, the T0020 reconciliation/activation milestone, and T0021.1–.2 are all merged. The historical branch topology — the per-ticket "Prior ticket — …" chain, the 2026-07-22 prune record, and the reality-check box that had accumulated three layers of correction-on-correction — is archived in [`archive/Repo_State_History.md`](archive/Repo_State_History.md). It is history, not guidance; do not reconcile against it.

**Deployed topology** (unchanged since T0018.4): API on **Render** (Docker, Singapore, Free, `WEB_CONCURRENCY=1`, health check `/api/v1/health`), Postgres on **Neon** (PG17), tracing on **Langfuse Cloud Hobby (JP)**. Secrets are Render env vars; `api.cors.allowed_origins` stays `[]` (same-origin). Render deploys from `main`, pinned by the tracked `render.yaml` (T0020.2) and confirmed live 2026-08-09. **LIVE: https://internhunteragent.onrender.com**

**Neon is at Alembic head** (`b7e2f4a91c3d`) as of the D6 migration, 2026-08-09 — `clean_jobs` has the full 22 columns. This is what unblocked T0021.1's boot-time schema guard; before it, that guard would have aborted the FastAPI boot on Render. Execution record: [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md) §3.

**CI:** `.github/workflows/ci.yml` runs `ruff` + `mypy` + `pytest -q` on every PR targeting `main`. It is live and has gated real merges (first code-change run: PR #39, green in 44s). **Branch protection to *enforce* it remains a pending maintainer action** — until that is set, a green check is advisory and a red one does not block.

**Ingestion cron:** `.github/workflows/ingestion.yml` is present on `main` with `schedule:` **commented out**, so `workflow_dispatch` is the sole trigger. The dormancy is deliberate and the activation sequence is gated — follow [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md), not this file. Setting the `DATABASE_URL` secret is the irreversible step.

### Archive tags — cite these, not branch names
The branches they replaced no longer exist.

| Tag | Commit | What it preserves |
|---|---|---|
| `archive/t0015.2-behavior-glossary` | `62f2089` | The **complete 18-string `behavior_glossary`** frozen by T0015.2 but never landed into `config/prompts.yaml`. Recover with `git show archive/t0015.2-behavior-glossary:config/prompts.yaml`. |
| `archive/t0015.4-scenario-matrix` | `eba3e1f` | The 29-scenario graded matrix **plus the harness that produced it** (`run_scenario_matrix.py`, `scenarios_v1.yaml`, the observed JSON) — needed for any re-measurement. |
| `archive/t0015.6-provider-ab` | `45d333c` | The provider/reasoning A/B phase. **Deliberately not revived** — A/B is out of scope for v1. Also holds `src/core/event_loop.py`, a Windows `SelectorEventLoop` factory for uvicorn that is not in the tree. |
| `archive/stash-t0019.6-docs` | `b7a291e` | The former `stash@{0}` from T0019.6. Its `Schema_Contract.md` fix is landed (with two corrections); the tag preserves the original and the other nine files verbatim. |

### Two carried items
- **`stash@{0}`** ("concurrent-session: error-handling observability audit — Known_Issues + Tickets") is still present. Its content is *believed* superseded: the audit it holds landed as `3a796fa`, and T0021.2 has since resolved three of its entries. It has **not** been verified line-by-line, so it is kept rather than dropped. Tag-and-drop is the house pattern — see `archive/stash-t0019.6-docs`.
- **M15 behavior track, partially reclaimed.** `docs/Agent_Behavior_Spec.md` (the T0015.2 spec of record) and `evals/v1_scenario_matrix.md` (29 scenarios, 13 pass / 16 fail) are in the tree, restored from `archive/t0015.4-scenario-matrix` because `research/honesty-enforcement-design.md` cites both as its evidence base. **The scenario harness was not restored** — it stays on the tag, so re-measurement means recovering it first. **`behavior_glossary` still does not exist** in `config/prompts.yaml`; landing it is owned follow-up work, deliberately deferred because it changes agent output. See `Known_Issues.md` → Repo state & version control.

## Completed milestones
One line per milestone. Per-ticket detail (files changed, test counts, follow-ups) lives in [`Completion_Reports.md`](Completion_Reports.md).

- **M0–M5** — Foundation → runnable request flow → ReAct runtime → self-hosted Langfuse → tracing integration → hardening.
- **M6** (T0006.1–.10) — First real SQL tool: read-only `query_clean_jobs` (schema → SQL gen → validate → execute → format), registered in the runtime, public API kept answer-only.
- **M7** (T0007.1–.4) — Short-term conversation memory: native Postgres checkpointer + async pool, `session_id → thread_id`, native `trim_messages` count cap.
- **M8** (T0008.1–.3) — Resumi persona, on-topic/honesty rules, SQL-generation hardening, schema context moved into `config/prompts.yaml`.
- **M9** (T0009.1–.11) — VietnamWorks data ingestion: `raw_jobs` landing + enriched `clean_jobs`, source-agnostic transform, idempotent loader; plus reset path, bounded query output (Groq `413` fix), and the `get_job_details` detail split.
- **M10** (T0010.1/.3/.4) — Pre-deploy hardening: typed error contract + graceful answer, true single-table SQL allowlist, off-event-loop LLM call; code-review bugs 3 & 4 fixed.
- **M11** (T0011.1–.6) — Model evaluation harness: DeepEval judge (Groq→Gemini) + RPM throttle, seeded fixture DB + versioned goldens, three-seam metric stack, Langfuse score writeback.
- **M12** (T0012.2–.10) — Hardening: qwen `<think>` leak fix, deepeval metric-template unblock, `trace_url` populated, graceful empty-answer fallback, non-str content coercion, eval-test marker hygiene, native-async `generate_sql`, cosmetic cleanup, eval judge cost/rate-limit reduction.
- **M13** (T0013.1–.5) — Schema Enrichment & v1 Freeze: `tech_stack` rebuilt against an external vocabulary (audit coverage 58% → 89%); `job_level`, `listing_expires_on`, and `created_on` exposed to the agent; the enriched **16-column** v1 contract recorded in [`Schema_Contract.md`](Schema_Contract.md) and enforced by prompt-freeze guards. (Historically the base of the long-lived T0014–T0019 branch chain, `51913f6`.)
- **M16** (T0016.1–.4) — Public-endpoint hardening: credential-less CORS, per-IP rate limit + friendly busy path, request length cap, explicit `/docs` exposure decision.
- **M17** (T0017.1–.2) — Streaming response delivery: runtime `astream` + no-leak filter, streaming service + `POST /api/v1/agent/chat/stream` SSE endpoint.
- **M19** (T0019.1–.10) — Ingestion deploy readiness: robots/ToS gate, Alembic baseline + lifecycle columns, accumulate/upsert semantics, source resilience + retry, unattended-run safety, nightly cron, keep-alive runbook, truthful `/ready` refresh date, ingestion coverage cap+interleave, `get_job_details` column allowlist. Landed on `main` via PR #29. **Note:** the cron was documented as dormant/human-gated but in fact auto-activated on that merge — GitHub arms `schedule:` from the default branch — and failed nightly for 19 days on a missing secret. Corrected and parked; full account in `Resolved_Issues.md` and the T0020.4 runbook.
- **M20** (T0020.1–.4) — Reconciliation & activation, **complete as a coder milestone**: `main` reconciled as the true head after PR #29 (.1); Render's deploy source repointed to `main` and pinned by a tracked `render.yaml` (.2); the `ruff` + `mypy` + `pytest` CI merge gate landed and now gating (.3); and the gated cron-activation sequence captured as an executable runbook (.4). The two pre-existing `mypy [arg-type]` errors were baselined with targeted `# type: ignore` so the gate is genuinely green. **Two maintainer actions remain open**: branch protection to *enforce* the gate, and the cron activation itself.
- **M21** (T0021.1–.2, in progress) — Serving-path hardening & honesty baseline: boot-time `clean_jobs` schema guard on the read path (.1, PR #30 — held until the D6 migration took Neon from 19 to 22 columns, then merged); `logger.error` at the three swallowed catch sites the error-handling honesty audit named (.2, PR #39). **T0021.3/.4 are named but unscoped** — see `Tickets.md` → T0021.

## In progress / next
**Nothing in progress.** `main` carries everything below — the full T0016 → T0021 stack (security posture → streaming → clickable demo → deploy → ingestion readiness → reconciliation → serving-path hardening), plus the SQL-generation reasoning-effort hotfix and the ReAct/SQL-generation config split — and it is deployed. What follows is a capability inventory of what is live, not a work queue; for what to do next see **Next recommended ticket** at the end of this file.

- **T0016.1 - CORS middleware:** `config/settings.yaml` carries `api.cors`, and `src/api/app.py` registers credential-less `CORSMiddleware`.
- **T0016.2 - Rate limiting and friendly busy path:** `slowapi` is installed, `api.rate_limit` defaults to `"15/minute"`, chat is limited, health is not, and provider pressure maps to a public-safe busy response.
- **T0016.3 - Request input hardening:** `api.max_query_chars: 2000` is recorded in config, while `src/api/schemas.py` currently enforces the matching static `DEFAULT_MAX_QUERY_CHARS = 2000` Pydantic cap. If this value changes later, update both or introduce a deliberate config-backed schema loader.
- **T0016.4 - `/docs` exposure and headers decision:** `api.docs_enabled: true` keeps `/docs`, `/redoc`, and `/openapi.json` public for the portfolio demo; `api.docs_enabled: false` disables all three.
- **T0017.1 - Runtime streaming + no-leak filter:** `AgentRuntime.astream(...)` emits filtered token events plus trailing metadata without exposing tool internals.
- **T0017.2 - Streaming service + SSE endpoint:** `POST /api/v1/agent/chat/stream` emits the public `session` → `token`* → `metadata`/`error` → `done` contract.
- **T0018.1 - Go-live glue:** `generate_agent_response(...)` and `stream_agent_response(...)` mint UUID4 session ids when omitted; `config/settings.yaml` records `api.demo.data_snapshot_date`; `GET /api/v1/ready` runs `SELECT 1` outside the chat limiter and returns readiness plus the snapshot date.
- **T0018.2 - Same-origin static serving + frame protection:** `src/api/app.py` mounts `src/api/static/` at `/` after API/docs routes and injects `X-Frame-Options: DENY` with a pure-ASGI middleware.
- **T0018.3 - Editorial streaming chat UI:** `src/api/static/index.html` + `styles.css` + `app.js` replace the placeholder with the vanilla, Editorial-styled demo page (system serif stack, hairline rules, restrained vermilion accent, light theme only). It consumes `POST /api/v1/agent/chat/stream` via `fetch()` + a `ReadableStream` reader, renders tokens one-by-one, reads the disclaimer snapshot date from `GET /api/v1/ready`, ships 4 send-on-click honesty chips, pins the server session id and reuses it on later turns, shows a `view-trace` link only when `trace_url` is non-null, and degrades mid-stream `error` events to a friendly bubble and pre-stream 400/429 to a toast. No backend change.
- **Split ReAct/SQL-generation LLM config - Backend hotfix:** `AgentProvider.build_model("react")` builds the outer ReAct model from `agent.react`; `AgentProvider.build_model("sql_generation")` builds the nested SQL-generation model from `agent.sql_generation`. Both profiles expose the same model fields, and only the SQL-generation profile sets `reasoning_effort: "none"`.
- **T0018.4 - Deploy topology + first public deploy:** API on **Render** (Docker, Singapore, Free, `WEB_CONCURRENCY=1`, health check `/api/v1/health`), Postgres on **Neon** (PG17, static 50-row snapshot), tracing on **Langfuse Cloud Hobby (JP)**; secrets are Render env vars, `api.cors.allowed_origins` stays `[]` (same-origin). Auto-deploy on push to `main`. **$0/mo** against a $10 ceiling. No app-code change was needed. **Live: https://internhunteragent.onrender.com**, verified end-to-end 2026-07-16.

- **T0019.1 - robots.txt / ToS gate (doc-only, no code):** resolved the `deployment-research-plan.md` §11 hard gate. **`ms.vietnamworks.com` serves no robots.txt at all (HTTP 404)**; `www.vietnamworks.com/robots.txt` permits the relevant paths with no `Crawl-delay`; the ToS contains **no** automated-access/scraping clause. **Recommended verdict: favorable — pending maintainer confirmation**, so **T0019.6 stays blocked until the maintainer signs off** (then on T0019.2–.5). Evidence archived under `research/experiments/` (both robots fetches + a ToS excerpt with verbatim Vietnamese and labeled translations); decision record in `research/deployment-research-plan.md` §11. One caveat registered in `Known_Issues.md`: ToS §7 restricts *republishing* content — a live question for the public demo, but not a cron blocker, since the deployed snapshot already raises it today.

- **T0019.2 - Alembic adoption: baseline migration + env wiring:** replaced `scripts/reset_db.sql` (DROP + recreate) as the de-facto migration strategy — that stops working once T0019.3 makes `raw_jobs` accumulate irreplaceable postings. Added `alembic` (`pyproject.toml`), scaffolding (`alembic.ini`, `alembic/env.py` reading `ALEMBIC_DATABASE_URL` → falls back to `settings.DATABASE_URL`, `target_metadata = Base.metadata`), and one hand-written baseline migration (`alembic/versions/f3a1c9d2e7b4_baseline_schema.py`, `down_revision = None`) reproducing the exact schema in `scripts/init_db.sql`. Aligned `RawJob.id`/`CleanJob.id` in `models.py` to `Identity(always=True)` (metadata-only fix — the DB already used `GENERATED ALWAYS AS IDENTITY`; the ORM metadata previously disagreed). `scripts/reset_db.sql` demoted to a local-dev-only header comment; `scripts/init_db.sql` untouched (the eval fixture loader still depends on it). New opt-in `tests/migrations/test_baseline_roundtrip.py` (skips without `SCRATCH_DATABASE_URL`). Verified: empty-DB `alembic upgrade head` builds the full 19-column `clean_jobs` schema correctly; the round-trip test passes against a scratch DB; `alembic stamp head` + `alembic upgrade head` is a clean no-op against the real local DB (row count unchanged at 50); the app boots and answers a live query against the migrated schema — verified via the Dockerized (Linux) `api` service, since native Windows `uv run uvicorn` hangs on a pre-existing, ticket-unrelated `ProactorEventLoop`/async-psycopg incompatibility (`Known_Issues.md`).

- **T0019.3 - Accumulate load semantics + hidden lifecycle columns:** dropped the `TRUNCATE` in `clean_store.py` — the already-written `ON CONFLICT (source, external_id) DO UPDATE` upsert (renamed `replace_clean_jobs` → `upsert_clean_jobs`) is now live code, so `raw_jobs`/`clean_jobs` accumulate across runs instead of being rebuilt each time. Added three hidden bookkeeping columns to `clean_jobs` — `is_active boolean not null default true`, `first_seen_at`/`last_seen_at timestamptz not null default now()` — via `alembic/versions/b7e2f4a91c3d_lifecycle_columns.py` (`down_revision = f3a1c9d2e7b4`), with a backfill from `raw_jobs.fetched_at` (confirmed the join was total: 0 orphaned `clean_jobs` rows on the 50-row local snapshot, so no row was left defaulted to migration-run time). The upsert now refreshes `last_seen_at = now()` and flips `is_active = true` on every conflict, and never touches `first_seen_at` (insert-only). New `expire_stale_clean_jobs(expire_after_days)` in `clean_store.py` runs a single time-based `UPDATE ... SET is_active = false WHERE last_seen_at < now() - make_interval(days => :days)` — never `DELETE`, never "not seen this run." `loader.py::run_ingestion` calls it after the upsert using `config/ingestion.yaml`'s new `lifecycle.expire_after_days: 7`, and the run summary gained `expired_count`. All three columns stay off the agent-visible surface — no `NormalizedJob`, `Schema_Contract.md`, or `config/prompts.yaml` change; the hidden-column guard in `tests/agents/runtime/test_prompts.py` was extended to assert `is_active`/`first_seen_at`/`last_seen_at` never appear in `schema_context`. `scripts/init_db.sql` was deliberately left untouched (now diverges from the Alembic head — logged in `Known_Issues.md`). Verified live against the local Docker DB: empty-DB `alembic upgrade head` builds the full 22-column schema; `alembic downgrade -1` cleanly drops the three columns; upgrading the real local DB preserved all 50 rows with a true backfill (0 rows at "now"); a synthetic row proved two upserts keep `is_active=true`/refresh `last_seen_at`/preserve `first_seen_at`, an 8-day-aged row flips to `is_active=false` under a 7-day window without being deleted, and re-seeding it flips `is_active` back to `true`; the Dockerized `api` service answered a live chat query ("13 AI Engineer jobs") with no mention of the hidden columns.

- **T0019.4 - Source resilience: per-page try/continue + retry/backoff:** `config/ingestion.yaml` gains `api.retry_attempts: 2` / `api.retry_backoff_seconds: 2.0`. `JobSource` (`sources/base.py`) gains a class-level `pages_failed: int = 0` counter. `VietnamWorksSource._post` stays an unchanged thin primitive; a new `_post_with_retry` wrapper retries transient failures (429, ≥500, timeouts, transport errors) with doubling backoff (2s, then 4s) and gives up immediately on permanent 4xx — on give-up it increments `pages_failed`, logs `ingestion.page_failed` (query + page + attempts + reason), and returns `None` without raising. `_collect` treats `None` as "skip this page" and a `try/finally` around the per-page body guarantees the politeness `time.sleep(self._delay)` still runs even when a page is skipped. `fetch()` resets `pages_failed = 0` at entry so a reused instance doesn't accumulate across runs. `loader.py::run_ingestion` reads `getattr(source, "pages_failed", 0)` after draining the generator and adds `"pages_failed"` to the summary dict — no other loader ordering changed. A single transient failure no longer discards an entire run's already-fetched pages.

- **T0019.5 - Unattended-run safety: pre-flight schema assertion, yield floor, dead-man ping:** new `src/services/ingestion/safety.py` with `IngestionSafetyError` and three functions. `assert_clean_jobs_schema()` queries live `information_schema.columns` for `clean_jobs` and compares against `{c.name for c in CleanJob.__table__.columns}` (derived from the ORM, never hand-maintained); on any mismatch it logs `ingestion.schema_drift` (missing + unexpected, both directions) and raises before any write — an absent table (empty column set) also raises, with its own message rather than listing all columns "missing." `assert_min_yield(fetched, min_yield)` raises `IngestionSafetyError` naming both numbers when `fetched < min_yield`, logging `ingestion.yield_floor_breached` first. `send_dead_man_ping(url)` POSTs to a healthchecks.io URL via `httpx`; `None`/empty logs `ingestion.ping_skipped` and returns `False` (the normal local path, not an error); any `httpx.HTTPError` or non-2xx logs `ingestion.ping_failed` as a warning and returns `False` without raising — a ping failure never fails the run. `config/ingestion.yaml` gains `safety.min_yield: 20`. `src/core/config.py` gains one optional field, `HEALTHCHECKS_URL: str | None = None`; documented (commented, optional) in `.env.example`. `loader.py::run_ingestion` now calls `assert_clean_jobs_schema()` first — before the source is constructed or anything fetched — then fetches, upserts raw (evidence preserved even on a bad run), calls `assert_min_yield(len(postings), settings.ingestion_yaml["safety"]["min_yield"])`, and only then normalizes/upserts clean/expires; a yield-floor abort happens before both the clean upsert and the expiry pass, so a skipped clean write can never have `expire_stale_clean_jobs` wrongly age out untouched rows. `run_ingestion` stays library code — it lets `IngestionSafetyError` propagate, no `sys.exit`. `main()` now owns the process contract: catches `IngestionSafetyError`, logs `ingestion.aborted`, exits 1; on the fully-green path it logs the existing `ingestion.completed` summary (unchanged: `fetched`/`raw_upserted`/`clean_loaded`/`skipped`/`expired_count`/`pages_failed`) and only then calls `send_dead_man_ping(settings.HEALTHCHECKS_URL)` — withholding the ping on any abort is the dead-man signal. All nine pre-existing `test_loader.py` tests were updated to patch the new `assert_clean_jobs_schema` and set `safety.min_yield: 0` in their mocked `ingestion_yaml` (no assertion weakened); three new loader tests cover schema-abort, yield-floor-abort, and the happy-path ordering/summary shape. New `tests/services/ingestion/test_safety.py` covers both schema-assertion mismatch directions, the empty-table case, both `assert_min_yield` branches, and all three `send_dead_man_ping` paths.

- **T0019.7 - Windowed keep-alive ping + Neon idle-pool verification (doc-only):** applies the cold-start mitigation decided 2026-07-16 but never executed — a windowed external ping of `GET /api/v1/health` to keep Render's free instance from spinning down. No code changed; this ticket produced an executable runbook (`Manual_Verification_Guide.md` → `### T0019.7`: cron-job.org setup steps, a 24-hour measurement template with the "expected if healthy" arithmetic worked out, and a pre-written, numerically-triggered decision rule), an updated `deployment-research-plan.md` §1a with an empty outcome-record slot for the maintainer to fill in after the 24 h observation, and updated `Known_Issues.md` entries reflecting that the ping is now documented-and-ready rather than merely decided. The open question the runbook exists to answer — whether the checkpointer's idle Postgres pool alone keeps Neon awake regardless of which endpoint is pinged — remains genuinely unmeasured; enabling the ping, taking readings, and applying the decision rule are maintainer actions, not yet executed.

- **T0019.8 - Truthful refresh date on `/ready`:** `/api/v1/ready` no longer reports a hand-maintained static date. `src/api/routes/health.py` splits the old `get_data_snapshot_date` into `_configured_snapshot_date()` (the static `api.demo.data_snapshot_date` fallback, with its defensive handling of a malformed `api.demo` block intact) and a data-derived `get_data_snapshot_date()` backed by a new `_select_max_last_seen()` running `SELECT MAX(last_seen_at)::date FROM clean_jobs` through the existing `session_factory`. The fallback fires on an empty table (`snapshot_date_empty_table_using_config_fallback`) or any query failure (`snapshot_date_query_failed_using_config_fallback`, logged with `exc_info`). `readiness_check` runs the date query via `asyncio.to_thread` **after** the `SELECT 1` probe, so a DB failure still short-circuits to 503 without attempting it. Response shape, field name, and the UI are unchanged — only the value's source moved; layer isolation holds (plain SQL against a table, no `src.services.ingestion` import). `tests/api/test_ready.py` carries 7 cases. Also corrected three untrue statements found in the working tree: `MVP_Technical_Design.md` §11.3 named `MAX(fetched_at)` (wrong table — `fetched_at` is on `raw_jobs`), the §7 banner claimed the T0019.1 ToS verdict was maintainer-confirmed (no committed doc records it), and the same banner claimed T0019.6 was built (its workflow is untracked).
- **T0019.9 - Ingestion coverage (raised cap + round-robin interleave):** the served corpus was both truncated and skewed. `config/ingestion.yaml`'s `max_jobs` moved `50 → 150` — a safety ceiling deliberately above the measured ~50–112 yield, not a target — and `VietnamWorksSource._collect` now iterates **page outer / query inner** (page 0 of every query, then page 1), so a cap truncates evenly across queries rather than exhausting the config list from the top and structurally starving `"MLOps"`, `"computer vision"`, `"deep learning"`. Both fixes were required; neither suffices alone. All T0019.4 invariants are preserved: `seen_ids` stays initialised once outside both loops (cross-query dedup), all three cap checks remain so the cap is still exact and global, `_is_ai_data` is unchanged, `time.sleep(self._delay)` still runs in the `finally` for every page attempt including skipped ones, and `_post_with_retry`'s None-means-skip semantics and `pages_failed` accounting are untouched. Request *count* is identical (`pages_per_query x queries` = 16, both unchanged); only order changes. `tests/services/ingestion/test_vietnamworks.py` gains `VietnamWorksCoverageTests` (6 cases), whose anti-skew case was **confirmed to fail** against the reverted query-outer loop before the interleave was restored. **No live API request was issued** — the ticket is gated on decision D8, so the re-measure it calls for is written as a runbook with empty result slots in `research/data-ingestion-stage.md` §11 and left for the maintainer.

- **T0019.6 - GitHub Actions nightly ingestion cron (recovered + committed):** lands `.github/workflows/ingestion.yml` — `schedule: '0 2 * * *'` (02:00 UTC / 09:00 ICT) + `workflow_dispatch`; `concurrency: {group: ingestion, cancel-in-progress: false}`; `timeout-minutes: 15`; `permissions: {contents: read}`; SHA-pinned `actions/checkout` + `astral-sh/setup-uv`; `uv sync --frozen --no-dev` then `uv run python -m src.services.ingestion.loader`. **Secrets block deviates from the ticket's original text** (maintainer decision, this session): `GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY` are set to the literal `"unused-by-ingestion"` rather than real GitHub secrets — `src/core/config.py`'s `Settings` requires them at import with no default, but ingestion is deterministic and reads none of their values (empirically verified — see `Manual_Verification_Guide.md` T0019.6 check B). Only `DATABASE_URL` and `HEALTHCHECKS_URL` come from `secrets.*`. The keepalive step (`gautamkrishnar/keepalive-workflow`) is deliberately omitted, not stubbed — the action's repo is 403'd by GitHub Staff for a ToS violation and cannot be SHA-pinned; risk logged in `Known_Issues.md`. Amends `Full_Design_Document.md` §2's "no schedulers" exclusion to scope it to the *serving path* only, naming this workflow as the one permitted out-of-band exception. **~~Committed, now on `main`, still dormant~~ — WRONG, corrected 2026-08-09.** GitHub only fires `schedule:` from the default branch — but that means landing on the default branch **activates** it. The T0019 chain merged to `main` via **PR #29 (`bcc81db`, 2026-07-22 — the T0020.1 reconciliation)**, and **the cron started firing that same day**. It was never dormant on `main`, and activation was never "a maintainer action gated on D2/D5" — it happened automatically with **D2 and D6 unsigned**. All 19 nightly runs (2026-07-22 → 2026-08-09) failed at config load for want of a `DATABASE_URL` secret, so no scrape or production write occurred. `schedule:` is now commented out on `main` (**PR #33**), making the workflow genuinely dormant and restoring the gated-activation story this paragraph originally asserted. Both release gates the spec named — **T0019.9** and **T0019.10** — have landed. No file under `src/`, `tests/`, or `config/` was touched.

**Status (2026-08-09):** everything listed above is complete and merged to `main`. The residual non-code items are: **T0019.1**'s D2 verdict still needs ratifying in a tracked doc; **T0019.7**'s keep-alive ping is written but not enabled (maintainer action); **T0019.9** stays `PARTIALLY RESOLVED` in `Known_Issues.md` because confirming `max_jobs: 150` clears the API ceiling needs a live re-measure blocked on decision **D8** (runbook with empty result slots at `research/data-ingestion-stage.md` §11); and **T0019.8/.10** still carry live-DB manual checks that could not run while Docker Desktop was down. Auto-deploy runs off `main`.

**Milestone map (see `Tickets.md`):** T0013 freeze → T0016 security posture → T0017 streaming response delivery → T0018 clickable demo UI + go-live ✅ → **T0019 ingestion deploy readiness ✅ landed via PR #29** → **T0020 reconciliation & activation ✅ coder slice complete** (.1 `main` reconciled, .2 Render→`main`, .3 CI gate live, .4 runbook committed; branch protection and cron activation are maintainer actions) → **T0021 serving-path hardening & honesty baseline ◀ in progress** (.1 ✅ schema guard, .2 ✅ error logging, .3/.4 unscoped) → T0022 v1.0 release cut.

**Next recommended ticket:** see [Next recommended ticket](#next-recommended-ticket) below — every T0019 sub-ticket is now code-complete; what remains is maintainer-gated.

## Current folder structure
```text
.
|-- .github/
|   `-- workflows/
|       |-- ci.yml
|       `-- ingestion.yml
|-- alembic.ini
|-- alembic/
|   |-- env.py
|   |-- script.py.mako
|   `-- versions/
|       |-- f3a1c9d2e7b4_baseline_schema.py
|       `-- b7e2f4a91c3d_lifecycle_columns.py
|-- config/
|   |-- ingestion.yaml
|   |-- prompts.yaml
|   `-- settings.yaml
|-- docker-compose.yml
|-- docker/
|   `-- Dockerfile
|-- infra/
|   |-- docker-compose.yaml
|   `-- langfuse/
|       `-- README.md
|-- scripts/
|   |-- eval_judge_spike.py
|   |-- init_db.sql
|   `-- reset_db.sql
|-- evals/
|   |-- __init__.py
|   |-- conftest.py
|   |-- harness.py
|   |-- judge.py
|   |-- writeback.py
|   |-- test_judge_scaffold.py
|   |-- test_judge.py
|   |-- test_goldens_load.py
|   |-- test_three_seams.py
|   |-- test_writeback.py
|   |-- fixtures/
|   |   |-- __init__.py
|   |   |-- loader.py
|   |   |-- seed_eval_db.sql
|   |   `-- test_fixture_counts.py
|   `-- goldens/
|       |-- __init__.py
|       `-- golden_dataset.json
|-- docs/
|-- src/
|   |-- agents/
|   |   |-- runtime/
|   |   |   |-- factory.py
|   |   |   |-- middleware.py
|   |   |   |-- prompts.py
|   |   |   |-- provider.py
|   |   |   `-- react_agent.py
|   |   |-- tools/
|   |   |   |-- get_job_details.py
|   |   |   |-- query_clean_jobs.py
|   |   |   `-- time.py
|   |   |-- tracing/
|   |   `-- service.py
|   |-- api/
|   |   |-- app.py
|   |   |-- schema_guard.py
|   |   |-- schemas.py
|   |   |-- routes/
|   |   `-- static/
|   |       |-- index.html
|   |       |-- styles.css
|   |       `-- app.js
|   |-- core/
|   |   |-- checkpointer.py
|   |   |-- config.py
|   |   |-- db.py
|   |   |-- errors.py
|   |   `-- logger.py
|   `-- services/
|       |-- ingestion/
|       |   |-- __init__.py
|       |   |-- models.py
|       |   |-- raw_store.py
|       |   |-- clean_store.py
|       |   |-- loader.py
|       |   |-- safety.py
|       |   |-- transform.py
|       |   |-- normalize/
|       |   |   |-- __init__.py
|       |   |   `-- vietnamworks.py
|       |   `-- sources/
|       |       |-- __init__.py
|       |       |-- base.py
|       |       `-- vietnamworks.py
|       `-- query/
|           |-- executor.py
|           |-- job_details.py
|           |-- models.py
|           |-- sql_validator.py
|           `-- table_formatter.py
|-- tests/
|   |-- core/
|   |-- agents/
|   |   |-- runtime/
|   |   `-- tools/
|   |-- api/
|   |   `-- test_static_serving.py
|   |-- migrations/
|   |   `-- test_baseline_roundtrip.py
|   `-- services/
|       `-- query/
|-- pyproject.toml
|-- uv.lock
|-- README.md
|-- AGENTS.md
`-- .env
```

Notes on the reorg (commit `182aac0`): the Langfuse Docker stack moved from `docker/docker-compose.yaml` to `infra/docker-compose.yaml` (with a companion `infra/langfuse/README.md`), and the app-only Postgres compose file lives at the repo root (`docker-compose.yml`) on port `5433` to avoid colliding with the Langfuse stack's own Postgres.

## Installed dependencies
Runtime dependencies declared in `pyproject.toml`:
- `alembic>=1.14` (T0019.2 — schema migrations; `alembic.ini` + `alembic/` at repo root)
- `fastapi>=0.136.3`
- `langchain>=1.3.1`
- `langchain-groq>=1.1.2`
- `langfuse>=4.6.1`
- `pydantic-settings>=2.14.1`
- `psycopg[binary,pool]>=3.2`
- `sqlalchemy>=2.0`
- `structlog>=25.5.0`
- `uvicorn>=0.48.0`
- `langgraph-checkpoint-postgres>=2.0`
- `cloudscraper>=1.2.71`
- `beautifulsoup4>=4.15.0`
- `lxml>=6.1.1`
- `httpx>=0.27`
- `slowapi>=0.1.10` (T0016.2 - in-process per-IP rate limiting for the public chat endpoint)
- `langchain-google-genai>=4.2.6` (T0011.6 — eval judge only; the request path never uses it)

Dev/test dependencies declared in `pyproject.toml` under `[dependency-groups] dev`:
- `pytest>=9.1.1`
- `pytest-asyncio>=1.4.0`
- `pytest-mock>=3.15.1`
- `ruff>=0.15.20`
- `mypy>=2.1.0`
- `deepeval>=4.0.7` (T0011.1 — eval/judge tooling only, not in the prod runtime image)

`anyio` and `langsmith` are transitive (pulled in by `fastapi`/`langchain`), not declared directly.

## Available scripts
No package scripts or `tool.*.scripts` entries are defined in `pyproject.toml`.

**CI (T0020.3) — NOT ACTIVE (corrected 2026-08-09).** `.github/workflows/ci.yml` exists only on the unmerged `feature/t0020.3-ci-merge-gate` branch (**PR #32**). It is **not on `main`** (`git ls-tree main .github/` → only `ingestion.yml`) and GitHub does not know it (`gh run list --workflow=ci.yml` → HTTP 404). When merged it will run `uv run ruff check .` + `uv run mypy` + `uv run pytest -q` on every PR targeting `main`. Until PR #32 lands, **no PR is linted or tested by CI** — PRs #30–#33 show only a GitGuardian check. Enforcement as a *required* check is a further pending maintainer branch-protection action — see `Known_Issues.md`.

Practical commands from the repository layout:
- `uv run uvicorn src.api.app:app --reload`
- `uv run pytest` (T0012.7: the standard suite excludes the `eval`-marked live tests by default — `addopts = "-m 'not eval' --strict-markers"` in `pyproject.toml`)
- `uv run pytest -m eval` (runs only the two live-API eval files, `evals/test_judge_scaffold.py` + `evals/test_three_seams.py`, 18 tests total; needs Groq/judge creds + fixture DB)
- `PYTHONUTF8=1 uv run deepeval test run evals/test_three_seams.py -m eval` (the verified working `deepeval` invocation — `-m eval` must be passed through explicitly or 0 tests are selected; see `Known_Issues.md`)
- `uv run ruff check .` (lint; config in `pyproject.toml` `[tool.ruff]`, `scripts/` spikes excluded)
- `uv run mypy` (type check `src`; config in `pyproject.toml` `[tool.mypy]`, pydantic plugin enabled)
- `python -m evals.fixtures.loader` (builds/refreshes the `internhunter_eval` fixture DB from scratch, prints `COUNT(*)`, T0011.2)
- `python -c "from evals.fixtures.loader import reset_fixture; reset_fixture()"` (drops + rebuilds the fixture tables)
- `docker compose up -d` (root `docker-compose.yml`: Postgres + API, port `5433` host-side)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql` (routine, non-destructive schema init/no-op; retained because `evals/fixtures/loader.py` depends on it to build the eval fixture DB — it and the Alembic baseline migration coexist as two independent schema-creation paths)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql` (**destructive, local dev only** — production and any deployed schema change goes through Alembic; must never be pointed at Neon)
- `uv run alembic current` (T0019.2 — shows the revision the target DB is stamped at)
- `uv run alembic history` (T0019.2 — lists migration history)
- `uv run alembic upgrade head` (T0019.2 — applies pending migrations; DSN from `ALEMBIC_DATABASE_URL` or falls back to `settings.DATABASE_URL`)
- `docker compose -f infra/docker-compose.yaml up --build` (Langfuse observability stack)

## Build/test status
**Current `main` (`a5ff82e`), measured 2026-08-09.** This section is deliberately current-only — one state, not a ledger. Per-ticket logs are archived: T0011–T0018.3 and T0019.3–T0019.10 both in [`archive/Repo_State_History.md`](archive/Repo_State_History.md). Those historical numbers are **not comparable** to these; the suite grew, skip behaviour changed, and T0020.3 baselined the two long-standing `mypy [arg-type]` errors that recur throughout them.

| Check | Result |
|---|---|
| `uv run pytest -q` | `346 passed, 1 skipped, 19 deselected, 4 subtests passed` in 5.71s |
| `uv run ruff check src tests` | all checks passed |
| `uv run mypy src` | `Success: no issues found in 43 source files` |
| CI gate (PR #39) | green in 44s — `ruff` + `mypy` + `pytest -q` |

- **The one skip is expected:** `tests/migrations/test_baseline_roundtrip.py` needs `SCRATCH_DATABASE_URL` pointed at a throwaway Postgres. The 19 deselected are the eval tests, auto-deselected by `pyproject` addopts.
- **`mypy` is genuinely clean.** Any statement elsewhere in the docs about "2 pre-existing `[arg-type]` errors" (`src/core/checkpointer.py`, `src/agents/runtime/middleware.py`) is historical — T0020.3 baselined both with targeted `# type: ignore[arg-type]`, so a new error now is a real regression, not noise.
- **Last change measured against its own baseline:** T0021.2 was `346` vs a `342` baseline taken in the same session on the same base with changes stashed, so its `+4` is measured rather than asserted.

## Known issues
Open known issues, risks, and out-of-scope follow-ups live in their own living register:
see [`Known_Issues.md`](Known_Issues.md). Append there when a ticket uncovers a new one.
Resolved items are archived in [`Resolved_Issues.md`](Resolved_Issues.md). A full per-module
logic review (2026-07-02) — bugs, improvement backlog, and doc insights — is captured in
[`Code_Review_Notes.md`](Code_Review_Notes.md); its bugs are logged in `Known_Issues.md`
(open) / `Resolved_Issues.md` (closed).

## Next recommended ticket

**Nothing is blocked on a coder, and nothing is half-landed.** Every branch is merged, the working tree is clean, and CI is green on `main`. The next step is a **scoping pass on the rest of M21** — T0021.3 and T0021.4 are named in `Tickets.md` → T0021 but deliberately left unscoped, because the `get_job_details` allowlist the research plan filed under M21 already shipped early as T0019.10, so the milestone's remaining shape needs deciding rather than assuming.

**T0021.4 already has concrete inherited scope**, which makes it the natural next ticket: the user-facing half of the error-handling honesty audit that T0021.2 deliberately left open. Every streaming failure still reads to the user as "the demo is busy," whatever actually went wrong — tracked as `[MED · OPEN]` in [`Known_Issues.md`](Known_Issues.md) → Error-handling honesty audit. The code change is one conditional (`provider_busy` already exists); the work is deciding what the honest generic message should say.

After M21: **M22 v1.0 release cut** — DoD sweep, ToS posture applied, docs conformance, tag. Full gap analysis and the D1–D13 decision list: [`research/v1-release-readiness-plan.md`](../research/v1-release-readiness-plan.md).

### Maintainer-gated — the only things actually pending

- **Branch protection on `main`** (T0020.3). The CI gate runs but does not *enforce*: a red check does not block a merge until protection is enabled (GitHub → Settings → Branches, or `gh api`). Verify end-to-end afterwards — a red PR is blocked, a green PR merges, and the run shows `19 deselected` confirming eval tests were not attempted.
- **Nightly ingestion cron activation** (T0020.4). Follow [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md), not this file. **D5** (local Docker-Postgres portion) and **D6** (Neon migrated to head) are both **signed off**. Remaining: **D2** (robots/ToS ratification in a tracked doc), the **secrets** (`DATABASE_URL` direct/non-pooled host + `HEALTHCHECKS_URL` — neither has ever been set), a **manual `workflow_dispatch` green**, then **re-arm `schedule:`** (uncomment, last step), the **first scheduled run**, and **D10** (v1.0 live-vs-parked decision).
  - **Setting `DATABASE_URL` is the irreversible step** — it is what turns a harmlessly-failing job into one that really scrapes and really writes production. Arm `schedule:` only *after* a green manual run; arming first is what produced the 19-night silent failure.
  - **Known first-run effect:** every Neon row carries `last_seen_at = 2026-07-01`, well past `expire_after_days: 7`, so `expire_stale_clean_jobs` will flip all 50 rows to `is_active = false` unless re-seen. Verified not to break the demo — neither `query_clean_jobs` nor `get_job_details` filters on `is_active`.
- **Rotate the `neondb_owner` password** — it was exposed in a chat transcript during the D6 run — and update `DATABASE_URL` in Render afterwards.
- **Render Blueprint sync** (T0020.2). The deploy repoint is done and verified live. Before any Blueprint sync, confirm `render.yaml`'s `name:` matches the existing service — a mismatch mints a second Free service and erodes the 750 instance-hour margin. Also still unconfirmed: that a no-op push to `main` triggers a redeploy.

### Outstanding manual verification (carried)
Three tickets shipped with live-DB checks unrun because Docker Desktop was down; all are listed in [`Manual_Verification_Guide.md`](Manual_Verification_Guide.md). Bringing the local stack up for the cron work is the natural moment to clear them in one session.
