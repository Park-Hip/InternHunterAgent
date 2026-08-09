## Current branch

> **⚠ Reality check (2026-08-09).** Three claims in this file were verified against GitHub/Render and found
> false. Read this box before trusting anything below.
>
> 1. **The nightly ingestion cron was NOT dormant.** It self-activated when PR #29 landed
>    `.github/workflows/ingestion.yml` on `main` (2026-07-22) — GitHub fires `schedule:` from the default
>    branch automatically — and ran **19 consecutive failing nightly runs** through 2026-08-09, each dying in
>    ~15 s with `ConfigLoadError: DATABASE_URL: String should have at least 1 character` (the secret was never
>    set). It failed at config load, before any network or DB call, so nothing was scraped and Neon was never
>    written — but **D2 and D6 were open the whole time**. **Fixed:** `schedule:` is commented out on `main`
>    (PR #33, merged 2026-08-09 as `abe84d8`); `workflow_dispatch` is now the sole trigger and no scheduled
>    run has fired since. Every "dormant / not activated / activation is a maintainer action" phrase below is
>    **wrong as written** and is corrected in
>    [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md).
> 2. **The T0020.3 CI merge gate does not exist on GitHub.** `ci.yml` lives only on the unmerged
>    `feature/t0020.3-ci-merge-gate` branch (PR #32). `git ls-tree main .github/` shows only `ingestion.yml`;
>    `gh run list --workflow=ci.yml` returns HTTP 404. **No open PR has ever been linted or tested by it.**
> 3. **The T0021 track has begun**, contrary to "Next recommended ticket" below: PR #30 (T0021.1) is open,
>    and the `IHA-t0021.2` worktree holds 8 uncommitted files.
>
> Verified **true**: `main` = `bcc81db`; Render deploys from `main` (live `index.html` is byte-identical to
> `main`'s, and differs from `feature/t0018.4-deploy`'s), so the T0019.8/.10 serving fixes **are** live.

`feature/t0020.4-cron-activation` — **T0020.4 cron-activation runbook + T0020 milestone authoring (docs-only, 2026-07-26).** Cut from `feature/t0020.3-ci-merge-gate`. Committed [`docs/T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md) and authored the `## T0020` milestone + sub-ticket blocks in `Tickets.md`. **This branch is not pushed and has no PR.** Prior ticket — **T0020.3 CI merge gate on `main` (GitHub Actions, 2026-07-22).** Cut from `feature/t0020.2-render-main-deploy`. Adds `.github/workflows/ci.yml`: on every PR targeting `main` it runs `uv run ruff check .` + `uv run mypy` + `uv run pytest -q` (SHA-pinned `actions/checkout@9c091bb` + `astral-sh/setup-uv@11f9893` matching `ingestion.yml`, `permissions: contents: read`, `concurrency` with `cancel-in-progress`, `timeout-minutes: 15`, four dummy env vars that only satisfy `Settings` load-time validation — the standard suite mocks DB + LLMs, and eval tests are auto-deselected by `pyproject` addopts so the gate adds no `-m` flag). To make the gate genuinely green, the two pre-existing mypy `[arg-type]` errors were baselined with **targeted** `# type: ignore[arg-type]` at `src/core/checkpointer.py:25` and `src/agents/runtime/middleware.py:48` (narrow, not blanket — a new error of any other type on those lines still fails); both are third-party stub/generic mismatches, real fix deferred and logged in `Known_Issues.md`. Only those 2 comment-only lines of code changed. **Branch protection to *enforce* the gate is a pending maintainer action** (a coder session can't enable a repo-admin setting) — logged in `Known_Issues.md`. Prior ticket — **T0020.2 Render deploy source → `main` + tracked `render.yaml` (infra-config + docs, 2026-07-22).** Cut from `feature/t0020.1-main-reconciliation`. Adds a tracked `render.yaml` blueprint at the repo root that pins the `InternHunterAgent` web service to `main` with the recorded runtime settings (Docker `./docker/Dockerfile`, context `.`, Singapore, Free, `WEB_CONCURRENCY=1`, `PORT=8000`, health `/api/v1/health`, `autoDeploy: true`); all five secrets declared `sync: false` (no values). The **repo now pins `main`**, and the maintainer **completed the dashboard repoint** `feature/t0018.4-deploy` → `main` (2026-07-22) — the redeploy off `main` succeeded, so the live path now serves the T0019.8/.10 fixes. A live-surface spot-check (T0019.10 UI behaviors) and the separate Blueprint-sync decision remain — see `Known_Issues.md`. No app/config/Dockerfile change. Prior ticket — **T0020.1 `main` reconciliation follow-through (docs + local ref, 2026-07-22):** `main` is now the reconciled head at `bcc81db` (PR #29 — the T0020.1 reconciliation merge of the T0019.10 chain), carrying the full T0019.6/.8/.9/.10 chain plus the M13/M15 doc rescues. That ticket fast-forwarded the local ref to `origin/main` (`bcc81db`) and corrected the docs that still described the pre-merge "stuck at T0009 / ec0b25a" world; no code, config, or history change. Prior ticket chain (now landed on `main` via PR #29): `feature/t0019.10-job-details-allowlist` — **T0019.10 `get_job_details` explicit column allowlist (2026-07-21).** `fetch_job_details` no longer runs `SELECT *`; it names the 16 columns of the `prompts.schema_context` frozen contract explicitly, closing a six-column leak (`is_active`, `first_seen_at`, `last_seen_at`, `posted_date`, `source`, `external_id`) that reached the agent verbatim through `_build_answer`'s `row.items()`. Cut from `feature/t0019.9-ingestion-coverage` — **T0019.9 Ingestion coverage: raised `max_jobs` + round-robin query interleave (2026-07-20).** Cut from `feature/t0019.8-truthful-refresh-date` — **T0019.8 Truthful refresh date on `/ready` (2026-07-20).** Previously `feature/t0019.7-keepalive-verification` — **T0019.7 Windowed keep-alive ping + Neon idle-pool verification (doc-only, independent of T0019.2–.6).** Cut from `feature/t0019.6-nightly-cron` (`bb75d10`), which sits at the same commit as `feature/t0019.5-unattended-safety`'s post-merge state at the time of cutting. Branched off `feature/t0019.4-source-resilience`, which was branched off `feature/t0019.3-accumulate-lifecycle`, which was branched off `feature/t0019.2-alembic-baseline`, which was branched off `feature/t0019.1-robots-tos-gate`, which was branched off `feature/t0018.4-deploy` (the branch Render deployed from at T0018.4; T0020.2 repointed the deploy source to `main`, now pinned by the tracked `render.yaml`; the maintainer completed the dashboard repoint 2026-07-22) — **LIVE: https://internhunteragent.onrender.com** (verified end-to-end 2026-07-16). **Correction (2026-07-19):** the long-standing note that `main` is "stale at T0009" is **no longer true** — `main` carries PRs #20–#27 (T0010.4, T0010.7, T0011.6, T0016.4, and T0017.1/T0017.2 via the `-recovered` branches) and sits at `e3e65ae`. `feature/t0019.5-unattended-safety` merged `origin/main` (`83fbe15`) to close that divergence; the merge was content-neutral (resulting tree byte-identical to `bb75d10`) because every `main` change was already present here — the `-recovered` T0017 commits reproduced byte-identical code. **Superseded (2026-07-22, T0020.1):** that divergence is fully closed — `main` was reconciled to `bcc81db` via PR #29 and is now the true head, so the "sits at `e3e65ae`" / "branch off `main` after this PR lands" notes above are historical; the current head is `bcc81db`.

**Note on `.github/workflows/ingestion.yml` (T0019.6):** the workflow is now **present on this branch**. T0019.6's recovery commit (`ad1c269`, originally on `feature/t0019.6-nightly-cron-finish`) was cherry-picked here on 2026-07-22 during a branch-consolidation pass, so the T0019 chain no longer forks across two tips. Cherry-picked rather than left isolated because GitHub only fires `schedule:` from the **default branch** — the cron is structurally incapable of running from a feature branch, so consolidating carries no activation risk, while the doc-conflict cost of keeping it separate grew with every ticket landed. ~~**The D2/D5 maintainer gates are unchanged and still bind before `main`.**~~ **They did not bind (corrected 2026-08-09):** nothing enforced them, and the PR #29 merge fired the cron with D2 and D6 unsigned. The reasoning about feature branches was sound; the unstated corollary — that reaching `main` *is* activation — was missed. See `Tickets.md` → T0019.6 and the Reality check at the top of this file.

**Branch consolidation (2026-07-22):** the T0019.10 branch merged `origin/main` (`ec0b25a`, the PR #28 merge of T0019.5) — a content-neutral merge, since that work was already present via `bb75d10`. That branch then merged to `main` as PR #29. `origin/main` is now `bcc81db` (PR #29 — the T0020.1 reconciliation merge of the T0019.10 chain), superseding the earlier `ec0b25a` / `e3e65ae` positions referenced elsewhere in this file.

Built clean off `e4076b2` (the kept ReAct/SQL-generation config split) with the T0018.3 Editorial UI committed as `7d4cfef`, then deployed: API on **Render** (Docker, Singapore, Free), Postgres on **Neon** (PG17, static 50-row snapshot), tracing on **Langfuse Cloud Hobby (JP)**. Secrets are Render env vars; `api.cors.allowed_origins` stays `[]` (same-origin). Full record in [`Completion_Reports.md`](Completion_Reports.md) → T0018.4, and the confirmed topology in `research/deployment-research-plan.md` §12. The dumped T0015.6/.7 provider-A/B phase is parked recoverably at tag **`archive/t0015.6-provider-ab`** (`45d333c`) — **deliberately not revived**: provider/reasoning A/B is out of scope for v1 (maintainer decision, 2026-07-22).

- Do not rebase this branch onto `main` without an explicit maintainer decision. `main` historically lagged the M12/M13/T0016 work — resolved 2026-07-19 by the `origin/main` merge above, which is a merge, not a rebase; the ticket-branch topology recorded here and in `Tickets.md` is unchanged.
- **M15 behavior track — partially reclaimed 2026-07-22.** Two artifacts were restored onto this branch from tag `archive/t0015.4-scenario-matrix` (`eba3e1f`): `docs/Agent_Behavior_Spec.md` (the T0015.2 spec of record) and `evals/v1_scenario_matrix.md` (the 29-scenario graded run, 13 pass / 16 fail). They were rescued because `research/honesty-enforcement-design.md` — a live design record in this branch — cites both as its evidence base, and deleting the branch would have made them unreachable. **The scenario harness was not restored** (`scripts/run_scenario_matrix.py`, `evals/scenarios_v1.yaml`, `evals/test_scenarios_v1_load.py`, `v1_scenario_matrix.observed.json`) — it stays on the tag only; re-measurement means recovering it first. **`behavior_glossary` still does not exist** in `config/prompts.yaml` — but it is **complete and recoverable** at tag `archive/t0015.2-behavior-glossary` (18 canonical strings, frozen 2026-07-11). Landing it is owned follow-up work, deliberately kept out of the cleanup pass because it changes agent output; see `Known_Issues.md` → Repo state & version control.

### Branch topology after the 2026-07-22 prune

The repo went from **55 local branches, 2 worktrees and 1 stash** to **2 branches, 1 worktree, no stash**. Only `feature/t0019.10-job-details-allowlist` and `main` remained after the prune. Everything else was either merged into that branch, content-verified as superseded, or preserved by an archive tag.

**Reconciliation (2026-07-22, T0020.1):** `feature/t0019.10-job-details-allowlist` was merged to `main` as **PR #29**, and the local `main` ref was fast-forwarded to `origin/main`. **`origin/main` = `bcc81db`** is now the true head, carrying the full **T0019.6/.8/.9/.10** chain plus the **M13/M15 doc rescues**. The active working branch is now **`feature/t0020.2-render-main-deploy`** (the T0020.2 `render.yaml` + deploy-doc pass, cut from `feature/t0020.1-main-reconciliation`). **T0020.2 (2026-07-22):** the repo now pins the deploy source to `main` via a tracked `render.yaml`, and the maintainer **completed the live dashboard repoint** `feature/t0018.4-deploy` → `main` (redeploy off `main` succeeded). A live-surface spot-check and the Blueprint-sync decision remain — see `Known_Issues.md`.

**Archive tags — cite these, not branch names.** The branches they replaced no longer exist:

| Tag | Commit | What it preserves |
|---|---|---|
| `archive/t0015.2-behavior-glossary` | `62f2089` | The **complete 18-string `behavior_glossary`** frozen by T0015.2 but never landed into `config/prompts.yaml`. Recover with `git show archive/t0015.2-behavior-glossary:config/prompts.yaml`. |
| `archive/t0015.4-scenario-matrix` | `eba3e1f` | The 29-scenario graded matrix **plus the harness that produced it** (`run_scenario_matrix.py`, `scenarios_v1.yaml`, the observed JSON) — needed for any re-measurement. |
| `archive/t0015.6-provider-ab` | `45d333c` | The provider/reasoning A/B phase. **Deliberately not revived** — A/B is out of scope for v1. Also holds `src/core/event_loop.py`, a Windows `SelectorEventLoop` factory for uvicorn that is not in the tree. |
| `archive/stash-t0019.6-docs` | `b7a291e` | The former `stash@{0}`. Its `Schema_Contract.md` fix is now landed (with two corrections); the tag preserves the original and the other nine files verbatim. |

**Deleted without a tag, because their content is demonstrably in this branch:** the 45 branches already merged into HEAD; `feature/t0019.5-unattended-safety` (contained in HEAD, refused `-d` only for being ahead of its remote); `docs/rename-t0013-schema-freeze` (applied as `284430c`); `feature/t0018.1-go-live-glue-recovered` (its only unique lines were stale review notes calling CORS/rate-limiting/`/docs` unimplemented — T0016 has since implemented all of it); `feature/t0019.6-nightly-cron-finish` (cherry-picked as `8f8406f`, workflow byte-identical).

**Remote branches were NOT pruned** — 30 still exist on `origin`, 19 of them merged into `origin/main`. Deleting them affects any other clone and needs its own explicit decision.
- Everything for this branch's current work is in [`Tickets.md`](Tickets.md) → **T0018.4** and the T0018.4 manual checklist in [`Manual_Verification_Guide.md`](Manual_Verification_Guide.md).
- Older branch/roadmap snapshots (T0014 and earlier) are archived in [`archive/Repo_State_History.md`](archive/Repo_State_History.md).

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
- **M13** (T0013.1–.5) — Schema Enrichment & v1 Freeze: `tech_stack` rebuilt against an external vocabulary (audit coverage 58% → 89%); `job_level`, `listing_expires_on`, and `created_on` exposed to the agent; the enriched **16-column** v1 contract recorded in [`Schema_Contract.md`](Schema_Contract.md) and enforced by prompt-freeze guards. **This is this branch's base (`51913f6`).**
- **M16** (T0016.1–.4) — Public-endpoint hardening: credential-less CORS, per-IP rate limit + friendly busy path, request length cap, explicit `/docs` exposure decision.
- **M17** (T0017.1–.2) — Streaming response delivery: runtime `astream` + no-leak filter, streaming service + `POST /api/v1/agent/chat/stream` SSE endpoint.
- **M19** (T0019.1–.10) — Ingestion deploy readiness: robots/ToS gate, Alembic baseline + lifecycle columns, accumulate/upsert semantics, source resilience + retry, unattended-run safety, nightly cron (**believed** dormant/human-gated — in fact auto-activated on the PR #29 merge; see the Reality check at the top), keep-alive runbook, truthful `/ready` refresh date, ingestion coverage cap+interleave, `get_job_details` column allowlist. Landed on `main` via PR #29.
- **M20** (T0020.1) — `main` reconciliation follow-through (docs + local ref): after PR #29 merged the T0019.10 chain to `main` (`bcc81db`), fast-forwarded the local `main` ref and corrected every doc/memory claim that still described the pre-merge "stuck at T0009 / `ec0b25a`" world. No code, config, or history change. Downstream T0020.2 (Render→`main`), T0020.3 (CI gate), T0020.4 (cron activation) remain sequenced after.
- **M21** (T0020.3) — CI merge gate on `main` **(written, not landed — PR #32 still open as of 2026-08-09, so the gate is not running)**: `.github/workflows/ci.yml` runs `ruff` + `mypy` + `pytest -q` on every PR targeting `main` (SHA-pinned actions mirroring `ingestion.yml`, least-privilege `contents: read`, dummy env vars, eval tests auto-deselected). Baselined the 2 pre-existing mypy `[arg-type]` errors with targeted `# type: ignore` so the gate is genuinely green (real fix deferred). Only 2 comment-only code lines changed. Branch protection to enforce the gate is a pending maintainer action. Downstream T0020.4 (cron activation) remains.

## In progress / next
**Nothing in progress — T0018 closed 2026-07-16 with the first public deploy.** This branch carries the full T0016 → T0018 stack (security posture → streaming → clickable demo), plus the SQL-generation reasoning-effort hotfix and the ReAct/SQL-generation config split, and it is deployed:

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
- **T0018.4 - Deploy topology + first public deploy:** API on **Render** (Docker, Singapore, Free, `WEB_CONCURRENCY=1`, health check `/api/v1/health`), Postgres on **Neon** (PG17, static 50-row snapshot), tracing on **Langfuse Cloud Hobby (JP)**; secrets are Render env vars, `api.cors.allowed_origins` stays `[]` (same-origin). Auto-deploy on push to this branch. **$0/mo** against a $10 ceiling. No app-code change was needed. **Live: https://internhunteragent.onrender.com**, verified end-to-end 2026-07-16.

- **T0019.1 - robots.txt / ToS gate (doc-only, no code):** resolved the `deployment-research-plan.md` §11 hard gate. **`ms.vietnamworks.com` serves no robots.txt at all (HTTP 404)**; `www.vietnamworks.com/robots.txt` permits the relevant paths with no `Crawl-delay`; the ToS contains **no** automated-access/scraping clause. **Recommended verdict: favorable — pending maintainer confirmation**, so **T0019.6 stays blocked until the maintainer signs off** (then on T0019.2–.5). Evidence archived under `research/experiments/` (both robots fetches + a ToS excerpt with verbatim Vietnamese and labeled translations); decision record in `research/deployment-research-plan.md` §11. One caveat registered in `Known_Issues.md`: ToS §7 restricts *republishing* content — a live question for the public demo, but not a cron blocker, since the deployed snapshot already raises it today.

- **T0019.2 - Alembic adoption: baseline migration + env wiring:** replaced `scripts/reset_db.sql` (DROP + recreate) as the de-facto migration strategy — that stops working once T0019.3 makes `raw_jobs` accumulate irreplaceable postings. Added `alembic` (`pyproject.toml`), scaffolding (`alembic.ini`, `alembic/env.py` reading `ALEMBIC_DATABASE_URL` → falls back to `settings.DATABASE_URL`, `target_metadata = Base.metadata`), and one hand-written baseline migration (`alembic/versions/f3a1c9d2e7b4_baseline_schema.py`, `down_revision = None`) reproducing the exact schema in `scripts/init_db.sql`. Aligned `RawJob.id`/`CleanJob.id` in `models.py` to `Identity(always=True)` (metadata-only fix — the DB already used `GENERATED ALWAYS AS IDENTITY`; the ORM metadata previously disagreed). `scripts/reset_db.sql` demoted to a local-dev-only header comment; `scripts/init_db.sql` untouched (the eval fixture loader still depends on it). New opt-in `tests/migrations/test_baseline_roundtrip.py` (skips without `SCRATCH_DATABASE_URL`). Verified: empty-DB `alembic upgrade head` builds the full 19-column `clean_jobs` schema correctly; the round-trip test passes against a scratch DB; `alembic stamp head` + `alembic upgrade head` is a clean no-op against the real local DB (row count unchanged at 50); the app boots and answers a live query against the migrated schema — verified via the Dockerized (Linux) `api` service, since native Windows `uv run uvicorn` hangs on a pre-existing, ticket-unrelated `ProactorEventLoop`/async-psycopg incompatibility (`Known_Issues.md`).

- **T0019.3 - Accumulate load semantics + hidden lifecycle columns:** dropped the `TRUNCATE` in `clean_store.py` — the already-written `ON CONFLICT (source, external_id) DO UPDATE` upsert (renamed `replace_clean_jobs` → `upsert_clean_jobs`) is now live code, so `raw_jobs`/`clean_jobs` accumulate across runs instead of being rebuilt each time. Added three hidden bookkeeping columns to `clean_jobs` — `is_active boolean not null default true`, `first_seen_at`/`last_seen_at timestamptz not null default now()` — via `alembic/versions/b7e2f4a91c3d_lifecycle_columns.py` (`down_revision = f3a1c9d2e7b4`), with a backfill from `raw_jobs.fetched_at` (confirmed the join was total: 0 orphaned `clean_jobs` rows on the 50-row local snapshot, so no row was left defaulted to migration-run time). The upsert now refreshes `last_seen_at = now()` and flips `is_active = true` on every conflict, and never touches `first_seen_at` (insert-only). New `expire_stale_clean_jobs(expire_after_days)` in `clean_store.py` runs a single time-based `UPDATE ... SET is_active = false WHERE last_seen_at < now() - make_interval(days => :days)` — never `DELETE`, never "not seen this run." `loader.py::run_ingestion` calls it after the upsert using `config/ingestion.yaml`'s new `lifecycle.expire_after_days: 7`, and the run summary gained `expired_count`. All three columns stay off the agent-visible surface — no `NormalizedJob`, `Schema_Contract.md`, or `config/prompts.yaml` change; the hidden-column guard in `tests/agents/runtime/test_prompts.py` was extended to assert `is_active`/`first_seen_at`/`last_seen_at` never appear in `schema_context`. `scripts/init_db.sql` was deliberately left untouched (now diverges from the Alembic head — logged in `Known_Issues.md`). Verified live against the local Docker DB: empty-DB `alembic upgrade head` builds the full 22-column schema; `alembic downgrade -1` cleanly drops the three columns; upgrading the real local DB preserved all 50 rows with a true backfill (0 rows at "now"); a synthetic row proved two upserts keep `is_active=true`/refresh `last_seen_at`/preserve `first_seen_at`, an 8-day-aged row flips to `is_active=false` under a 7-day window without being deleted, and re-seeding it flips `is_active` back to `true`; the Dockerized `api` service answered a live chat query ("13 AI Engineer jobs") with no mention of the hidden columns.

- **T0019.4 - Source resilience: per-page try/continue + retry/backoff:** `config/ingestion.yaml` gains `api.retry_attempts: 2` / `api.retry_backoff_seconds: 2.0`. `JobSource` (`sources/base.py`) gains a class-level `pages_failed: int = 0` counter. `VietnamWorksSource._post` stays an unchanged thin primitive; a new `_post_with_retry` wrapper retries transient failures (429, ≥500, timeouts, transport errors) with doubling backoff (2s, then 4s) and gives up immediately on permanent 4xx — on give-up it increments `pages_failed`, logs `ingestion.page_failed` (query + page + attempts + reason), and returns `None` without raising. `_collect` treats `None` as "skip this page" and a `try/finally` around the per-page body guarantees the politeness `time.sleep(self._delay)` still runs even when a page is skipped. `fetch()` resets `pages_failed = 0` at entry so a reused instance doesn't accumulate across runs. `loader.py::run_ingestion` reads `getattr(source, "pages_failed", 0)` after draining the generator and adds `"pages_failed"` to the summary dict — no other loader ordering changed. A single transient failure no longer discards an entire run's already-fetched pages.

- **T0019.5 - Unattended-run safety: pre-flight schema assertion, yield floor, dead-man ping:** new `src/services/ingestion/safety.py` with `IngestionSafetyError` and three functions. `assert_clean_jobs_schema()` queries live `information_schema.columns` for `clean_jobs` and compares against `{c.name for c in CleanJob.__table__.columns}` (derived from the ORM, never hand-maintained); on any mismatch it logs `ingestion.schema_drift` (missing + unexpected, both directions) and raises before any write — an absent table (empty column set) also raises, with its own message rather than listing all columns "missing." `assert_min_yield(fetched, min_yield)` raises `IngestionSafetyError` naming both numbers when `fetched < min_yield`, logging `ingestion.yield_floor_breached` first. `send_dead_man_ping(url)` POSTs to a healthchecks.io URL via `httpx`; `None`/empty logs `ingestion.ping_skipped` and returns `False` (the normal local path, not an error); any `httpx.HTTPError` or non-2xx logs `ingestion.ping_failed` as a warning and returns `False` without raising — a ping failure never fails the run. `config/ingestion.yaml` gains `safety.min_yield: 20`. `src/core/config.py` gains one optional field, `HEALTHCHECKS_URL: str | None = None`; documented (commented, optional) in `.env.example`. `loader.py::run_ingestion` now calls `assert_clean_jobs_schema()` first — before the source is constructed or anything fetched — then fetches, upserts raw (evidence preserved even on a bad run), calls `assert_min_yield(len(postings), settings.ingestion_yaml["safety"]["min_yield"])`, and only then normalizes/upserts clean/expires; a yield-floor abort happens before both the clean upsert and the expiry pass, so a skipped clean write can never have `expire_stale_clean_jobs` wrongly age out untouched rows. `run_ingestion` stays library code — it lets `IngestionSafetyError` propagate, no `sys.exit`. `main()` now owns the process contract: catches `IngestionSafetyError`, logs `ingestion.aborted`, exits 1; on the fully-green path it logs the existing `ingestion.completed` summary (unchanged: `fetched`/`raw_upserted`/`clean_loaded`/`skipped`/`expired_count`/`pages_failed`) and only then calls `send_dead_man_ping(settings.HEALTHCHECKS_URL)` — withholding the ping on any abort is the dead-man signal. All nine pre-existing `test_loader.py` tests were updated to patch the new `assert_clean_jobs_schema` and set `safety.min_yield: 0` in their mocked `ingestion_yaml` (no assertion weakened); three new loader tests cover schema-abort, yield-floor-abort, and the happy-path ordering/summary shape. New `tests/services/ingestion/test_safety.py` covers both schema-assertion mismatch directions, the empty-table case, both `assert_min_yield` branches, and all three `send_dead_man_ping` paths.

- **T0019.7 - Windowed keep-alive ping + Neon idle-pool verification (doc-only):** applies the cold-start mitigation decided 2026-07-16 but never executed — a windowed external ping of `GET /api/v1/health` to keep Render's free instance from spinning down. No code changed; this ticket produced an executable runbook (`Manual_Verification_Guide.md` → `### T0019.7`: cron-job.org setup steps, a 24-hour measurement template with the "expected if healthy" arithmetic worked out, and a pre-written, numerically-triggered decision rule), an updated `deployment-research-plan.md` §1a with an empty outcome-record slot for the maintainer to fill in after the 24 h observation, and updated `Known_Issues.md` entries reflecting that the ping is now documented-and-ready rather than merely decided. The open question the runbook exists to answer — whether the checkpointer's idle Postgres pool alone keeps Neon awake regardless of which endpoint is pinged — remains genuinely unmeasured; enabling the ping, taking readings, and applying the decision rule are maintainer actions, not yet executed.

- **T0019.8 - Truthful refresh date on `/ready`:** `/api/v1/ready` no longer reports a hand-maintained static date. `src/api/routes/health.py` splits the old `get_data_snapshot_date` into `_configured_snapshot_date()` (the static `api.demo.data_snapshot_date` fallback, with its defensive handling of a malformed `api.demo` block intact) and a data-derived `get_data_snapshot_date()` backed by a new `_select_max_last_seen()` running `SELECT MAX(last_seen_at)::date FROM clean_jobs` through the existing `session_factory`. The fallback fires on an empty table (`snapshot_date_empty_table_using_config_fallback`) or any query failure (`snapshot_date_query_failed_using_config_fallback`, logged with `exc_info`). `readiness_check` runs the date query via `asyncio.to_thread` **after** the `SELECT 1` probe, so a DB failure still short-circuits to 503 without attempting it. Response shape, field name, and the UI are unchanged — only the value's source moved; layer isolation holds (plain SQL against a table, no `src.services.ingestion` import). `tests/api/test_ready.py` carries 7 cases. Also corrected three untrue statements found in the working tree: `MVP_Technical_Design.md` §11.3 named `MAX(fetched_at)` (wrong table — `fetched_at` is on `raw_jobs`), the §7 banner claimed the T0019.1 ToS verdict was maintainer-confirmed (no committed doc records it), and the same banner claimed T0019.6 was built (its workflow is untracked).
- **T0019.9 - Ingestion coverage (raised cap + round-robin interleave):** the served corpus was both truncated and skewed. `config/ingestion.yaml`'s `max_jobs` moved `50 → 150` — a safety ceiling deliberately above the measured ~50–112 yield, not a target — and `VietnamWorksSource._collect` now iterates **page outer / query inner** (page 0 of every query, then page 1), so a cap truncates evenly across queries rather than exhausting the config list from the top and structurally starving `"MLOps"`, `"computer vision"`, `"deep learning"`. Both fixes were required; neither suffices alone. All T0019.4 invariants are preserved: `seen_ids` stays initialised once outside both loops (cross-query dedup), all three cap checks remain so the cap is still exact and global, `_is_ai_data` is unchanged, `time.sleep(self._delay)` still runs in the `finally` for every page attempt including skipped ones, and `_post_with_retry`'s None-means-skip semantics and `pages_failed` accounting are untouched. Request *count* is identical (`pages_per_query x queries` = 16, both unchanged); only order changes. `tests/services/ingestion/test_vietnamworks.py` gains `VietnamWorksCoverageTests` (6 cases), whose anti-skew case was **confirmed to fail** against the reverted query-outer loop before the interleave was restored. **No live API request was issued** — the ticket is gated on decision D8, so the re-measure it calls for is written as a runbook with empty result slots in `research/data-ingestion-stage.md` §11 and left for the maintainer.

- **T0019.6 - GitHub Actions nightly ingestion cron (recovered + committed):** lands `.github/workflows/ingestion.yml` — `schedule: '0 2 * * *'` (02:00 UTC / 09:00 ICT) + `workflow_dispatch`; `concurrency: {group: ingestion, cancel-in-progress: false}`; `timeout-minutes: 15`; `permissions: {contents: read}`; SHA-pinned `actions/checkout` + `astral-sh/setup-uv`; `uv sync --frozen --no-dev` then `uv run python -m src.services.ingestion.loader`. **Secrets block deviates from the ticket's original text** (maintainer decision, this session): `GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY` are set to the literal `"unused-by-ingestion"` rather than real GitHub secrets — `src/core/config.py`'s `Settings` requires them at import with no default, but ingestion is deterministic and reads none of their values (empirically verified — see `Manual_Verification_Guide.md` T0019.6 check B). Only `DATABASE_URL` and `HEALTHCHECKS_URL` come from `secrets.*`. The keepalive step (`gautamkrishnar/keepalive-workflow`) is deliberately omitted, not stubbed — the action's repo is 403'd by GitHub Staff for a ToS violation and cannot be SHA-pinned; risk logged in `Known_Issues.md`. Amends `Full_Design_Document.md` §2's "no schedulers" exclusion to scope it to the *serving path* only, naming this workflow as the one permitted out-of-band exception. **~~Committed, now on `main`, still dormant~~ — WRONG, corrected 2026-08-09.** GitHub only fires `schedule:` from the default branch — but that means landing on the default branch **activates** it. The T0019 chain merged to `main` via **PR #29 (`bcc81db`, 2026-07-22 — the T0020.1 reconciliation)**, and **the cron started firing that same day**. It was never dormant on `main`, and activation was never "a maintainer action gated on D2/D5" — it happened automatically with **D2 and D6 unsigned**. All 19 nightly runs (2026-07-22 → 2026-08-09) failed at config load for want of a `DATABASE_URL` secret, so no scrape or production write occurred. `schedule:` is now commented out on `main` (**PR #33**), making the workflow genuinely dormant and restoring the gated-activation story this paragraph originally asserted. Both release gates the spec named — **T0019.9** and **T0019.10** — have landed. No file under `src/`, `tests/`, or `config/` was touched.

**Status (2026-07-22):** T0016.1–T0016.4, T0017.1–T0017.2, **T0018.1–T0018.4**, the SQL-generation reasoning-effort hotfix, and the ReAct/SQL-generation config split are complete on this stack; **T0019.1** is complete pending the maintainer's verdict confirmation (D2); **T0019.2**–**T0019.5** are complete; **T0019.6** is **committed and now consolidated onto this branch** (cherry-picked `ad1c269`, 2026-07-22) — the workflow is dormant by construction until the chain merges to `main`, and remains release-gated on T0019.9 (done) and T0019.10 (done); **T0019.7** (doc-only) is complete — the ping itself is not yet enabled, that's a maintainer action; **T0019.8** is complete (code + docs; live-DB manual checks outstanding — see Build/test status); **T0019.9** is complete in code, config and tests, but its `[MED]` `Known_Issues` entry stays open as **PARTIALLY RESOLVED**: confirming the new `max_jobs: 150` actually clears the API's current ceiling needs a live re-measure, which decision **D8** blocks — runbook with empty result slots at `research/data-ingestion-stage.md` §11. **T0019.10** is code-complete (committed `62654eb`), with live-DB manual checks C–E still pending Docker. Open issues live in [`Known_Issues.md`](Known_Issues.md); resolved/background items in [`Resolved_Issues.md`](Resolved_Issues.md).

**Milestone map (see `Tickets.md`):** T0013 freeze → T0016 security posture → T0017 streaming response delivery → T0018 clickable demo UI + go-live ✅ → **T0019 ingestion deploy readiness (live-DB) ✅ landed on `main` via PR #29** (T0019.1 ✅, T0019.2 ✅, T0019.3 ✅, T0019.4 ✅, T0019.5 ✅, T0019.6 ✅ committed/dormant/human-gated, T0019.7 ✅ doc-only, T0019.8 ✅, T0019.9 ✅ code-complete/re-measure gated on D8, T0019.10 ✅ code-complete/live-DB checks C–E pending Docker) → **T0020 reconciliation & activation ◀ T0020.1 ✅ (`main` = `bcc81db`); T0020.2/.3/.4 sequenced**.

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
Current-branch (T0019.10 + the cherry-picked T0019.6) results below; earlier per-ticket logs (T0011–T0018.3, incl. the ReAct/SQL-generation config split) are archived in [`archive/Repo_State_History.md`](archive/Repo_State_History.md).

- `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ingestion.yml')); print('YAML OK')"` (T0019.6) → `YAML OK`.
- `git status --short` (T0019.6, before commit) → only the files this ticket touched (`docs/**`, `research/**`) plus the previously-untracked `.github/` now staged; no `src/`/`tests/`/`config/` changes.
- `uv run pytest -q` (T0019.6, full standard suite) → `328 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~8567s — **identical to T0019.9's baseline**, exactly as expected since no `src`/`tests` file was touched by this ticket.
- `uv run ruff check .` (T0019.6, whole repo) → all checks passed.
- `uv run mypy` (T0019.6, whole repo) → the same 2 pre-existing, unrelated errors (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`). No third error introduced.
- `grep -n "secrets\." .github/workflows/ingestion.yml` → exactly 2 lines (`DATABASE_URL`, `HEALTHCHECKS_URL`); no real Groq or Langfuse secret referenced.
- `grep -n "No autonomous or background execution" docs/Full_Design_Document.md` → no match (the amended line replaces it); `sed -n '20,30p'` confirms the amended §2 bullet + T0019.6 note is present.
- **Manual check B (empirical secrets-required test) was run this session, not just carried from the stash:** with `.env` moved aside, unsetting each of `GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY` in turn against `uv run python -m src.services.ingestion.loader` failed fast with `ConfigLoadError` and `exit=1` before any DB connection, for all three. `.env` restored immediately after. Full transcript in the T0019.6 completion report.
- **Checks C, D, E were not run** — they require GitHub Actions secrets configured on the repo and/or the T0019 chain merged to `main`, both maintainer-gated actions outside this ticket's scope. Not fabricated; see `Manual_Verification_Guide.md` → T0019.6.
- `git stash list` → `b7a291e`, the recovered T0019.6 stash, remains present and was not dropped. (The separate T0019.10 WIP stash referenced in the original T0019.6 report was restored and committed as `62654eb`; only `b7a291e` is left.)

- `uv run pytest` (T0019.10, full standard suite) → `329 passed, 8 skipped, 19 deselected` in 526.10s. **+1 over T0019.9's 328**, exactly the one net-new guard case. No pre-existing test was modified, weakened or removed — all 6 prior cases in `test_job_details.py` pass unchanged.
- `uv run pytest tests/services/query/test_job_details.py -v` (T0019.10, targeted) → `7 passed` in 0.53s.
- **Discriminating-test evidence (T0019.10):** two deliberate regressions were run against `test_selects_exactly_the_schema_context_column_contract`. (1) Reverting to `SELECT *` fails it — but naming the **missing** contract columns, since the parsed token set becomes `{'*'}` and the forbidden-column assertions are never reached; the `*` assertion is what trips. (2) Keeping the allowlist and appending `, is_active, source, external_id, posted_date` fails with `Items in the first set but not the second: 'posted_date', 'is_active', 'external_id', 'source'` — naming all four leaks, and confirming whole-token matching (`source` flagged while allowlisted `source_url` is not; `external_id` while `id` is not). Scenario 2 is the one that exercises the leak assertions; scenario 1 alone would overstate coverage. The allowlist was restored and green re-confirmed.
- `uv run ruff check .` (T0019.10, whole repo) → all checks passed.
- `uv run mypy` (T0019.10, whole repo) → the same 2 pre-existing, unrelated errors (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`). No third error introduced.
- `uv run pytest -q` (T0019.9, full standard suite) → `328 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~526s. **+6 over T0019.8's 322**, exactly accounting for the six net-new `VietnamWorksCoverageTests` cases. No pre-existing test was modified, weakened, or removed — all 21 prior cases in `test_vietnamworks.py` pass unchanged, including `test_max_jobs_cap_is_honoured`.
- `uv run pytest tests/services/ingestion/test_vietnamworks.py -q` (T0019.9, targeted) → `27 passed` in 0.39s.
- **Discriminating-test evidence (T0019.9):** with `_collect`'s loops temporarily reverted to query-outer, the same file gives `2 failed, 25 passed` — `test_cap_truncates_evenly_across_queries_not_alphabetically` fails with `q6`/`q7`/`q8` missing from the covered set, and `test_request_order_is_page_major` fails with the interleaved `[0,1,0,1,...]` order. The interleave was restored and the suite re-confirmed green.
- `uv run ruff check .` (T0019.9, whole repo) → all checks passed.
- `uv run mypy` (T0019.9, whole repo) → the same 2 pre-existing, unrelated errors (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`). No third error introduced.
- **Manual verification (T0019.9): checks A–C run and passing, D skipped, E confirmed.** Check C's per-query distribution over 8 queries with `max_jobs = 20` printed `4,4,2,2,2,2,2,2` — **all 8 queries represented, exactly 20 postings** (the old loop would print `4,4,4,4,4,0,0,0`). Check D (local Docker pipeline) was **skipped**: it could not be done without either a live fetch or scaffolding beyond the ticket's scope, and the D8 gate outranks the check. **No live request was issued to `ms.vietnamworks.com` at any point.**
- `uv run pytest -q` (T0019.8, full standard suite) → `322 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~525s. **+3 over the 319 baseline**, exactly accounting for the three net-new `tests/api/test_ready.py` cases (the file goes 4 → 7). No pre-existing test was modified or weakened. The 8 skips are all DB-dependent (no local Docker Postgres this session) plus `tests/migrations/test_baseline_roundtrip.py`, which needs `SCRATCH_DATABASE_URL`.
- `uv run pytest tests/api/test_ready.py -v` (T0019.8, targeted) → `7 passed` in 1.88s — MAX-present, empty-table fallback, query-raises fallback, 503 short-circuit with `assert_not_called()` on the date query, and the not-rate-limited guarantee.
- `uv run ruff check .` (T0019.8, whole repo) → all checks passed.
- `uv run mypy` (T0019.8, whole repo) → the same 2 pre-existing, unrelated errors (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48` — logged in `Known_Issues.md`). No third error introduced; `src/api/routes/health.py` is clean.
- **⚠ Manual verification NOT run (T0019.8).** Docker Desktop was not running this session (`docker ps` → `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`), so none of checks A–E in the new `Manual_Verification_Guide.md` T0019.8 entry were executed. The automated tests patch `_select_max_last_seen` and feed it a `datetime.date`, so they prove the fallback logic but **cannot** prove that Postgres's `::date` cast arrives as a `datetime.date` through psycopg3, nor that the real value wins over the fallback against a populated table. **Check B is outstanding** — this is the same class of gap as T0019.5's unrun checks B–E, and is recorded rather than glossed.

Earlier T0019.7 and T0019.5 results follow.

- `uv run pytest -q` (T0019.7, full standard suite — no code changed, confirmed unaffected) → `319 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~266s, identical to the pre-ticket baseline.
- `uv run ruff check .` (T0019.7, whole repo) → all checks passed.
- `uv run mypy` (T0019.7, whole repo) → the same 2 pre-existing, unrelated errors (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48` — logged in `Known_Issues.md`).
- Live check: `curl -s -o /dev/null -w "%{http_code}\n" https://internhunteragent.onrender.com/api/v1/health` → `200`, confirming the T0019.7 runbook's ping target is reachable and correct.

- `uv run pytest -q` (T0019.5, full standard suite, DB-dependent tests skip without Docker up) → `319 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~268s. No pre-existing test's assertions were weakened — the 9 pre-existing `test_loader.py` tests now patch `assert_clean_jobs_schema` and carry `safety.min_yield: 0` in their mocked config.
- `uv run pytest tests/services/ingestion/test_safety.py tests/services/ingestion/test_loader.py -q` (T0019.5, targeted) → `23 passed` in <1s.
- `uv run ruff check .` (T0019.5, whole repo) → all checks passed.
- `uv run mypy` (T0019.5, whole repo) → 2 pre-existing errors, both unrelated to this ticket (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48` — logged in `Known_Issues.md`); the three touched files (`safety.py`, `loader.py`, `src/core/config.py`) are clean.
- Manual verification against a live local Docker DB (checks B–E of the T0019.5 checklist) was not run in this session — no local Docker Postgres was up. Flagged as a risk below; the checklist is appended to `Manual_Verification_Guide.md` for the next person with the stack running.

- `uv run pytest -q` (T0019.4, full standard suite) → `311 passed, 1 skipped, 19 deselected, 4 subtests passed` in ~5s. The 1 skip is `tests/migrations/test_baseline_roundtrip.py`, which needs `SCRATCH_DATABASE_URL`. No pre-existing test was modified.
- `uv run ruff check .` (T0019.4, whole repo) → all checks passed.
- `uv run mypy` (T0019.4, whole repo) → 2 pre-existing errors, both unrelated to this ticket (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48` — logged in `Known_Issues.md`).
- Manual: a mock-client script driving `VietnamWorksSource` with one page failing 500 three times then a later page succeeding showed `pages_failed == 1`, surviving postings present, and an `ingestion.page_failed` JSON warning on stderr with the query/page/attempts/reason; `run_ingestion` against a stub source with `pages_failed = 2` returned that value in the summary dict alongside `fetched`/`raw_upserted`/`clean_loaded`/`skipped`/`expired_count`.
- `uv run pytest tests/services/ingestion/test_vietnamworks.py -v` (T0019.4, new `VietnamWorksResilienceTests`) → 7 new tests, all passing, in well under a second (confirms `time.sleep` is patched, not really waiting through backoff).

- `uv run pytest -q` (T0019.3, full standard suite) → `303 passed, 1 skipped, 19 deselected, 4 subtests passed` in ~5s. The 1 skip is `tests/migrations/test_baseline_roundtrip.py`, which needs `SCRATCH_DATABASE_URL`.
- `uv run ruff check .` (T0019.3, touched files) → all checks passed.
- `uv run mypy` (T0019.3, touched files) → no issues.
- Manual: empty-DB `alembic upgrade head` built the full 22-column `clean_jobs` schema (19 baseline + `is_active`/`first_seen_at`/`last_seen_at`); `alembic downgrade -1` cleanly dropped the three columns; upgrading the real local DB preserved all 50 rows and backfilled `first_seen_at`/`last_seen_at` truthfully from `raw_jobs.fetched_at` (0 rows at "now", join confirmed total — 0 orphans); a synthetic-row probe against the local DB proved the upsert refreshes `last_seen_at`/`is_active` and preserves `first_seen_at` across repeat runs, an 8-day-aged row expires under a 7-day window without deletion, and re-seeding flips it back active; the Dockerized (Linux) `api` service answered a live chat query with no mention of the hidden columns. Native Windows `uv run uvicorn` boot still hangs on the pre-existing `ProactorEventLoop` incompatibility, unrelated to this ticket (`Known_Issues.md`).
- Prior (T0019.2): `alembic upgrade head` against an empty scratch DB built the correct 19-column `clean_jobs` schema; `alembic stamp head` + `alembic upgrade head` against the real local DB was a clean no-op (row count unchanged at 50); the Dockerized (Linux) `api` service booted cleanly and answered a live query against the migrated/stamped schema.

## Known issues
Open known issues, risks, and out-of-scope follow-ups live in their own living register:
see [`Known_Issues.md`](Known_Issues.md). Append there when a ticket uncovers a new one.
Resolved items are archived in [`Resolved_Issues.md`](Resolved_Issues.md). A full per-module
logic review (2026-07-02) — bugs, improvement backlog, and doc insights — is captured in
[`Code_Review_Notes.md`](Code_Review_Notes.md); its bugs are logged in `Known_Issues.md`
(open) / `Resolved_Issues.md` (closed).

## Next recommended ticket
**The T0020.4 coder slice is complete** — the cron-activation runbook is committed ([`docs/T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md)) and the `## T0020` milestone + sub-ticket blocks are authored in `Tickets.md`.

**~~the nightly ingestion cron is not activated~~ — FALSE when written (2026-07-26); corrected 2026-08-09.** The cron had already been firing nightly for four days by then, because merging the workflow to `main` in PR #29 *is* what activates a `schedule:` trigger. It ran 19 times and failed 19 times (missing `DATABASE_URL` secret), harmlessly but silently, with D2 and D6 unsigned. **PR #33 comments out `schedule:`**, so the statement is true again — the cron is now genuinely dormant and activation *is* now a deliberate maintainer step. Follow the runbook, not this file, and note its new ordering: manual `workflow_dispatch` green **first**, re-arm `schedule:` **last**.

**The immediate work is not a ticket — it is landing what is already written.** Four PRs are open and unmerged; none of them is blocked on anything:

| PR | Branch | Opened | What lands |
|---|---|---|---|
| **#33** | `fix/cron-schedule-dormant` | 2026-08-09 | Stops the 19-night failing cron. **Merge first.** |
| **#31** | `feature/t0020.2-render-main-deploy` | 2026-07-26 | Tracked `render.yaml` (T0020.1 + T0020.2) |
| **#32** | `feature/t0020.3-ci-merge-gate` | 2026-07-26 | The CI gate itself — inert until merged |
| **#30** | `feature/t0021.1-read-path-schema-assertion` | 2026-07-22 | T0021.1 read-path schema assertion |

Also unpushed: this branch (`feature/t0020.4-cron-activation`, 1 commit) and the `IHA-t0021.2` worktree (8 uncommitted files, T0021.2 agent error logging).

**The T0021 / T0022 track has already begun** (release integrity → honesty → v1.0 tag — see `research/v1-release-readiness-plan.md` §2 and the `[[v1-release-roadmap-m20-m22]]` memory note). The former instruction here — *"do not treat the T0021/T0022 track as begun until cron activation is signed off"* — was overtaken by events: T0021.1 was opened as PR #30 on 2026-07-22 and T0021.2 was started in a worktree.

Also pending, all maintainer-gated:

- **T0020.3 maintainer action (pending)** — enable branch protection on `main` requiring the CI check green before merge (GitHub → Settings → Branches, or `gh api`); then verify end-to-end (a red PR is blocked, a green PR merges, and the run shows `19 deselected` confirming eval tests were not attempted).
- **T0020.2 maintainer actions — the repoint is DONE (verified 2026-08-09).** Render deploys from `main`: the live `index.html` is byte-identical to `main`'s copy and differs from `feature/t0018.4-deploy`'s by 5 lines, so the T0019.8/.10 serving fixes are live. Still pending: confirm `render.yaml`'s `name:` matches the existing service before any Blueprint sync (a mismatch mints a second Free service, eroding the 750 instance-hour margin), and confirm a no-op push to `main` triggers a redeploy.
- **T0020.4** — nightly ingestion cron activation. **The execution runbook is committed** ([`docs/T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md)); read its 2026-08-09 correction banner first. Remaining gates: **D2** (robots/ToS ratification in a tracked doc), **D6** (one-time `alembic stamp head` on Neon's direct/non-pooled host), **secrets** (`DATABASE_URL` direct host + `HEALTHCHECKS_URL` — neither has ever been set), **4a** manual `workflow_dispatch` green, **re-arm `schedule:`** (uncomment, last step), **first scheduled run**, and **D10** (v1.0 live-vs-parked decision). **D5** is signed for the local Docker-Postgres portion (2026-07-22, coder session) — the Neon/prod portion remains. **Correction:** the earlier claim that "activation is structurally possible but not automatic" had it backwards — with `schedule:` present on the default branch, activation *is* automatic, and it already occurred on 2026-07-22 with D2/D6 open. PR #33 comments out `schedule:` to restore genuine dormancy. **Setting the `DATABASE_URL` secret is now the irreversible step** — it is what turns a harmlessly-failing job into one that really scrapes and really writes production.

Both release gates the T0019.6 cron spec names are satisfied: **T0019.9** (done) and **T0019.10** (done) — the `SELECT *` leak that would have turned from cosmetic to a real honesty defect once expiry starts flipping rows is closed.

Ticket detail: [`Tickets.md`](Tickets.md) → T0020. Full gap analysis and the D1–D13 decision list: [`research/v1-release-readiness-plan.md`](../research/v1-release-readiness-plan.md).

### Outstanding manual verification (carried, does not block T0019.6's scoping)
Three tickets shipped with live-DB checks unrun because Docker Desktop was down; all are in [`Manual_Verification_Guide.md`](Manual_Verification_Guide.md). D5 above will bring the stack up — run these in the same session.

- **T0019.10** — checks **C, D, E**. The guard test proves the *statement* names exactly the 16 contract columns; unproven is that a real `fetch_job_details` call returns exactly those 16 keys and that the tool output the model sees carries no `is_active=` / `posted_date=None`. **D is load-bearing** — it is the model's actual view.
- **T0019.8** — checks **A–E**. **B is load-bearing**: endpoint date vs. `psql` `MAX(last_seen_at)`.
- **T0019.9** — its `[MED · PARTIALLY RESOLVED]` entry does not close until the re-measure in [`research/data-ingestion-stage.md`](../research/data-ingestion-stage.md) §11 runs and §11.2's table is filled from a real run. Gated on **D8**. If measured yield comes back at or above ~150, the cap is binding again and the original defect has returned.
