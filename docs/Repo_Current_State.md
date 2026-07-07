## Current branch
feature/t0012.9-cosmetic-cleanup

## Completed milestones
One line per milestone. Per-ticket detail (files changed, test counts, follow-ups) lives in [`Completion_Reports.md`](Completion_Reports.md).

- **M0–M5** — Foundation → runnable request flow → ReAct runtime → self-hosted Langfuse → tracing integration → hardening.
- **M6** (T0006.1–.10) — First real SQL tool: read-only `query_clean_jobs` (schema → SQL gen → validate → execute → format), registered in the runtime, public API kept answer-only.
- **M7** (T0007.1–.4) — Short-term conversation memory: native Postgres checkpointer + async pool, `session_id → thread_id`, native `trim_messages` count cap.
- **M8** (T0008.1–.3) — Resumi persona, on-topic/honesty rules, SQL-generation hardening, schema context moved into `config/prompts.yaml`.
- **M9** (T0009.1–.11) — VietnamWorks data ingestion: `raw_jobs` landing + enriched `clean_jobs`, source-agnostic transform, idempotent loader; plus reset path, bounded query output (Groq `413` fix), and the `get_job_details` detail split.
- **M10** (T0010.1/.3/.4) — Pre-deploy hardening: typed error contract + graceful answer, true single-table SQL allowlist, off-event-loop LLM call; code-review bugs 3 & 4 fixed.
- **M11** (T0011.1–.6) — Model evaluation harness: DeepEval judge (Groq→Gemini) + RPM throttle, seeded fixture DB + versioned goldens, three-seam metric stack, Langfuse score writeback.
- **M12** (T0012.2–.9) — Hardening: qwen `<think>` leak fix, deepeval metric-template unblock, `trace_url` populated, graceful empty-answer fallback, non-str content coercion, eval-test marker hygiene, native-async `generate_sql`, cosmetic cleanup.

## In progress / next
- **Milestone 11 not fully closed:** T0011.5 (threshold calibration + baseline report) remains **open** — its two hard prerequisites (T0012.2 qwen `<think>` leak, T0012.3 deepeval metric-template bug) are now cleared, so it is unblocked.
- **Milestone 12 complete.** Milestone 10 remaining lower-priority items (freshness-honesty determinism, hidden-salary phrasing, the best-effort id-in-SQL nudge) are tracked in [`Known_Issues.md`](Known_Issues.md), not as blocking tickets.
- **Next recommended ticket:** T0011.5.

## Current folder structure
```text
.
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
|   |   `-- routes/
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

Practical commands from the repository layout:
- `uv run uvicorn src.api.app:app --reload`
- `uv run pytest` (T0012.7: the standard suite now excludes the `eval`-marked live tests by default — `addopts = "-m 'not eval' --strict-markers"` in `pyproject.toml`)
- `uv run pytest -m eval` (T0012.7: runs only the two live-API eval files, `evals/test_judge_scaffold.py` + `evals/test_three_seams.py`, 18 tests total; needs Groq/judge creds + fixture DB)
- `PYTHONUTF8=1 uv run deepeval test run evals/test_three_seams.py -m eval` (T0012.7: the verified working `deepeval` invocation — `deepeval test run` inherits `addopts` too, so `-m eval` must be passed through explicitly or 0 tests are selected; see `Known_Issues.md`)
- `uv run ruff check .` (lint; config in `pyproject.toml` `[tool.ruff]`, `scripts/` spikes excluded)
- `uv run mypy` (type check `src`; config in `pyproject.toml` `[tool.mypy]`, pydantic plugin enabled)
- `uv run python scripts/eval_judge_spike.py` (throwaway judge JSON-reliability spike, T0011.1)
- `PYTHONUTF8=1 uv run deepeval test run evals/test_judge_scaffold.py -m eval` (harness scaffold; `PYTHONUTF8=1` needed on Windows — see `Known_Issues.md`; `-m eval` needed post-T0012.7)
- `python -m evals.fixtures.loader` (builds/refreshes the `internhunter_eval` fixture DB from scratch, prints `COUNT(*)`, T0011.2)
- `python -c "from evals.fixtures.loader import reset_fixture; reset_fixture()"` (drops + rebuilds the fixture tables)
- `docker compose up -d` (root `docker-compose.yml`: Postgres + API, port `5433` host-side)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/init_db.sql` (routine, non-destructive schema init/no-op)
- `docker compose exec -T postgres psql -U internhunter -d internhunter -f scripts/reset_db.sql` (destructive — drops and recreates both tables; use only when the schema shape changes, then re-ingest)
- `docker compose -f infra/docker-compose.yaml up --build` (Langfuse observability stack)

## Build/test status
- Command run: `uv run pytest`
- Result: passed
- Summary: `231 passed` (includes `evals/test_judge_scaffold.py`, incidentally collected by plain pytest — see `Known_Issues.md`)
- Command run: `uv run mypy`
- Result: `Found 3 errors in 3 files (checked 41 source files)` — all 3 are pre-existing, documented residuals (`checkpointer.py:25`, `middleware.py:48`, `query_clean_jobs.py:41`); unchanged by T0011.1 (no new errors; `evals/` is outside `[tool.mypy] files = ["src"]`).
- Command run: `uv run ruff check`
- Result: `All checks passed!`
- Command run: `uv run python scripts/eval_judge_spike.py`
- Result: both Groq candidates PASS; recommended `provider=groq model=openai/gpt-oss-120b`.
- Command run: `PYTHONUTF8=1 uv run deepeval test run evals/test_judge_scaffold.py`
- Result: `1 passed` — `Pass Rate: 100.0%`.
- Command run: `python -m evals.fixtures.loader` (T0011.2, against the live `internhunter_eval` Postgres DB, port 5433)
- Result: `COUNT(*) = 22`; all pins verified via `psql` (role split 5/4/4/4/4/1, Python=12, Python∩Hanoi=7, COBOL=0, interns=5, VND max 40,000,000, USD max 5,000); `reset_fixture()` rebuilds cleanly back to 22.
- Command run: `python -m pytest evals/ -v`
- Result: `10 passed` (7 fixture-count tests against the live eval DB, 2 goldens-load tests with no DB, 1 pre-existing judge-scaffold test).
- Command run: `python -m ruff check evals config src`
- Result: `All checks passed!`
- Command run: `python -m mypy`
- Result: same 3 pre-existing residuals as T0011.1, no new errors (`evals/` untouched by `[tool.mypy] files = ["src"]`).
- Command run: `pytest tests/agents/tools/test_query_clean_jobs.py -q` (T0011.3, config-forward change)
- Result: `8 passed`.
- Command run: `python -m pytest tests/ -q` (T0011.3, full suite after the config-forward change)
- Result: `230 passed, 4 subtests passed`.
- Command run: `git grep -n "deepeval" src/` (T0011.3, tracing-boundary check)
- Result: no matches.
- Command run: `python -m evals.fixtures.loader` (T0011.3, fixture DB brought up via `docker compose up -d postgres`)
- Result: `COUNT(*) = 22`.
- Command run: `PYTHONUTF8=1 python -m pytest evals/test_three_seams.py -q -k "A1 or A3 or C3 or D1 or D2" -s` (T0011.3, live spot-check against real Groq)
- Result: `5 passed` (run individually across several invocations to stay under the Groq free-tier rate limit — see `Known_Issues.md`). Real per-seam scores observed, e.g. D1/D2: Tool Correctness `1.0`, Argument Correctness `1.0`, Faithfulness `1.0`, Honesty `1.0`; A3/C3: SQL Schema Quality (seam 2, GEval) `0.2`–`0.5` against an actually-captured nested `generate_sql` span. `ArgumentCorrectnessMetric` (when a tool was called) and `TaskCompletionMetric` (always) scored `None` — a `deepeval==4.0.7` internal template bug, logged in `Known_Issues.md`, not a harness defect. Full 17-golden run not completed live in this sandbox (rate limits); the config-forward/span-capture mechanism itself was additionally verified with a fake-model, no-network check.
- Command run: `uv run pytest -q evals/test_writeback.py` (T0011.4, no-network unit tests)
- Result: `6 passed`.
- Command run: `uv run ruff check .` (T0011.4)
- Result: `All checks passed!`
- Command run: `uv run mypy evals/writeback.py evals/harness.py evals/test_writeback.py` (T0011.4)
- Result: no new errors (the 3 pre-existing residuals live in unrelated files not touched by this ticket).
- Command run: `PYTHONUTF8=1 uv run deepeval test run evals/test_three_seams.py -k D1` (T0011.4, live golden against a locally running self-hosted Langfuse, `LANGFUSE_BASE_URL=http://localhost:3000`)
- Result: `1 passed`; printed `scores written to trace <id>: 4`; confirmed via `lf.api.scores.get_many(trace_id=...)` that all 4 seam-prefixed scores landed on the real trace.
- Command run: manual `write_scores(trace_id, {...})` re-run against the same trace_id with a different score value (idempotency check, T0011.4)
- Result: same `score_id` upserted in place after Langfuse's async worker caught up — still exactly 4 score rows for the trace, no duplicate.
- Command run: `write_scores(...)` with `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` unset (creds-absent check, T0011.4)
- Result: returned `0`, no exception.
- Command run: `uv run pytest -q` (T0011.4, full suite, Langfuse running locally)
- Result: `246 passed, 17 failed` — all 17 failures are `groq.RateLimitError` (Groq daily token cap) from the full-17-golden live `test_three_seams.py` run, a pre-existing risk already logged under T0011.3's Known_Issues entry; no failures attributable to this ticket's changes.
- Command run: `PYTHONUTF8=1 uv run python -c "from src.agents.tools.query_clean_jobs import generate_sql; generate_sql('Which companies have AI Engineer roles?')"` (T0012.2, live, pre-fix repro)
- Result: raw response was a 4166-char `<think>...</think>` chain-of-thought transcript, not bare SQL — confirmed the leak.
- Command run: same call, post-fix (`agent.groq.reasoning_format: hidden`, `max_tokens: 2048`)
- Result: clean bare `SELECT id, company FROM clean_jobs WHERE role ILIKE '%AI Engineer%'`, no `<think>` text.
- Command run: direct `model.invoke(...)` probe with `reasoning_format='hidden'` at the old `max_tokens=1024`
- Result: `content=''`, `usage_metadata.output_token_details.reasoning == 1024` — proved the empty-answer symptom is separate: reasoning consumed the entire token budget. Re-run at `max_tokens=2048` returned non-empty `.content`.
- Command run: `AgentRuntime().ainvoke(...)` live on A3 ("Which jobs use Python?") and C3 ("Do you have any COBOL jobs?") (T0012.2)
- Result: both returned clean, non-empty, `<think>`-free answers — but a graceful "database error" message, not real data, because Docker Desktop was not running in this sandbox (Postgres at `localhost:5433` unreachable, `psycopg.ConnectionTimeout`). Confirms the leak/empty-answer fix holds end-to-end; the data-bearing answer content itself is an open follow-up (see `Known_Issues.md`).
- Command run: `PYTHONUTF8=1 uv run pytest tests/ -q` (T0012.2, full suite minus slow `evals/`)
- Result: `232 passed, 4 subtests passed` (230 pre-existing + 2 new `tests/agents/runtime/test_provider.py` tests).
- Command run: `uv run ruff check src config tests` / `uv run mypy` (T0012.2)
- Result: both clean — `ruff` all checks passed; `mypy` unchanged at the same 3 pre-existing residuals (`checkpointer.py:25`, `middleware.py:48`, `query_clean_jobs.py:41`), no new errors.
- Command run: `uv run python -c "..."` checking PyPI's `deepeval` release list (T0012.3, Step A check)
- Result: latest published release is `4.0.7` (the pinned version) — no patch release exists to fix the template bug; Step A ruled out, proceeded to Step B.
- Command run: `PYTHONUTF8=1 uv run python -c "from evals.harness import seam1_metrics, seam2_metrics, seam3_metrics; print([type(m).__name__ for m in seam1_metrics()+seam2_metrics()+seam3_metrics()])"` (T0012.3)
- Result: `['ToolCorrectnessMetric', 'GEval', 'GEval', 'GEval', 'FaithfulnessMetric', 'GEval']` — neither `ArgumentCorrectnessMetric` nor `TaskCompletionMetric` present.
- Command run: `PYTHONUTF8=1 uv run pytest evals/test_goldens_load.py evals/test_judge_scaffold.py -q` (T0012.3)
- Result: `3 passed`.
- Command run: `uv run pytest evals/test_writeback.py -q` (T0012.3)
- Result: `6 passed`.
- Command run: `uv run pytest evals/ -q --collect-only` (T0012.3)
- Result: `33 tests collected`, no import errors.
- Command run: `docker compose up -d postgres` + `uv run pytest evals/fixtures/test_fixture_counts.py -q` (T0012.3, confirming the eval fixture DB, not run against live goldens)
- Result: `7 passed` — fixture DB reachable and correctly seeded; live `evals/test_three_seams.py` was deliberately **not** run this session to avoid Groq/Gemini API spend (see the T0012.3 completion entry above).
- Command run: `uv run pytest tests/agents/runtime/test_react_agent.py tests/agents/test_service.py tests/api/test_query.py -v` (T0012.4)
- Result: `14 passed`.
- Command run: `uv run pytest tests/ -q` (T0012.4, full non-eval suite)
- Result: `232 passed, 4 subtests passed` — one additional pre-existing test (`tests/agents/runtime/test_memory.py::GeneratedSessionIdTests`) also pinned the old runtime-return shape and needed the same `trace_url` key added to its mock, beyond the tests the ticket prompt named.
- Command run: `uv run ruff check src tests` / `uv run mypy` (T0012.4)
- Result: `ruff` all checks passed; `mypy` unchanged at the same 3 pre-existing residuals (`checkpointer.py:25`, `middleware.py:48`, `query_clean_jobs.py:41`), no new errors.
- Command run: manual verification one-liner constructing a real `AgentRuntime` around a fake agent returning `{"messages": []}`, driven through `generate_agent_response` (T0012.5)
- Result: printed `True` — `result["answer"] == FALLBACK_ANSWER`, confirming the empty-messages path degrades to the `200` fallback instead of raising.
- Command run: `uv run pytest tests/agents/runtime/test_react_agent.py tests/agents/test_service.py tests/api/test_query.py -v` (T0012.5)
- Result: `18 passed`.
- Command run: `uv run pytest tests/ -q` (T0012.5, full suite)
- Result: `236 passed, 4 subtests passed`.
- Command run: `uv run ruff check src tests` / `uv run mypy` (T0012.5)
- Result: `ruff` all checks passed; `mypy` unchanged at the same 3 pre-existing residuals (`checkpointer.py:25`, `middleware.py:48`, `query_clean_jobs.py:41`), no new errors.
- Command run: `uv run python -c "from src.agents.tools.query_clean_jobs import _content_to_text; print(...)"` (T0012.6, coercion proof)
- Result: two `True` lines — list-content flattening and the unchanged `str` fast path.
- Command run: `uv run pytest tests/agents/tools/test_query_clean_jobs.py -q` (T0012.6)
- Result: `11 passed` (8 pre-existing + 3 new).
- Command run: `uv run pytest -q --ignore=evals` (T0012.6, full suite excluding live-network eval tests)
- Result: `239 passed, 4 subtests passed`.
- Command run: `uv run ruff check .` (T0012.6)
- Result: `All checks passed!`
- Command run: `uv run mypy` (T0012.6)
- Result: `Found 2 errors in 2 files` — `checkpointer.py:25` and `middleware.py:48` remain; the `query_clean_jobs.py:44` union-attr residual is resolved (down from 3).
- Command run: `PYTHONUTF8=1 uv run pytest -q` (T0012.7, before → after, plain suite)
- Result: before this ticket the plain suite collected and ran all 272 tests (including 1 live judge call + 17 live seam cases); after adding the `eval` marker + `addopts`, `254 passed, 18 deselected, 4 subtests passed` — the 18 deselected are exactly the live judge test (1) and the 17 `test_three_seams` parametrizations.
- Command run: `uv run pytest -m eval --collect-only -q` (T0012.7)
- Result: `18/272 tests collected (254 deselected)` — lists exactly `evals/test_judge_scaffold.py::test_judge_scaffold` and `evals/test_three_seams.py::test_three_seams[A1..E2]` (17 ids), nothing from `tests/`.
- Command run: `uv run pytest -m eval --collect-only -q 2>&1 | grep -i "PytestUnknownMarkWarning"` (T0012.7)
- Result: no match — marker registered cleanly, no warning.
- Command run: `uv run pytest -q --strict-markers` (T0012.7, hardening check before baking `--strict-markers` into `addopts`)
- Result: `254 passed, 18 deselected, 4 subtests passed` — full suite stays green, so `--strict-markers` was added to `addopts`.
- Command run: `PYTHONUTF8=1 uv run deepeval test run evals/test_three_seams.py --collect-only -q` (T0012.7, deepeval passthrough check, no `-m eval`)
- Result: "No test cases found, please try again" — confirms `addopts`' `-m 'not eval'` deselects the eval tests under `deepeval test run` too, same as plain pytest.
- Command run: `PYTHONUTF8=1 uv run deepeval test run evals/test_judge_scaffold.py -m eval` (T0012.7, deepeval passthrough check, with the override)
- Result: `1 total tests`, `Pass Rate: 0.0%` (failed on `score=None`/no judge response — no judge credentials in this sandbox) — confirms the test was actually **selected and executed**, not deselected; `-m eval` is the verified working form.
- Command run: `uv run ruff check .` / `uv run mypy` (T0012.7)
- Result: `ruff` all checks passed; `mypy` unchanged at the same 2 pre-existing residuals (`checkpointer.py:25`, `middleware.py:48`), no new errors (`evals/` is outside `[tool.mypy] files = ["src"]`).
- Command run: `uv run pytest tests/agents/tools/test_query_clean_jobs.py -v` (T0012.8)
- Result: `10 passed` (7 unchanged `QueryCleanJobsToolTests` + 3 converted `GenerateSqlContentCoercionTests`; the thread-offload test is removed, not skipped).
- Command run: `uv run pytest` (T0012.8, full standard suite)
- Result: `253 passed, 18 deselected` (18 = the unchanged eval-marked tests from T0012.7).
- Command run: `uv run mypy src` (T0012.8)
- Result: `Found 2 errors in 2 files` — same pre-existing residuals as before this ticket (`checkpointer.py:25`, `middleware.py:48`); confirmed identical via `git stash`/re-run. No new errors from the coroutine typing.
- Command run: `grep -n "to_thread" src/agents/tools/query_clean_jobs.py` / `grep -n "async def generate_sql" src/agents/tools/query_clean_jobs.py` (T0012.8)
- Result: one `to_thread` hit (`execute_validated_sql`, line 95, unchanged); one `async def generate_sql` hit.
- Command run: `uv run pytest -q` (T0012.9, verification pass, Docker Desktop not running in this sandbox)
- Result: `246 passed, 7 skipped, 18 deselected, 4 subtests passed` — the 7 skips are `evals/fixtures/test_fixture_counts.py`'s own reachability guard (`internhunter_eval` Postgres unreachable, port 5433), not a regression; standard suite otherwise green.
- Command run: `uv run ruff check .` / `uv run mypy` (T0012.9)
- Result: `ruff` all checks passed; `mypy` unchanged at the same 2 pre-existing residuals (`checkpointer.py:25`, `middleware.py:48`), no new errors.
- Command run: `uv run python -c "from src.api.app import app; ..."` (T0012.9, confirms nothing imports the deleted `main.py`)
- Result: imports cleanly, `FastAPI` app object returned.

## Known issues
Open known issues, risks, and out-of-scope follow-ups live in their own living register:
see [`Known_Issues.md`](Known_Issues.md). Append there when a ticket uncovers a new one.
Resolved items are archived in [`Resolved_Issues.md`](Resolved_Issues.md) (moved out of the
register so it stays focused on what is still open). A full per-module logic review
(2026-07-02) — bugs, improvement backlog, and doc insights — is captured in
[`Code_Review_Notes.md`](Code_Review_Notes.md); its bugs are logged in `Known_Issues.md`
(open) / `Resolved_Issues.md` (closed).

## Next recommended ticket
Milestone 9 (data ingestion) is closed, and the structured-query-vs-detail split is complete (T0009.10 bounded `query_clean_jobs`, T0009.11 `get_job_details`). Milestone 10 (pre-deploy hardening) is essentially complete through T0010.7. T0011.1 (judge spike + harness scaffold), T0011.2 (eval fixture DB + golden dataset), T0011.3 (three-seam instrumentation + metric stack), and T0011.4 (Langfuse score writeback) are all closed: the judge is picked, `internhunter_eval` is seeded and pinned, the 17-case golden dataset loads, `evals/harness.py` + `evals/test_three_seams.py` run the agent end-to-end and score every seam, and `evals/writeback.py` attaches every score onto the same Langfuse trace as the raw agent run. T0011.6 (Gemini judge provider) is also closed, plus its rate-limit follow-up (judge RPM throttle, now formally T0012.1). T0012.2 (qwen `<think>` leak fix), T0012.3 (`deepeval` `ArgumentCorrectnessMetric`/`TaskCompletionMetric` template-bug fix), T0012.4 (populate `trace_url`, closing C4), T0012.5 (graceful empty-answer fallback, closing the remaining [MED] item), T0012.6 (coerce non-str model content in `generate_sql`, closing the last pre-existing mypy residual on `query_clean_jobs.py`), T0012.7 (`eval` pytest marker, closing the T0011.1/T0011.6 plain-suite live-network findings), and T0012.8 (native-async `generate_sql`, closing the last "Query tooling & SQL safety" finding) are all now closed — Milestone 12 (Hardening) is complete. Seam-1/seam-3 scores are no longer blanked by the deepeval bug, both hard prerequisites for T0011.5 are cleared, the API response's `trace_url` field is a real Langfuse URL when tracing is enabled, an empty/unreadable agent answer now returns `200` + `FALLBACK_ANSWER` instead of a `500`, `generate_sql` no longer risks an `AttributeError` on a list-content model reply, `uv run pytest` no longer makes a live Groq/Gemini call or takes several minutes, and `generate_sql` awaits the Groq model natively instead of parking a thread-pool worker per SQL-gen round-trip. Two follow-ups remain open from T0012.2/T0012.3 (see `Known_Issues.md`): the full live A3/C3 data-answer re-check from T0012.2 (Docker wasn't running in that sandbox), and a one-golden live spot-check of the new "Argument Correctness"/"Task Completion" GEval scores from T0012.3 (deliberately skipped this session to avoid API spend). Two low-priority follow-ups from T0012.7 are also logged: `evals/conftest.py`'s `DATABASE_URL` redirect still fires at collection time regardless of the marker, and `deepeval test run` requires an explicit `-m eval` passthrough to select the live tests. **Recommended next: T0011.5** (threshold calibration + baseline report) — both hard prerequisites are now cleared, so this can proceed. **Ingestion Deploy Readiness is renumbered T0013 (deferred, sequenced after T0012)**, its full design captured in `research/deployment-research-plan.md` §4.1–§4.2, to be ticketed once the evaluation baseline lands.

Other future phases (resume/embedding retrieval, charts, typed error contract) still need tickets authored against `Full_Design_Document.md` / `MVP_Spec.md` §6 before implementation.
