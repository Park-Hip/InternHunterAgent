# Completion Reports — Archive (M0–M14)

Per-ticket outcome records for milestones **0–14**, moved out of the live
[`../Completion_Reports.md`](../Completion_Reports.md) to keep it focused on the current
deploy-era stack (M16+). Entries are condensed to the durable summary; the full
implementation detail lives in the code and git history. Recent milestones (M16–M18) stay
in the live file.

---

## Milestone 0–5 — Foundation through Hardening
- **T0000** — Foundation (FastAPI, logging, health endpoint).
- **T0001** — Runnable request flow (`POST /api/v1/agent/chat`).
- **T0002** — ReAct agent runtime.
- **T0003** — Self-hosted Langfuse (Docker Compose, under `infra/langfuse/`). <!-- archived-on-tag -->
- **T0004** — Tracing integration.
- **T0005** — Hardening (error handling, timeouts, integration tests).

## Milestone 6 — First Real SQL Tool
- **T0006.1** — DB foundation (Postgres, deps, settings, session factory).
- **T0006.2** — Query result models (`TableArtifact`, `QueryRefusal`, `QueryToolResult`) + serialization tests.
- **T0006.3** — Deterministic `format_rows` in `table_formatter.py` + edge-case tests.
- **T0006.4** — Schema context + SQL-generation prompt (`build_clean_jobs_schema_context()`, `load_sql_generation_prompt()`).
- **T0006.5** — Read-only SQL validator (`sql_validator.py::validate_sql`, 13 tests).
- **T0006.6** — SQL executor (`executor.py::execute_validated_sql`, `ExecutorError`).
- **T0006.7** — `query_clean_jobs` LangChain tool adapter (schema → SQL gen → validate → execute → format → answer).
- **T0006.8** — Registered `query_clean_jobs` in `factory.py`; system prompt forces tool use for job-data questions.
- **T0006.9** — Confirmed public API stays answer-only (audit, no code change).
- **T0006.10** — End-to-end manual verification (no code change).

## Milestone 7 — Conversation Memory
- **T0007.1** — Startup lifecycle + async checkpointer foundation (`checkpointer.py`, FastAPI `lifespan`, agent via `app.state.runtime`).
- **T0007.2** — Wired checkpointer + `session_id → thread_id`; service generates a UUID4 id when omitted and returns the id used.
- **T0007.3** — Native context trimming: `TrimMessagesMiddleware` applies `trim_messages` (count cap to `agent.memory.max_messages`) per-turn only.
- **T0007.4** — Memory tests + doc status flips (closes M7). No runtime behavior change.

## Milestone 8 — System Prompt & Persona Refinement
- **T0008.1** — Resumi persona + on-topic policy + honesty rules (rewrote `system_prompt` only).
- **T0008.2** — SQL-generation prompt hardening; moved schema facts into `config/prompts.yaml::schema_context`; `load_schema_context()`.
- **T0008.3** — Manual verification (closes M8): rebuilt image, 12-question checklist all passed, 70 tests green.

## Milestone 9 — Data Ingestion (VietnamWorks)
- **T0009.1** — Schema: `raw_jobs` + enriched `clean_jobs` (role, source/external_id, structured salary, unique `(source, external_id)`); idempotent `init_db.sql`; ingestion `models.py`. 70 pass.
- **T0009.2** — `config/ingestion.yaml` (API params, 8 keyword queries, tech_dictionary, role_taxonomy, city_alias_map); `RawPosting`/`NormalizedJob` models. 70 pass.
- **T0009.3** — `JobSource` interface + `VietnamWorksSource` (keyword recall + jobFunction filter, dedupe, `max_jobs` cap, content_hash); promoted `httpx` to main deps. 84 pass.
- **T0009.4** — Raw landing: `raw_store.upsert_raw_postings` (batched `INSERT … ON CONFLICT`), `RawStoreError`. 93 pass.
- **T0009.5** — Source-agnostic `transform.py` + VietnamWorks `to_normalized_job`; dicts from config; structured salary. 100 pass.
- **T0009.6** — Loader: `clean_store.replace_clean_jobs` (TRUNCATE+upsert, empty-guard) + `loader.run_ingestion`. 184 pass.
- **T0009.7** — Agent schema follow-through: `schema_context` lists 12 visible columns; salary honesty reworded; `posted_date` omitted. 184 pass.
- **T0009.8** — E2E manual verification (closes M9): live ingest `{fetched:50, raw_upserted:50, clean_loaded:50}`; fixed a `cityName` field bug in `to_normalized_job`; logged 3 follow-ups (TPM 413, freshness fabrication, hidden-salary wording). 184 pass.
- **T0009.9** — Explicit schema reset path (`scripts/reset_db.sql`); documented reset-then-reingest. 184 pass.
- **T0009.10** — Bounded query output (fixes Groq TPM 413): `format_rows` drops `description`, caps at `max_rows`; answer says "Showing N of M". +`agent.query.max_rows: 20`. 188 pass.
- **T0009.11** — `get_job_details` tool: deterministic parameterized fetch-by-id; +`agent.query.max_detail_ids: 3`; registered in factory. 199 pass.

## Milestone 10 — Pre-deploy Hardening
- **T0010.1** — Graceful answer + typed error contract: `AgentResponse` TypedDict coerces empty→`FALLBACK_ANSWER`; `InvalidQueryError`→`400` on blank; `500` path intact. 204 pass.
- **T0010.3** — True single-table SQL allowlist: validator masks string literals, requires every `FROM`/`JOIN` = `clean_jobs`, rejects comma-`FROM`. 210 pass.
- **T0010.4** — Offload SQL-gen LLM call off the event loop (`await asyncio.to_thread(generate_sql, …)`). 211 pass.
- **Bugfix (review bug 4)** — SQL validator denylist false-positives on string literals: mask literals before the denylist scan. 214 pass.
- **Bugfix (review bug 3)** — Ingestion aborting on one bad payload: per-record `try/except`, `skipped` count in the summary. 215 pass.

## Milestone 11 — Model Evaluation
- **T0011.1** — Judge spike + harness scaffold: picked Groq `openai/gpt-oss-120b`; new `evals/` package (`judge.py`, `test_judge_scaffold.py`); `eval.judge` config; `deepeval` dev dep. Logged Windows-console + judge-choice notes. 231 pass.
- **T0011.2** — Eval fixture DB + goldens: `internhunter_eval` (port 5433, 22 seeded rows), 17-case `golden_dataset.json`, `fixtures/loader.py`. Logged the `evals/goldens.py`-can't-coexist deviation. 10 evals tests.
- **T0011.3** — Three-seam instrumentation + metric stack: config-forward `config` param into `generate_sql`; `harness.py` scores 3 seams from the captured span tree; `test_three_seams.py` (report-only). Tracing boundary intact (`git grep deepeval src/` clean). Logged 3 findings (qwen `<think>` leak HIGH, deepeval metric-template bug MED, full-run rate limit LOW).
- **T0011.4** — Langfuse score writeback: `writeback.py::write_scores` attaches every non-`None` score to the same trace; never raises. 6 unit tests; live-verified against local Langfuse.
- **T0011.6** — Gemini judge provider: `build_judge()` dispatches on `provider`; new `google` branch (`gemini-2.5-flash`, `max_tokens=4096` for the thinking model); `GOOGLE_API_KEY` optional. Judge-agreement gate BLOCKED on Groq TPD.
- **T0011.6 follow-up** — Judge RPM throttle: `_RpmThrottle` + `eval.judge.rpm: 8` (works either provider; `0` disables).

## Milestone 12 — Hardening
- **T0012.2** — Fix qwen `<think>` leak: `agent.groq.reasoning_format: hidden` + `max_tokens: 2048`; 2 provider tests. Live A3/C3 data-answer re-check left as a follow-up (Docker was down). 232 pass.
- **T0012.3** — Unblock deepeval metrics: `GEval` substitutes for `ArgumentCorrectnessMetric`/`TaskCompletionMetric` (seam-2's dropped as redundant). Live scoring deliberately skipped to save API spend.
- **T0012.4** — Populate `trace_url` (via `get_trace_url`; service pass-through, no Langfuse import added). Closes C4.
- **T0012.5** — Graceful fallback on empty answer: `_extract_answer` returns `""`, existing guard fires → `200`+`FALLBACK_ANSWER`. 236 pass.
- **T0012.6** — Coerce non-str model content: `_content_to_text` before `.strip()`; mypy 3→2 residuals. 239 pass.
- **T0012.7** — Keep live-API eval tests out of plain pytest: `eval` marker + `addopts = "-m 'not eval' --strict-markers"`. 254 pass / 18 deselected.
- **T0012.8** — Native-async `generate_sql` (`await model.ainvoke`). 253 pass.
- **T0012.9** — Cosmetic cleanup: fixture `job_level`/source fidelity, deleted dead `main.py`, rewrote stale comment, register hygiene. 253 pass.
- **T0012.10** — Reduce judge cost: `eval.judge.thinking_budget: 0`, dropped redundant `FaithfulnessMetric`; live judge-agreement spot-check BLOCKED (no creds). 247 pass.

## Milestone 14 — Pre-Deploy Known-Issue Fixes
- **T0014.1** — Graceful startup & config-load robustness: lazy `settings` proxy + lazy `db`, `ConfigLoadError`, FastAPI `lifespan` loads config first (fails fast). Tests in `test_config.py`/`test_startup_config.py`.
- **T0014.2** — Known-Issues register housekeeping: reconciled register/archive after sibling T0015.4 evidence (docs-only, no-op sweep). Smoke suite passed.
