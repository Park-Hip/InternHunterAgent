# Resolved Issues & Fixes

Archive of issues, risks, and follow-ups from `Known_Issues.md` that have been
**resolved**. Split out of the living register so `Known_Issues.md` holds only genuinely
open items. Detailed resolution records are intentionally preserved for future reference,
grouped under the same category headers as the register so cross-references still resolve.

`Known_Issues.md` links here for closed items; **do not delete entries from this file.**

## Entry format
Each entry leads with a **`[SEVERITY · RESOLVED · Ticket, date]` bold headline**, then the
resolution detail and a `Verified:` line where relevant. Severity is carried over from the
original register entry (omitted where none was assigned).

## Categories
- [Documentation drift](#documentation-drift) — 3
- [Config, startup & deployment](#config-startup--deployment) — 3
- [API layer](#api-layer) — 2
- [Agent runtime & prompts](#agent-runtime--prompts) — 5
- [Data & ingestion / database schema](#data--ingestion--database-schema) — 3
- [Query tooling & SQL safety](#query-tooling--sql-safety) — 4
- [Capacity & performance](#capacity--performance) — 1
- [Evaluation harness](#evaluation-harness) — 10 (T0011.1–T0012.2)
- [Earlier resolved (pre-register)](#earlier-resolved-pre-register--chronological) — 12

---

## Documentation drift
- **`[LOW · RESOLVED · T0020.4, 2026-07-26]` T0020 had no milestone/sub-ticket block in `Tickets.md` while T0020.1–.4 were already referenced across the docs.**
  - **Resolved 2026-07-26, T0020.4:** the `## T0020: Milestone 20 - Reconciliation & Activation` section was authored in `docs/Tickets.md` (inserted after T0019.10, before `## Backlog`), with four `### T0020.x` sub-ticket In/Out-of-Scope blocks — .1 `main` reconciliation (✅), .2 Render deploy branch → `main` (✅), .3 CI merge gate (✅ `f6cbec0`), .4 gated cron-activation (▶ maintainer-gated, runbook artifact). The numbered roadmap and the prose docs are back in step; a reader following `Tickets.md` alone now finds T0020.1–.4 defined. Originally scoped in `research/v1-release-readiness-plan.md` §2 and the `[[v1-release-roadmap-m20-m22]]` memory note; deliberately deferred from T0020.1 (docs-reconciliation only) per its follow-up note.

- **`[RESOLVED · T0014.2, 2026-07-12]` Pre-deploy plan's old 13-column / `job_level`-hidden references reconciled.**
  - The matching open bullet was already absent from `Known_Issues.md` on `fix/known-issues-hardening`, so T0014.2 did not move a live register item. Sibling commit `75bf992` (`feature/t0015.4-v1-scenario-matrix`) reconciled `research/pre-deploy-refinement-plan.md` to the frozen 16-column agent-visible schema (`job_level`, `listing_expires_on`, `created_on` visible; `posted_date`/bookkeeping columns hidden). This archive note records the no-op register sweep and points future readers to the sibling evidence.

- **`[RESOLVED · T0011, 2026-07-04]` Scope clarified: the product is AI/Data jobs broadly, not internships-only.**
  - Decided during T0011 fixture design — the real corpus is ~2% internships (110 of 112 captured VietnamWorks postings are non-internship) and `is_internship` is just one filterable column. `MVP_Spec.md` (§1 Purpose/Vision, §2 capability line, §7 future-data line) broadened to "AI/Data job opportunities (internships included)"; the agent prompt was already broad. Referenced by `MVP_Technical_Design.md` §8.3 and `Tickets.md` T0011.2 (eval fixture is ~5/22 internships, matching reality).

## Config, startup & deployment
- **`[RESOLVED · T0014.1, 2026-07-12]` Import-time config loading made startup fragile.**
  - `src/core/config.py` no longer runs `settings = load_settings()` at import; it resolves `.env` and all four YAMLs from the repo root, wraps missing/invalid env or YAML in a clear `ConfigLoadError`, and exposes a lazy `settings` proxy so existing `settings.*` call sites still work after startup. `src/core.db` made lazy for the same reason (avoids an import-time `DATABASE_URL` crash via SQLAlchemy engine construction). FastAPI `lifespan` calls `load_settings()` first, so startup fails fast with an actionable config error instead of an opaque `ImportError`.

- **`[RESOLVED · T0012.9, 2026-07-06]` `main.py` placeholder removed.**
  - `main.py` was only a `print("Hello…")` placeholder — dead code, not the entrypoint. Deleted, and `COPY main.py ./` removed from `docker/Dockerfile`; confirmed nothing imports it and `CMD` still runs `uvicorn src.api.app:app`. No behavior change.

- **`[HIGH · RESOLVED · 2026-07-04]` Agent LLM `llama-3.3-70b-versatile` being retired by Groq** (time-boxed).
  - `config/settings.yaml:4` now pins `agent.groq.model: qwen/qwen3.6-27b` (chosen over `openai/gpt-oss-120b`, which has reported tool-calling regressions on Groq — LangChain #34155 — kept only as the *judge* model where no tool calls happen). The retired `llama-3.3-70b-versatile` (Groq deprecated 2026-06-17, shutdown 2026-08-16) is no longer referenced. Background: `research/deepeval-sql-agent-eval-planning.md` §11.4/§11.7 (F1).
  - **Residual:** live-validation of the qwen pin remains tracked in `Known_Issues.md`.

## API layer
- **`[RESOLVED · T0012.4, 2026-07-06]` `trace_url` always returned `None` in `src/agents/service.py`.**
  - `AgentRuntime.ainvoke` now resolves `trace_url` via `Langfuse.get_trace_url(trace_id=...)` and `service.py` passes it through unchanged (still no Langfuse import in the API/service layer). `trace_url` is `None` when tracing is disabled, `trace_id` is absent, or `get_trace_url` returns `None` (C4).

- **`[MED · RESOLVED · T0012.5, 2026-07-06]` Empty agent answer still returned a 500; the fallback guard was effectively dead.**
  - `react_agent._extract_answer` now returns `""` in all three previously-raising branches (non-dict response, missing/empty messages, non-str/empty/whitespace final content) instead of raising `ValueError`. `service.py`'s existing `if answer is None or not answer.strip()` guard now actually fires, coercing `""` to `FALLBACK_ANSWER` — a `200` instead of the generic `500` in `query.py`. No change to `service.py`/`query.py`. Detail: `Code_Review_Notes.md` doc-insight 3.

## Agent runtime & prompts
- **`[HIGH · RESOLVED · 2026-07-15]` `generate_sql` returned empty content when qwen spent the whole `max_tokens` budget on hidden reasoning.**
  - `AgentProvider.build_model(...)` now accepts a per-call `reasoning_effort` override and only forwards it to `ChatGroq(...)` when the caller supplies one, so the default ReAct-agent path remains unchanged. `config/settings.yaml` records `agent.query.sql_generation_reasoning_effort: "none"`, and `query_clean_jobs.generate_sql()` reads that setting before building the hidden SQL-generation model. This fixes the diagnosed reasoning-heavy query failure where "List the AI Engineer jobs that require Python, sorted by salary descending." previously produced empty SQL because qwen burned all 2048 output tokens on hidden reasoning.
  - **Verified:** `uv run pytest tests/agents/runtime/test_provider.py tests/agents/tools/test_query_clean_jobs.py -q` passed (`15 passed`). Live Groq/manual eval confirmation still needs maintainer credentials and a seeded DB.
- **`[LOW · RESOLVED · T0013.5, 2026-07-11]` Freeze-guard needed the `job_level` visibility flip.**
  - `tests/agents/runtime/test_prompts.py` now freezes the enriched 16-column visible set and asserts `job_level` is present in `schema_context` and the system-prompt available-fields line, while hidden columns remain excluded.

- **`[LOW · RESOLVED · T0013.5, 2026-07-11]` Freeze-guard must count `listing_expires_on` as agent-visible.**
  - The prompt guard now asserts `listing_expires_on` is present in the frozen visible set and keeps `posted_date`, `external_id`, and hidden `source` out of the guarded prompt column surfaces.

- **`[LOW · RESOLVED · T0013.5, 2026-07-11]` Freeze-guard must count `created_on` as agent-visible.**
  - The prompt guard now includes `created_on` in the frozen visible set, matching the T0013.4 C1 freshness path, and `docs/Schema_Contract.md` records it as part of the v1 schema contract.

- **`[RESOLVED · T0012.6, 2026-07-06]` `response.content.strip()` assumed string content** (mypy-flagged, 2026-07-02 audit).
  - `src/agents/tools/query_clean_jobs.py:41` called `.strip()` on `model.invoke(...).content`, typed `str | list[...]` — a list-content reply (structured/tool blocks) would raise `AttributeError`. `generate_sql` now runs `response.content` through a private `_content_to_text` helper (flattens `str` unchanged; joins `{"text": ...}` blocks for list content; unrecognized blocks contribute nothing) before `.strip()`. The `str` fast path is byte-identical. mypy's union-attr residual on this line is gone (3 → 2).

## Data & ingestion / database schema
- **`[LOW · RESOLVED · T0012.9, 2026-07-06]` Stale comment in `normalize/vietnamworks.py`.**
  - Found 2026-07-04: the `posted_date = None` comment (~line 99) cited a defunct T0009.8 ticket and implied a pending parse step. The comment now cites the reliability decision (VietnamWorks surfaces no reliable published date; `onlineOn`/`approvedOn`/`expiredOn` each mean something other than "first posted") and the future ingestion-owned `first_seen_at`/`listed_on` direction gated on T0014, cross-referencing the register and `research/job-site-comparison.md` §122. Comment-only change.

- **`[MED · RESOLVED · T0010.6, 2026-07-02]` `normalize_location` only matched on an exact full-string lookup.**
  - `normalize_location` did `city_alias_map.get(lower)` against the whole address string, so a known city embedded in a free-form address (`"12 Nguyen Hue, District 1, Ho Chi Minh City"`) never canonicalized and fell through to `"Other"`. Now each alias key is matched against every source as a `\b`-anchored, case-insensitive regex, so a city occurring anywhere in the text is recognized while short aliases (`hn`, `hcm`) still can't match inside unrelated words (`john`, `technology`). Multiple distinct canonical cities are returned in first-appearance order, deduped as before.
  - **Verified:** new `tests/services/ingestion/test_transform.py::NormalizeLocationTests` (free-form address, short-alias-inside-address, short-alias-false-positive-guard, multi-city order, dedup) + existing `test_normalize_vietnamworks.py` location tests. Detail: `Code_Review_Notes.md` bug 6.

- **`[LOW · RESOLVED · 2026-07-02]` `replace_clean_jobs` would crash on intra-batch duplicate keys** (latent).
  - `INSERT … ON CONFLICT DO UPDATE` errored if the same `(source, external_id)` appeared twice in one batch. `replace_clean_jobs` now dedups `rows` by `(source, external_id)` (last-write-wins) before the insert, and the returned count reflects the deduped rows. Verified: `tests/services/ingestion/test_clean_store.py::ReplaceCleanJobsTests::test_intra_batch_duplicate_key_is_deduped_last_wins`. Detail: `Code_Review_Notes.md` bug 8.

## Query tooling & SQL safety
- **`[HIGH · RESOLVED · T0010.3, 2026-07-02]` SQL validator did not enforce a single table.**
  - Previously only checked `"clean_jobs" in statement.lower()` (substring presence), so a query that also referenced another table passed (e.g. `... FROM clean_jobs JOIN raw_jobs USING (source, external_id)`). Now masks string-literal contents, then requires every `FROM`/`JOIN` reference to equal `clean_jobs` and rejects a comma-separated `FROM` list; a bare `SELECT 1` (no table) remains valid. The string-literal masking was later reused to fix the denylist-keyword false-positive class (bug 4). Detail: `Code_Review_Notes.md` bug 1.

- **`[MED-HIGH · RESOLVED · T0010.4, 2026-07-02]` Blocking LLM call on the async event loop.**
  - `query_clean_jobs` (async) offloaded the DB call via `asyncio.to_thread` but ran `generate_sql`'s `model.invoke(...)` synchronously on the loop, so each Groq SQL-gen round-trip blocked every concurrent request and the health probe. Now `sql = await asyncio.to_thread(generate_sql, question)` — scheduling-only, generated SQL unchanged. Detail: `Code_Review_Notes.md` bug 2. (Superseded by the T0012.8 native-async change below.)

- **`[MED · RESOLVED · T0010.5, 2026-07-02]` "Showing N of M" could understate the true match count.**
  - `table_formatter.format_rows` set `row_count = len(rows)` — already capped by whatever `LIMIT` the *model* wrote — so when the model's `LIMIT` was below the real match count, the tool reported "Found N result(s)" as if N were the total and never surfaced a truncation notice. Fixed the Option-A way (fetch bound now system-owned): `query_clean_jobs` rewrites validated SQL via `enforce_fetch_limit` to fetch `agent.query.max_rows + 1` rows regardless of any model `LIMIT`/`OFFSET`, and `format_rows` uses the +1 row as a truncation sentinel (`TableArtifact.truncated`). The answer says "Showing the first N results — there are more matches…" when truncated, and "Found N result(s)" only when N is genuinely complete; no exact total is computed for list queries (rejected Option B: a separate `COUNT(*)`). Scalar/`COUNT(*)` queries unaffected.
  - **Verified:** `tests/services/query/test_row_bound.py`, updated `test_table_formatter.py` + `test_query_clean_jobs.py`. Detail: `Code_Review_Notes.md` bug 5.

- **`[LOW · RESOLVED · T0012.8, 2026-07-06]` Nested SQL-generation call used thread-offloaded sync `invoke`, not native async.**
  - `generate_sql` is now `async def` and calls `await model.ainvoke(...)` directly; `query_clean_jobs` calls `await generate_sql(question, config)` with no thread hop. The `execute_validated_sql` `asyncio.to_thread` offload (genuinely-sync DB work) is unchanged. Scheduling-only — the generated SQL, prompt, and model are byte-for-byte the same. `test_generate_sql_runs_off_the_event_loop_thread` was removed (it asserted the old thread-offload behavior this fix eliminates); `GenerateSqlContentCoercionTests` converted to `IsolatedAsyncioTestCase` with `fake_model.ainvoke = AsyncMock(...)`.

## Capacity & performance
- **`[LOW · RESOLVED · 2026-07-02]` Per-request `client.flush()` on the event loop.**
  - `react_agent.ainvoke` flushed the Langfuse client synchronously on every request — blocking I/O on the async path that stalled concurrent requests. Now offloaded via `await asyncio.to_thread(client.flush)`, matching the existing `asyncio.to_thread(...)` pattern; per-request flush semantics preserved, it just no longer blocks the event loop. Detail: `Code_Review_Notes.md` bug 7.

## Evaluation harness

### T0011.1
- **`[RESOLVED · T0012.9, 2026-07-06 — obsolete]` `gpt-oss-120b` GEval score looked low relative to its reasoning.**
  - Observed during the spike: the probe returned `score=0.1` even though the model's own `reason` text was fully positive. Struck as obsolete — the judge moved from Groq `gpt-oss-120b` to Google `gemini-2.5-flash` in T0011.6, so this Groq-judge scoring quirk no longer applies to the shipping harness.

### T0011.2
- **`[LOW · RESOLVED · T0012.9, 2026-07-06]` Fixture `job_level` was NULL on all 22 rows, but production populates it.**
  - Found 2026-07-04: `seed_eval_db.sql` left `job_level` NULL on every row, diverging from the live pipeline's five-value taxonomy. All 22 rows now carry a real value mirroring the corpus distribution — 5 internship rows → `Intern/Student`; remaining 17 → `Experienced (non-manager)` (14), `Manager` (2), `Fresher/Entry level` (1). No golden pin depends on `job_level` (the C6 seniority-honesty probe rests on the column being omitted from `schema_context`), so all 22 goldens still hold.

- **`[LOW · RESOLVED · T0012.9, 2026-07-06]` Fixture used `source='fixture'` + `external_id='fixture-NNN'`, not the real `source='vietnamworks'` + integer IDs.**
  - All 22 rows now use `source='vietnamworks'` and `external_id='vnw-eval-NNN'` — a truer production mirror while keeping an eval marker (the structured columns are engineered to hit the golden pins and don't match a real posting's values). No golden pin depends on either value, so all 22 goldens still hold.

### T0011.3
- **`[HIGH · RESOLVED · T0012.2, 2026-07-04]` Agent model `qwen/qwen3.6-27b` leaked raw `<think>...</think>` reasoning into message `.content`.**
  - Found running the live harness against real Groq. Both the nested `generate_sql` LLM span's output and, on some turns, the agent's own final synthesis message came back with raw chain-of-thought inline in `.content`. Two symptoms: (a) the "SQL" `generate_sql` returns is sometimes the entire reasoning transcript, not a bare `SELECT`; (b) on ≥2 live goldens (A3, C3) the agent's final answer came back empty. Both root causes detailed in the T0012.2 entry below.

- **`[MED · RESOLVED · T0012.3, 2026-07-06]` `deepeval==4.0.7`'s `ArgumentCorrectnessMetric` and `TaskCompletionMetric` are broken for this project's use.**
  - Both raised `MetricTemplateInterpolationError` from internal Jinja templates — `ArgumentCorrectnessMetric` on `'stringified_tools_called' is undefined` whenever `tools_called` was non-empty, `TaskCompletionMetric` on `'tools_called_formatted' is undefined` unconditionally. Checked PyPI first — `4.0.7` is still the latest release, so no pin fixes it; a version bump was out of scope (risk to `deepeval.integrations.langchain`/`trace_test_manager` internals). Resolved by replacing both with `GEval` substitutes in `evals/harness.py`: seam-1 `ArgumentCorrectnessMetric` → `GEval("Argument Correctness")` using `INPUT`/`ACTUAL_OUTPUT`/`TOOLS_CALLED`; seam-2's `ArgumentCorrectnessMetric` dropped (seam 2 already has a strong `GEval("SQL Schema Quality")`); seam-3 `TaskCompletionMetric` → `GEval("Task Completion")` using `INPUT`/`ACTUAL_OUTPUT`/`RETRIEVAL_CONTEXT`.
  - **Verified:** import smoke test + existing `test_goldens_load.py`/`test_judge_scaffold.py`/`test_writeback.py` (all pass). Live golden scoring deliberately skipped to avoid API spend. Follow-up: one live spot-check before T0011.5 calibrates thresholds.
  - **Confirmed upstream — a deepeval packaging bug, not our test-case construction.** The metric's Python passes render kwarg `tools_called` but its own bundled template references `{{ stringified_tools_called }}`, and `_get_prompt(..., strict=True)` renders with Jinja `StrictUndefined`, so the mismatch raises instead of blanking; `stringified_tools_called` is assigned nowhere. `TaskCompletionMetric` is the same defect with `tools_called_formatted`. Reported as `confident-ai/deepeval#2817`/`#2807`; fix PRs `#2820`/`#2808`/`#2809` open but unreleased as of 2026-07-06. Follow-up: once a release ships those fixes, consider reverting to the premade metrics.
  - **Behavior caveat — the GEval substitutes are equivalent in *intent*, not *scoring*.** A `GEval` judges in a single pass from our criteria + the params we list, whereas the premade metrics run fixed multi-step algorithms — notably the real `TaskCompletionMetric` reads the full agent trace, while our `GEval("Task Completion")` judges only from `input` + final `actual_output` + the tool's `retrieval_context`. Consequences: (a) scores aren't comparable to deepeval's published benchmarks; (b) seam-3 completion is judged on the final answer, not the whole trace. Acceptable for the internal T0011.5 baseline; revisit if trace-level completion scoring is later needed.

- **`[RESOLVED · T0011.6, 2026-07-05]` Move the judge to Google (Gemini) to break the double-Groq-load.**
  - `eval.judge.provider`/`model` now default to `google`/`gemini-2.5-flash`; `evals/judge.py::build_judge()` dispatches on `provider` (`groq` unchanged, new `google` branch using `ChatGoogleGenerativeAI`, fields verified against `langchain-google-genai==4.2.6`). `GOOGLE_API_KEY: str | None = None` added to `Settings` (optional — boot/tests unaffected without it). Groq path verified byte-identical by flipping `provider: groq` back.

- **`[RESOLVED · 2026-07-05]` Moving the judge to Gemini alone didn't remove the judge-side rate limit.**
  - Gemini's own free-tier judge budget (~10 RPM per third-party trackers — Google no longer publishes a static table) is still well under the harness's ~119 sequential judge calls for 17 goldens, so the judge alone could 429-storm even off Groq. Added a client-side sliding-window throttle (`evals/judge.py::_RpmThrottle`, applied in `DeepEvalJudge.generate`/`a_generate`) driven by `eval.judge.rpm: 8`. Groq's agent-side budget has enough headroom to skip a default throttle (`rpm: 0` disables it; the key works for either provider). Verified via a `_RpmThrottle` unit check (3rd call in a 2-RPM window waits ~60s) — see `Manual_Verification_Guide.md` → T0011.6.

### T0011.6
- **`[RESOLVED · T0011.6, 2026-07-05]` Gemini judge truncated its JSON because `gemini-2.5-flash` is a "thinking" model.**
  - Found running `test_judge_scaffold.py` live: the first call returned a transient `429 RESOURCE_EXHAUSTED` (free-tier burst, cleared within a minute), then reliably raised `ValueError: Evaluation LLM outputted an invalid JSON` — raw output cut off mid-JSON. Root cause: the model spends part of `max_tokens` on internal reasoning before the visible answer, and the Groq branch's `max_tokens=1024` was too small once the JSON also carries GEval's `"steps"` array. Fixed in the `google` branch by raising `max_tokens` to `4096`; confirmed via 3 consecutive live passes. Groq branch untouched.

- **`[LOW · RESOLVED · T0012.7, 2026-07-06]` `test_three_seams.py` made a full plain `pytest evals/` run take several minutes.**
  - `evals/test_three_seams.py` now carries `pytestmark = pytest.mark.eval`, so all 17 parametrized cases are deselected from plain `uv run pytest` by default (`-m 'not eval'`); select them with `-m eval` or `deepeval test run evals/test_three_seams.py -m eval`.

### T0012.2
- **`[HIGH · RESOLVED · T0012.2, 2026-07-06]` qwen `<think>` reasoning leak — two distinct root causes, both fixed** (closes the T0011.3 HIGH entry above).
  - Confirmed live against real Groq that the leak had two separate causes, not one.
  - **(a) SQL-span leak:** `generate_sql`'s raw response was the entire chain-of-thought (verified live: 4166-char `<think>...</think>`, no bare `SELECT`). Root cause: `ChatGroq`/`langchain-groq==1.1.2` inlines qwen's reasoning into `.content` by default. Fixed by forwarding `agent.groq.reasoning_format: hidden` into `ChatGroq(...)` in `provider.py::build_model()` (None-safe). Post-fix, `generate_sql("Which companies have AI Engineer roles?")` returns bare `SELECT id, company FROM clean_jobs WHERE role ILIKE '%AI Engineer%'`.
  - **(b) Empty final-answer symptom (A3/C3) is a *different* bug:** `reasoning_format='hidden'` alone reproduced it — at the old `max_tokens=1024`, a direct `model.invoke(...)` returned `content=''` with `output_tokens=1024, reasoning=1024`, i.e. reasoning consumed the entire budget before any visible answer. Same root cause as T0011.6's Gemini truncation — a thinking model's `max_tokens` must cover reasoning *and* answer. Fixed by raising `agent.groq.max_tokens` 1024 → 2048; confirmed non-empty coherent `.content` and clean bare SQL.
  - **Live end-to-end only partially verified:** Docker Desktop wasn't running, so Postgres (`localhost:5433`) was unreachable — A3/C3 final answers came back as a graceful, non-empty, `<think>`-free "database error" message (proving the fix holds through the full ReAct pipeline), but data-bearing answer content wasn't confirmed against real rows. Follow-up: re-run `test_three_seams.py -k "A3 or C3"` once Docker/Postgres is up.
  - **Not adopted:** the ticket's fallback of swapping `generate_sql` to a smaller non-thinking model — the provider-level `reasoning_format`/`max_tokens` levers resolved both symptoms in two config lines, so the swap (which would change what seam 2 measures for the T0011.5 baseline) was unnecessary.

## Earlier resolved (pre-register / chronological)
- **`[MED · RESOLVED · T0010.7, 2026-07-02]` Explicit user-requested counts were silently overridden by the system cap.**
  - T0010.5 made the fetch bound fully system-owned by stripping *any* model-written `LIMIT`, which fixed the "Found 20" honesty bug but also discarded a genuine user-requested count ("top 3" always returned up to `max_rows` with a truncation notice). Fixed by making `LIMIT` a trustworthy signal of explicit intent: `config/prompts.yaml` `sql_generation` now tells the model to add `LIMIT` only when the user explicitly asked for a count. `enforce_fetch_limit` is replaced by `resolve_bounds(sql, max_rows) -> FetchBounds`, which honors a trailing `LIMIT` exactly when `<= max_rows` (no truncation notice) else falls back to the `max_rows + 1` sentinel with `display_cap = max_rows`. Scalar/`COUNT(*)` unaffected. Verified via rewritten `test_row_bound.py` + a new honored-count test. (The deferred "more may match" hint on an honored count remains open in `Known_Issues.md`.)

- **`[RESOLVED · T0010.1, 2026-07-02]` Unhandled `None` answer collapsed into an opaque 500** (C1, mypy-flagged).
  - `src/agents/service.py` now types its return as a local `AgentResponse` TypedDict (`answer: str`, not `str | None`) and coerces a `None`/empty/whitespace-only runtime answer into `FALLBACK_ANSWER` before it reaches `QueryResponse`. Verified: `uv run mypy` no longer reports the union error; `tests/api/test_query.py::GenerateAgentResponseTests` covers `None` and whitespace-only answers.

- **`[RESOLVED · T0010.1, 2026-07-02]` All exceptions collapsed into the same generic 500** (C5).
  - `src/api/routes/query.py` now raises `InvalidQueryError` (`src/core/errors.py`) for a blank/whitespace-only `payload.query` and maps it to `400 "Query must not be empty."` before `generate_agent_response` is called; genuine internal failures still fall through to the existing `500 "Failed to process query"` with the `query.failed` log intact and no internals leaked. Verified via `test_query_route_returns_400_for_blank_query` (asserts the service isn't awaited) + existing `test_query_route_returns_500_when_service_fails`.

- **`[RESOLVED · 2026-07-02]` Large uncommitted pile vs. "completed" record.**
  - The T0009.3–T0009.11 work plus the pre-deploy audit (previously all uncommitted on top of `199dceb feat(T0009.2)`) were committed as three coherent commits on `feature/t0009.11-job-detail-tool`: `efb8ac7 feat(T0009.3-.9)`, `171da99 feat(T0009.10-.11)`, `ce68925 chore: pre-deploy audit`. Working tree clean; history matches the `Repo_Current_State.md` completed-ticket record.

- **`[RESOLVED · 2026-07-02]` Pre-deploy audit batch 1: endpoint drift + doc drift + lint + static-analysis setup.**
  - (a) **API endpoint drift:** docs said `POST /api/v1/agent/chat` but the route was `/agent/query`; renamed to `/agent/chat` (owner decision — "chat" is canonical for the coming UI) and updated `test_query.py`, `MVP_Technical_Design.md`, `Manual_Verification_Guide.md`. (b) **Doc drift:** corrected the Langfuse compose path (`infra/langfuse/docker-compose.yaml` → `infra/docker-compose.yaml`) in `Repo_Current_State.md`; added missing runtime deps (`cloudscraper`, `beautifulsoup4`, `lxml`, `httpx`) + dev deps (`ruff`, `mypy`); fixed the stale schema-evolution header in `MVP_Technical_Design.md`. (c) **Static analysis stood up:** added `ruff` + `mypy` (+ `pydantic.mypy`) and `[tool.ruff]`/`[tool.mypy]` config; `ruff check .` passes (7 autofixes, `scripts/` excluded); `mypy` 10 → 3 errors (residuals triaged). All 199 tests pass.

- **`[RESOLVED · 2026-07-02]` Architecture-invariant audit — verified clean by grep.**
  - Nothing in the request path imports `services.ingestion`; `langfuse` is imported only in `agents/tracing/langfuse.py`; the query DTOs (`TableArtifact`/`QueryToolResult`/`QueryRefusal`) never appear outside `tools/` + `services/query/`; `service.py`/`api/` import no LangChain types. The Full_Design layer laws hold in code.

- **`[RESOLVED · 2026-07-01]` Uncommitted stray edit in `query_clean_jobs.py`** (stray bare `1` after `return _build_answer(table)`) — reverted; file now ends cleanly.

- **`[RESOLVED · 2026-07-01]` Stray committed file at repo root** (`s -ExecutionPolicy RemoteSigned…Activate.ps1`) — no longer on disk or in `git ls-files`.

- **`[RESOLVED · 2026-07-01]` Doc drift: `Manual_Verification_Guide.md` pointed at `docker/docker-compose.yaml`** — corrected to `infra/docker-compose.yaml` in both T0003/T0004 steps. (The register had also mis-stated it as `infra/langfuse/docker-compose.yaml`; corrected too.)

- **`[RESOLVED · T0009.8 — no code change]` Empty-fetch guard relies on source not raising** (T0009.6).
  - Verified during T0009.8: `test_clean_store.py` (9 tests) confirms `replace_clean_jobs([])` returns 0 and skips `TRUNCATE`; a code read of `run_ingestion` confirms `list(source.fetch())` raises before either `upsert_raw_postings` or `replace_clean_jobs` runs, so a source exception aborts before any DB write. Behavior already correct.

- **`[RESOLVED · T0009.9, 2026-07]` Live Postgres volume retained a stale pre-T0009 `clean_jobs` schema.**
  - `scripts/init_db.sql` (`CREATE TABLE IF NOT EXISTS`) intentionally stays non-destructive, so it still can't migrate an existing wrong-shape table — but the schema-change path is now explicit: `scripts/reset_db.sql` (`DROP TABLE IF EXISTS clean_jobs, raw_jobs CASCADE;` then `\i scripts/init_db.sql`) replaces the old manual `DROP TABLE`. An MVP-appropriate reset, not a migration framework, because both tables are reproducible (`clean_jobs` rebuilt every run, `raw_jobs` re-fetchable). Alembic deferred — the trigger to revisit is when deployed data becomes genuinely irreplaceable.

- **`[RESOLVED · T0009.10, 2026-07]` Large result sets can exceed the Groq free-tier TPM limit.**
  - Observed during T0009.8. `query_clean_jobs` now enforces the bounded-output law deterministically at the tool boundary: `table_formatter.py` drops any `description` column (case-insensitive) regardless of what was `SELECT`ed, and caps rows at `agent.query.max_rows` (`20`, in `config/settings.yaml`). When capped, the answer states "Showing N of M …" with the true total; small/aggregate results (e.g. `COUNT(*)`) pass through unchanged. Full-description retrieval moved to a bounded `get_job_details(ids)` fetch (T0009.11).
