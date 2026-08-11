# Repo State — Archived History

Content moved out of [`../Repo_Current_State.md`](../Repo_Current_State.md) to keep that
file a lean "now" snapshot. Nothing here reflects the current branch; it is kept only so
old branch snapshots, build/test logs, and roadmap notes are not lost. Per-ticket detail
also lives in [`../Completion_Reports.md`](../Completion_Reports.md); the authoritative
history is git.

---

## Historical branch snapshot (T0014)
`fix/known-issues-hardening` — the **Milestone 14 (Pre-Deploy Known-Issue Fixes)** branch.

**Branch topology.** This branch was forked from `51913f6` (the **T0013.5 schema-freeze** commit), **not** from `main`. `main`/`origin/main` is stale at **T0011.6** — M12, M13, and the M15 behavior track are **not merged there**; they exist only as feature branches. This branch is a **parallel sibling of the M15 behavior/scenario track** (`feature/t0015.4-v1-scenario-matrix`): both forked at T0013.5 and run independently, neither blocking the other.
- **Do not rebase this branch onto `main`** — you would drop M12 + M13 (schema freeze, the current `config.py`). The correct base is `51913f6`.
- The **M15 behavior work (T0015.1–.5) is NOT present here** — it lives on the `feature/t0015.x-*` branches.

## Historical in-progress snapshot (T0014)
**T0014 — Pre-Deploy Known-Issue Fixes** ([`../Tickets.md`](../Tickets.md) → T0014). Scope was **only** the deploy-facing items in [`../Known_Issues.md`](../Known_Issues.md) section "Config, startup & deployment", deliberately kept separate from the broader deploy-hardening body. Both sub-tickets are complete:
- **T0014.1 — Graceful startup & config-load robustness**: `src/core/config.py` now resolves YAML and `.env` from the repo root and raises `ConfigLoadError` during startup instead of validating at import time; `src/core/db.py` is lazy for the same reason; FastAPI `lifespan` now fails fast on bad config.
- **T0014.2 — Known-Issues register housekeeping**: the named 13-column/`job_level` drift bullet was already absent from `Known_Issues.md`, so the sweep is recorded as a no-op archive note in `Resolved_Issues.md`; the qwen note remains open but clarified as a final pre-T0011.5 confirmation.

**Status update (2026-07-12):** T0014 complete on this branch. T0014.1 fixed startup/config-load robustness; T0014.2 reconciled the living register/archive without code or product-behavior changes.

**Open elsewhere (not this branch's concern at the time):** T0011.5 eval baseline (needs live Groq/Google creds; T0012.10 judge-agreement spot-check BLOCKED on creds — both under M11); the M15 behavior track (T0015.4 paused on the Groq daily quota, T0015.5 pending).

---

## Historical roadmap note
T0014 is closed on `fix/known-issues-hardening`: T0014.1 removed import-time config validation fragility, and T0014.2 reconciled the known-issues register/archive. The next recommended ticket at that time was **T0011.5 — threshold calibration + baseline report** once maintainer credentials are available.

Milestone 9 (data ingestion) is closed, and the structured-query-vs-detail split is complete (T0009.10 bounded `query_clean_jobs`, T0009.11 `get_job_details`). Milestone 10 (pre-deploy hardening) is essentially complete through T0010.7. T0011.1–T0011.4 and T0011.6 are all closed: the judge is picked, `internhunter_eval` is seeded and pinned, the 17-case golden dataset loads, `evals/harness.py` + `evals/test_three_seams.py` run the agent end-to-end and score every seam, and `evals/writeback.py` attaches every score onto the same Langfuse trace. T0012.2–T0012.8 are closed — Milestone 12 (Hardening) is complete.

**Ingestion Deploy Readiness is renumbered T0013 (deferred, sequenced after T0012)**, its full design captured in `../../research/deployment-research-plan.md` §4.1–§4.2.

Other future phases (resume/embedding retrieval, charts, typed error contract) still need tickets authored against `Full_Design_Document.md` / `MVP_Spec.md` §6 before implementation.

### T0016 dated update log
- **2026-07-12 T0016.1:** branch `feature/t0016.1-cors-middleware`, cut from `fix/known-issues-hardening` after T0014.1/T0014.2. `config/settings.yaml` carries the credential-less `api.cors` block, `src/api/app.py` registers `CORSMiddleware` before router includes, `tests/api/test_cors.py` proves allowed/disallowed preflight. `uv run pytest -q tests/api/test_cors.py tests/api/test_query.py tests/api/test_startup_config.py` passed.
- **2026-07-12 T0016.2:** branch `feature/t0016.2-rate-limit-429`. `slowapi` installed, `api.rate_limit: "15/minute"`, per-app limiter + friendly 429 handler, limit applied only to `POST /api/v1/agent/chat`, provider pressure mapped to a friendly busy response. `uv run pytest -q tests/api/test_rate_limit.py tests/api/test_query.py tests/api/test_cors.py tests/api/test_startup_config.py` → `16 passed`.
- **2026-07-12 T0016.3:** branch `feature/t0016.3-input-length-cap`. `api.max_query_chars: 2000`, `src/api/schemas.py` constrains `QueryRequest.query` with `DEFAULT_MAX_QUERY_CHARS = 2000`, over-limit requests return HTTP 422 before the service is awaited. `uv run pytest -q tests/api/test_query.py tests/api/test_rate_limit.py tests/api/test_cors.py tests/api/test_startup_config.py` → `18 passed`.
- **2026-07-13 T0016.4:** branch `feature/t0016.4-docs-headers`. `api.docs_enabled: true` wires `docs_url`/`redoc_url`/`openapi_url` together (flippable via `create_app(docs_enabled=...)`); `tests/api/test_docs_exposure.py` proves enabled→200 / locked-down→404. No security-header middleware by design (API-only at that point).

---

## Build/test history (T0011 – T0018.2)

Command logs moved out of the live snapshot. Current-branch results stay in `Repo_Current_State.md`.

### T0018.3 / ReAct-SQL-generation config split (pre-T0019)
- `uv run pytest tests/agents/runtime/test_provider.py tests/agents/tools/test_query_clean_jobs.py -q` (ReAct/SQL-generation config split) → `16 passed`.
- `uv run pytest -q` (full standard suite after ReAct/SQL-generation config split) → `297 passed, 19 deselected, 4 subtests passed`.
- `uv run pytest tests/api/test_static_serving.py -q` (static-serving regression — the UI keeps the `InternHunter` string this test asserts on `GET /`) → `4 passed`.
- `uv run pytest tests/api -q` (API route suite — the UI is static assets only; backend untouched) → `33 passed`.
- `uv run pytest -q` (full standard suite) → `296 passed, 19 deselected, 4 subtests passed` in ~7s.
- Render check: served `src/api/static/` standalone and loaded `index.html` in a headless browser at 960px and 390px widths — Editorial masthead/chips/composer render, the vermilion editor's-rule marks agent answers, the streaming cursor and `view-trace` link render from injected turns, and the dateline degrades to the dateless sentence when `/api/v1/ready` is unavailable (no `undefined`, no crash).

### T0018.2
- `uv run pytest tests/api/test_static_serving.py -q` → `4 passed`.
- `uv run pytest tests/api/test_stream.py -q` → `5 passed`.
- `uv run pytest tests/api -q` → `33 passed`.
- `uv run pytest -q` → `286 passed, 7 skipped, 19 deselected, 4 subtests passed` (7 skips = eval fixture DB reachability, Postgres on `localhost:5433` not running).
- `uv run ruff check src/api/app.py tests/api/test_static_serving.py` → `All checks passed!`.

### T0017.1
- `uv run pytest tests/agents/runtime/test_react_agent.py -q` → `9 passed`.
- `uv run pytest -q` → `273 passed, 7 skipped, 19 deselected, 4 subtests passed`.
- `uv run ruff check src/agents/runtime/react_agent.py tests/agents/runtime/test_react_agent.py` → `All checks passed!`.
- Live probe blocked: `GROQ_API_KEY` missing and Postgres `127.0.0.1:5433` closed.

### T0017.2
- `uv run pytest tests/api/test_stream.py -q` → `4 passed`.
- `uv run pytest tests/api -q` → `24 passed`.
- `uv run pytest -q` → `277 passed, 7 skipped, 19 deselected, 4 subtests passed`.
- `uv run ruff check src/agents/service.py src/api/routes/query.py src/api/schemas.py tests/api/test_stream.py` → `All checks passed!`.
- Live curl verification blocked (needs Groq creds + seeded local Postgres).

### T0018.1
- `uv run pytest -q tests/agents/test_service.py tests/api/test_ready.py tests/api/test_stream.py` → `11 passed`.
- `uv run ruff check src/agents/service.py src/api/routes/health.py src/api/schemas.py tests/agents/test_service.py tests/api/test_ready.py tests/api/test_stream.py` → `All checks passed!`.
- `uv run pytest -q tests/api` → `29 passed`.
- `uv run pytest -q` → `282 passed, 7 skipped, 19 deselected, 4 subtests passed`.

### T0016.x
- `uv run pytest -q tests/api/test_query.py tests/api/test_rate_limit.py tests/api/test_cors.py tests/api/test_startup_config.py` → `18 passed`.
- `uv run ruff check src/api/schemas.py tests/api/test_query.py` → `All checks passed!`.

### T0014
- `uv run pytest -q tests/core/test_config.py tests/api/test_startup_config.py` → `4 passed`.
- `uv run pytest tests/core/test_config.py -v` → `3 passed`.
- `uv run pytest tests/api/test_startup_config.py tests/api/test_query.py -v` → `10 passed`.

### T0011 – T0012 (evaluation harness & hardening)
- `uv run pytest` → `231 passed` (includes `evals/test_judge_scaffold.py`, incidentally collected by plain pytest).
- `uv run mypy` → `Found 3 errors in 3 files (checked 41 source files)` — all 3 pre-existing residuals (`checkpointer.py:25`, `middleware.py:48`, `query_clean_jobs.py:41`); `evals/` is outside `[tool.mypy] files = ["src"]`.
- `uv run ruff check` → `All checks passed!`.
- `uv run python scripts/eval_judge_spike.py` → both Groq candidates PASS; recommended `provider=groq model=openai/gpt-oss-120b`.
- `PYTHONUTF8=1 uv run deepeval test run evals/test_judge_scaffold.py` → `1 passed` (`Pass Rate: 100.0%`).
- `python -m evals.fixtures.loader` (live `internhunter_eval`, port 5433) → `COUNT(*) = 22`; all pins verified via `psql`; `reset_fixture()` rebuilds cleanly.
- `python -m pytest evals/ -v` → `10 passed`.
- T0011.3 live spot-check `PYTHONUTF8=1 python -m pytest evals/test_three_seams.py -q -k "A1 or A3 or C3 or D1 or D2" -s` → `5 passed` (run individually to stay under Groq free-tier rate limit); `ArgumentCorrectnessMetric`/`TaskCompletionMetric` scored `None` — a `deepeval==4.0.7` internal template bug.
- T0011.4 writeback: `uv run pytest -q evals/test_writeback.py` → `6 passed`; live `deepeval test run evals/test_three_seams.py -k D1` printed `scores written to trace <id>: 4`, idempotency + creds-absent (`returned 0`) both verified. Full suite `uv run pytest -q` → `246 passed, 17 failed` — all 17 = `groq.RateLimitError` (Groq daily token cap), pre-existing risk.
- T0012.2 qwen `<think>` leak: pre-fix repro returned a 4166-char `<think>` transcript; post-fix (`reasoning_format: hidden`, `max_tokens: 2048`) returned clean bare SQL. `PYTHONUTF8=1 uv run pytest tests/ -q` → `232 passed, 4 subtests passed`.
- T0012.3 template-bug fix: `deepeval` latest release is `4.0.7` (no patch); metric list confirmed; `uv run pytest evals/ -q --collect-only` → `33 tests collected`, no import errors.
- T0012.4 `trace_url`: `uv run pytest tests/ -q` → `232 passed, 4 subtests passed`.
- T0012.5 empty-answer fallback: manual driver printed `True` (`result["answer"] == FALLBACK_ANSWER`); `uv run pytest tests/ -q` → `236 passed, 4 subtests passed`.
- T0012.6 non-str content coercion: `uv run pytest -q --ignore=evals` → `239 passed, 4 subtests passed`; `mypy` down to 2 residuals (`query_clean_jobs.py` resolved).
- T0012.7 `eval` marker + `addopts`: after change `254 passed, 18 deselected, 4 subtests passed` (18 = 1 live judge + 17 `test_three_seams`); `--strict-markers` added.
- T0012.8 native-async `generate_sql`: `uv run pytest` → `253 passed, 18 deselected`; `mypy` 2 residuals unchanged.
- T0012.9: `uv run pytest -q` → `246 passed, 7 skipped, 18 deselected, 4 subtests passed`.
- T0012.10 judge `thinking_budget` + `FaithfulnessMetric` removed: `uv run pytest evals/test_judge.py -v` → `1 passed`; `uv run pytest -q` → `247 passed, 7 skipped, 18 deselected`; live judge-agreement spot-check **BLOCKED** (no `GOOGLE_API_KEY`/Groq creds).

## Historical branch snapshot (T0019 – T0021, through the 2026-08-09 prune)

Moved out of `../Repo_Current_State.md` on 2026-08-09, when the repo was pruned to a single
`main` branch with no worktrees and no open PRs. The per-ticket "Prior ticket — …" chain below
was the live "Current branch" section for the whole T0019–T0021 run; it is preserved verbatim
because several of its notes are the only prose record of *why* a branch was cut or held.
None of it describes the current state. The authoritative history is git.

### The reality-check box (2026-08-09)

Retained as a record of a correction sequence, not as live guidance. Three claims in the
then-current file were checked against GitHub/Render and found false; the box was then amended
twice more the same day as the underlying facts moved. **All three items are now closed** — the
cron is parked (`workflow_dispatch` only), `ci.yml` is live and gating, and the T0021 track has
landed through T0021.2. The lesson it records is worth keeping: a "current state" doc accreted
three layers of correction-on-correction in one day, which is what motivated collapsing it.

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
>    **Closed out 2026-08-09:** PR #30 merged (`df451ef`) once D6 made Neon 22 columns, and the worktree's
>    8 files are committed on `feature/t0021.2-agent-error-logging`. Its two stale doc edits were
>    **discarded and rewritten** rather than committed — cut from `bcc81db` on 2026-07-22, they would have
>    reverted the T0020.x + D6 doc work that landed in the 18 commits after.
>
> Verified **true**: `main` = `bcc81db`; Render deploys from `main` (live `index.html` is byte-identical to
> `main`'s, and differs from `feature/t0018.4-deploy`'s), so the T0019.8/.10 serving fixes **are** live.
>
> **Update (2026-08-09, later the same day):** items 2 and 3 of this box have moved on. PRs #31/#32/#34/#35/#36
> have since merged, so `main` is now `56d74d9` and **`ci.yml` is live** — the gate ran for the first time on
> PR #36 and passed (`329 passed, 8 skipped, 19 deselected`). Item 1 (the cron) is unchanged: still parked,
> `workflow_dispatch` only.

### The T0019 → T0021.2 branch chain (verbatim)


`feature/t0021.2-agent-error-logging` — **T0021.2 agent-path error logging at swallowed catch sites (2026-08-09).** Cut from `main` (`3b5fc0a`, the PR #38 D6-signoff merge, which carries T0021.1 via PR #30). Adds one `logger.error(...)` at each of the three catch sites named by the 2026-07-22 error-handling honesty audit: `query_clean_jobs.db_error` and `get_job_details.db_error` at the two `except ExecutorError` sites, and `stream_agent_response.failed` in the streaming catch-all — the last also **binding** the `classify_provider_busy_error(exc)` result that was previously computed and thrown away, recording it as `reclassified_busy`, plus `session_id` so a user-reported failure is traceable. **Log-only by design: no user-facing string changed.** `stream_agent_response` still returns `BUSY_MESSAGE` for every failure including non-provider ones; introducing a `GENERIC_ERROR_MESSAGE` is honesty work deferred to **T0021.4**, so the audit's "misreported to the user" half stays open — this ticket closes the observability half only. Three `Known_Issues.md` entries (1 MED + 2 HIGH) moved to `Resolved_Issues.md`; the `validate_sql` reject-branch logging idea was **split out as a new `[LOW · OPEN]`** rather than closed with them, since nothing is raised there. The `## T0021` milestone + the `### T0021.2` block were authored in `Tickets.md` (same after-the-fact pattern as T0020; .3/.4 deliberately left unscoped). **Note on the base:** this branch sat at `bcc81db` with the work uncommitted for 18 days and was rebased twice — first to local `main`, then to `origin/main` after PRs #30/#38 merged mid-session. Its stale `Known_Issues.md` / `Repo_Current_State.md` edits were rewritten against the current base, not applied.

Prior ticket — `feature/t0021.1-read-path-schema-assertion` — **T0021.1 API read-path startup schema assertion (2026-07-22).** Cut from `main` (`bcc81db`, the PR #29 reconciliation carrying all T0019 work); T0021 is an independent code track parallel to T0020, so it branches off `main`, not the T0020 chain. Adds a boot-time `clean_jobs` schema guard on the serving path: `src/api/schema_guard.py::assert_serving_schema` (new) is called inside `app.py`'s `lifespan` via `asyncio.to_thread`, after `load_settings()` and before the checkpointer pool opens, and aborts the FastAPI boot with `SchemaGuardError` on any schema drift (missing/renamed/extra column), an absent table, or a DB-inspection failure — closing the read-path half of the 2026-07-15 drift incident (T0019.5 covered the write path). The guard imports **only** from `src.core.*` + `sqlalchemy`; per the layer-isolation rule it does **not** import the `src.services.ingestion` package, so the 22-column expected set is a frozen literal duplicated deliberately (tracked in `Known_Issues.md` → Config, startup & deployment). Distinct log events `api.schema_ok` / `api.schema_drift` keep serving-path drift separable from the ingestion path's `ingestion.schema_*`.

> **✅ Resolved — this merged as PR #30 (`df451ef`) on 2026-08-09**, after D6 took Neon from 19 to 22 columns.
> The hold below is retained as the record of why it was held. Original text:
>
> **⚠ This branch must not merge yet (2026-08-09).** Merged `origin/main` (`56d74d9`) to clear doc conflicts;
> that merge brought in the Neon-baseline finding. Production `clean_jobs` has **19** columns, not 22 —
> `first_seen_at`, `is_active`, `last_seen_at` are missing — so `assert_serving_schema` would raise
> `SchemaGuardError` in the `lifespan` and **abort the FastAPI boot on Render, taking the live demo down.**
> Migrate Neon to Alembic head first (`T0020.4_Cron_Activation_Runbook.md` §3, steps 3a–3d), confirm 22
> columns, then merge. The guard is not wrong — it detected real production drift before shipping, which is
> the job it was built for.

Prior ticket — `feature/t0020.4-cron-activation` — **T0020.4 cron-activation runbook + T0020 milestone authoring (docs-only, 2026-07-26).** Cut from `feature/t0020.3-ci-merge-gate`. Committed [`docs/T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md) and authored the `## T0020` milestone + sub-ticket blocks in `Tickets.md`. **This branch is not pushed and has no PR.** Prior ticket — **T0020.3 CI merge gate on `main` (GitHub Actions, 2026-07-22).** Cut from `feature/t0020.2-render-main-deploy`. Adds `.github/workflows/ci.yml`: on every PR targeting `main` it runs `uv run ruff check .` + `uv run mypy` + `uv run pytest -q` (SHA-pinned `actions/checkout@9c091bb` + `astral-sh/setup-uv@11f9893` matching `ingestion.yml`, `permissions: contents: read`, `concurrency` with `cancel-in-progress`, `timeout-minutes: 15`, four dummy env vars that only satisfy `Settings` load-time validation — the standard suite mocks DB + LLMs, and eval tests are auto-deselected by `pyproject` addopts so the gate adds no `-m` flag). To make the gate genuinely green, the two pre-existing mypy `[arg-type]` errors were baselined with **targeted** `# type: ignore[arg-type]` at `src/core/checkpointer.py:25` and `src/agents/runtime/middleware.py:48` (narrow, not blanket — a new error of any other type on those lines still fails); both are third-party stub/generic mismatches, real fix deferred and logged in `Known_Issues.md`. Only those 2 comment-only lines of code changed. **Branch protection to *enforce* the gate is a pending maintainer action** (a coder session can't enable a repo-admin setting) — logged in `Known_Issues.md`. Prior ticket — **T0020.2 Render deploy source → `main` + tracked `render.yaml` (infra-config + docs, 2026-07-22).** Cut from `feature/t0020.1-main-reconciliation`. Adds a tracked `render.yaml` blueprint at the repo root that pins the `InternHunterAgent` web service to `main` with the recorded runtime settings (Docker `./docker/Dockerfile`, context `.`, Singapore, Free, `WEB_CONCURRENCY=1`, `PORT=8000`, health `/api/v1/health`, `autoDeploy: true`); all five secrets declared `sync: false` (no values). The **repo now pins `main`**, and the maintainer **completed the dashboard repoint** `feature/t0018.4-deploy` → `main` (2026-07-22) — the redeploy off `main` succeeded, so the live path now serves the T0019.8/.10 fixes. A live-surface spot-check (T0019.10 UI behaviors) and the separate Blueprint-sync decision remain — see `Known_Issues.md`. No app/config/Dockerfile change. Prior ticket — **T0020.1 `main` reconciliation follow-through (docs + local ref, 2026-07-22):** `main` is now the reconciled head at `bcc81db` (PR #29 — the T0020.1 reconciliation merge of the T0019.10 chain), carrying the full T0019.6/.8/.9/.10 chain plus the M13/M15 doc rescues. That ticket fast-forwarded the local ref to `origin/main` (`bcc81db`) and corrected the docs that still described the pre-merge "stuck at T0009 / ec0b25a" world; no code, config, or history change. Prior ticket chain (now landed on `main` via PR #29): `feature/t0019.10-job-details-allowlist` — **T0019.10 `get_job_details` explicit column allowlist (2026-07-21).** `fetch_job_details` no longer runs `SELECT *`; it names the 16 columns of the `prompts.schema_context` frozen contract explicitly, closing a six-column leak (`is_active`, `first_seen_at`, `last_seen_at`, `posted_date`, `source`, `external_id`) that reached the agent verbatim through `_build_answer`'s `row.items()`. Cut from `feature/t0019.9-ingestion-coverage` — **T0019.9 Ingestion coverage: raised `max_jobs` + round-robin query interleave (2026-07-20).** Cut from `feature/t0019.8-truthful-refresh-date` — **T0019.8 Truthful refresh date on `/ready` (2026-07-20).** Previously `feature/t0019.7-keepalive-verification` — **T0019.7 Windowed keep-alive ping + Neon idle-pool verification (doc-only, independent of T0019.2–.6).** Cut from `feature/t0019.6-nightly-cron` (`bb75d10`), which sits at the same commit as `feature/t0019.5-unattended-safety`'s post-merge state at the time of cutting. Branched off `feature/t0019.4-source-resilience`, which was branched off `feature/t0019.3-accumulate-lifecycle`, which was branched off `feature/t0019.2-alembic-baseline`, which was branched off `feature/t0019.1-robots-tos-gate`, which was branched off `feature/t0018.4-deploy` (the branch Render deployed from at T0018.4; T0020.2 repointed the deploy source to `main`, now pinned by the tracked `render.yaml`; the maintainer completed the dashboard repoint 2026-07-22) — **LIVE: https://internhunteragent.onrender.com** (verified end-to-end 2026-07-16). **Correction (2026-07-19):** the long-standing note that `main` is "stale at T0009" is **no longer true** — `main` carries PRs #20–#27 (T0010.4, T0010.7, T0011.6, T0016.4, and T0017.1/T0017.2 via the `-recovered` branches) and sits at `e3e65ae`. `feature/t0019.5-unattended-safety` merged `origin/main` (`83fbe15`) to close that divergence; the merge was content-neutral (resulting tree byte-identical to `bb75d10`) because every `main` change was already present here — the `-recovered` T0017 commits reproduced byte-identical code. **Superseded (2026-07-22, T0020.1):** that divergence is fully closed — `main` was reconciled to `bcc81db` via PR #29 and is now the true head, so the "sits at `e3e65ae`" / "branch off `main` after this PR lands" notes above are historical; the current head is `bcc81db`.

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
- Everything for this branch's current work is in [`Tickets.md`](Tickets.md) → **T0018.4** and the T0018.4 manual checklist in [`Manual_Verification_Archive.md`](Manual_Verification_Archive.md).
- Older branch/roadmap snapshots (T0014 and earlier) are archived in [`archive/Repo_State_History.md`](archive/Repo_State_History.md).

## Build/test history (T0019.3 – T0019.10)

Moved out of `../Repo_Current_State.md` on 2026-08-09 when that section was collapsed to
current-ticket-only. These per-ticket logs are point-in-time and **not comparable to each
other or to current numbers** — the suite grew, the skip behaviour changed, and T0020.3 later
baselined the two `mypy [arg-type]` errors that recur throughout, so `mypy` is now clean.

Earlier — current-branch (T0019.10 + the cherry-picked T0019.6) results:

- `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ingestion.yml')); print('YAML OK')"` (T0019.6) → `YAML OK`.
- `git status --short` (T0019.6, before commit) → only the files this ticket touched (`docs/**`, `research/**`) plus the previously-untracked `.github/` now staged; no `src/`/`tests/`/`config/` changes.
- `uv run pytest -q` (T0019.6, full standard suite) → `328 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~8567s — **identical to T0019.9's baseline**, exactly as expected since no `src`/`tests` file was touched by this ticket.
- `uv run ruff check .` (T0019.6, whole repo) → all checks passed.
- `uv run mypy` (T0019.6, whole repo) → the same 2 pre-existing, unrelated errors (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48`). No third error introduced.
- `grep -n "secrets\." .github/workflows/ingestion.yml` → exactly 2 lines (`DATABASE_URL`, `HEALTHCHECKS_URL`); no real Groq or Langfuse secret referenced.
- `grep -n "No autonomous or background execution" docs/Full_Design_Document.md` → no match (the amended line replaces it); `sed -n '20,30p'` confirms the amended §2 bullet + T0019.6 note is present.
- **Manual check B (empirical secrets-required test) was run this session, not just carried from the stash:** with `.env` moved aside, unsetting each of `GROQ_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY` in turn against `uv run python -m src.services.ingestion.loader` failed fast with `ConfigLoadError` and `exit=1` before any DB connection, for all three. `.env` restored immediately after. Full transcript in the T0019.6 completion report.
- **Checks C, D, E were not run** — they require GitHub Actions secrets configured on the repo and/or the T0019 chain merged to `main`, both maintainer-gated actions outside this ticket's scope. Not fabricated; see `Manual_Verification_Archive.md` → T0019.6.
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
- **⚠ Manual verification NOT run (T0019.8).** Docker Desktop was not running this session (`docker ps` → `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`), so none of checks A–E in the new `Manual_Verification_Archive.md` T0019.8 entry were executed. The automated tests patch `_select_max_last_seen` and feed it a `datetime.date`, so they prove the fallback logic but **cannot** prove that Postgres's `::date` cast arrives as a `datetime.date` through psycopg3, nor that the real value wins over the fallback against a populated table. **Check B is outstanding** — this is the same class of gap as T0019.5's unrun checks B–E, and is recorded rather than glossed.

Earlier T0019.7 and T0019.5 results follow.

- `uv run pytest -q` (T0019.7, full standard suite — no code changed, confirmed unaffected) → `319 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~266s, identical to the pre-ticket baseline.
- `uv run ruff check .` (T0019.7, whole repo) → all checks passed.
- `uv run mypy` (T0019.7, whole repo) → the same 2 pre-existing, unrelated errors (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48` — logged in `Known_Issues.md`).
- Live check: `curl -s -o /dev/null -w "%{http_code}\n" https://internhunteragent.onrender.com/api/v1/health` → `200`, confirming the T0019.7 runbook's ping target is reachable and correct.

- `uv run pytest -q` (T0019.5, full standard suite, DB-dependent tests skip without Docker up) → `319 passed, 8 skipped, 19 deselected, 4 subtests passed` in ~268s. No pre-existing test's assertions were weakened — the 9 pre-existing `test_loader.py` tests now patch `assert_clean_jobs_schema` and carry `safety.min_yield: 0` in their mocked config.
- `uv run pytest tests/services/ingestion/test_safety.py tests/services/ingestion/test_loader.py -q` (T0019.5, targeted) → `23 passed` in <1s.
- `uv run ruff check .` (T0019.5, whole repo) → all checks passed.
- `uv run mypy` (T0019.5, whole repo) → 2 pre-existing errors, both unrelated to this ticket (`src/core/checkpointer.py:25`, `src/agents/runtime/middleware.py:48` — logged in `Known_Issues.md`); the three touched files (`safety.py`, `loader.py`, `src/core/config.py`) are clean.
- Manual verification against a live local Docker DB (checks B–E of the T0019.5 checklist) was not run in this session — no local Docker Postgres was up. Flagged as a risk below; the checklist is appended to `Manual_Verification_Archive.md` for the next person with the stack running.

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

