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
