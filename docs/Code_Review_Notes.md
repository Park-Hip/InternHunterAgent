# Code Review Notes

Per-module logic review of every `src/` module, 2026-07-02 (post-T0009.11, on
`feature/t0009.11-job-detail-tool`). Complements the mechanical pre-deploy audit
(architecture-invariant greps + ruff/mypy) with a **logic read** of each module.

**How findings are split**
- 🐞 **Bugs / correctness risks** → logged in [`Known_Issues.md`](Known_Issues.md); summarized
  here with a pointer.
- 💡 **Improvements / future work / cleanup** → this document (the actionable backlog).
- 📄 **Doc insights** → this document's final section; the ones that touch a *stated
  invariant* are flagged for an owner decision rather than edited unilaterally.

Severity is about real-world impact, not style. Nothing here is auto-fixed (per `CLAUDE.md`
§1 — follow-ups are reported, not fixed inside an unrelated pass).

---

## 🐞 Bugs found (detail — also in Known_Issues.md)

1. ~~**[HIGH] SQL validator does not actually enforce a single table.**~~ **Fixed by T0010.3**
   (2026-07-02): `sql_validator.py` only checked `"clean_jobs" in statement.lower()` — a
   *substring* presence test. A query that also referenced another table passed, e.g.
   `SELECT * FROM clean_jobs JOIN raw_jobs USING (source, external_id)` or
   `SELECT ... FROM clean_jobs, raw_jobs ...`. `JOIN`/`,` were not denylisted, so the agent
   could read `raw_jobs` (verbatim JSONB payloads) or any other table alongside `clean_jobs`.
   This **contradicted the stated invariant** in `Full_Design_Document.md` §6 ("The SQL
   validator allowlists the *table* `clean_jobs`") and §3's curated-schema boundary.
   The `SET TRANSACTION READ ONLY` in `executor.py` still prevented writes, so this was a
   *read-scope* escape, not a write hole — but it defeated the "agent only sees the curated
   `clean_jobs` columns" guarantee. Now fixed: string-literal masking + a `TABLE_REF_PATTERN`
   check requires every `FROM`/`JOIN` table reference to equal `clean_jobs`, and a
   comma-separated `FROM` list is rejected outright. Detail: `Known_Issues.md`.

2. ~~**[MED-HIGH] Blocking LLM call on the async event loop.**~~ **Fixed by T0010.4**
   (2026-07-02): `query_clean_jobs` is `async`, and it correctly offloads the DB call via
   `asyncio.to_thread(execute_validated_sql, …)` — but `generate_sql(question)` ran
   `model.invoke(...)` **synchronously on the event loop**. That Groq round-trip
   (seconds) blocked *every* concurrent request and the health probe for its duration.
   Now `sql = await asyncio.to_thread(generate_sql, question)`. Detail: `Known_Issues.md`.

3. **[MED] Ingestion aborts inconsistently on one bad payload.**
   `loader.run_ingestion` upserts `raw_jobs` first, then does
   `[to_normalized_job(p.raw_payload) for p in postings]` with no per-record guard.
   `to_normalized_job` does `payload["jobId"]` (hard key) and constructs a pydantic model,
   so a single malformed record raises → normalization aborts → `replace_clean_jobs` never
   runs. Net state: `raw_jobs` refreshed, `clean_jobs` left stale, no error surfaced to a
   scheduled run beyond a stack trace. Fix: isolate per-record normalization (skip + log
   bad records) so one bad row can't silently desync the two tables.

4. **[MED] Denylist matches keywords inside string literals.**
   `sql_validator` tokenizes the *entire* statement, including the contents of string
   literals, then rejects any token in `DENYLISTED_KEYWORDS`. So legitimate queries are
   refused: `... WHERE description ILIKE '%replace%'`, a company named `Merge`, a title
   containing `call`/`exec`/`grant`, etc. → "Unsafe keyword(s) detected". False-positive
   refusals on valid user questions.

5. **[MED] "Showing N of M" can understate the true match count.**
   `table_formatter.format_rows` sets `row_count = len(rows)` — the count of rows the SQL
   *returned*, not the true number of matches. The prompt tells the model to "always
   include a LIMIT", so when the model's own `LIMIT` (say 20) is below the real match count
   (say 50), the tool reports "Found 20 result(s)" and never shows the "narrow your search"
   notice — implying 20 is the total. The T0009.10 design intent ("carry the true match
   count") isn't fully met because the true count is only knowable via a separate
   `COUNT(*)`, which list queries don't run.

6. **[MED] `normalize_location` only matches on an exact full-string lookup.**
   It lowercases each source and does `city_alias_map.get(lower)` — an *exact* dict-key
   match. A free-form `address` like `"12 Nguyen Hue, District 1, Ho Chi Minh City"` never
   equals an alias key, so it contributes nothing; location canonicalization depends
   entirely on clean `workingLocations[].cityName` values. (This is why the T0009.8
   `cityName` field-name bug made *every* row "Other".) A substring/contains match against
   alias keys would make location far more robust.

7. **[LOW] Per-request `client.flush()` on the event loop.**
   `react_agent.ainvoke` calls the Langfuse client's `flush()` synchronously on every
   request. It's blocking I/O on the async path and defeats Langfuse's batching. Prefer a
   background/periodic flush, or offload it.

8. **[LOW/latent] `replace_clean_jobs` would crash on intra-batch duplicate keys.**
   `INSERT ... ON CONFLICT (source, external_id) DO UPDATE` errors ("cannot affect row a
   second time") if the *same* `(source, external_id)` appears twice in one batch. The
   VietnamWorks source dedups by `jobId`, so it can't happen today — but a future source
   that doesn't dedup would crash the load. Cheap guard: dedup in `replace_clean_jobs`.

---

## 💡 Improvements / future work (by area)

### Query tool & services
- **Dead abstraction:** `QueryToolResult` and `QueryRefusal` (`services/query/models.py`)
  are defined and unit-tested but **never used** by the runtime path — `query_clean_jobs`
  returns a plain string and `TableArtifact` directly. Either wire them in or delete them
  to avoid implying a richer contract than exists.
- **DRY:** `executor.py` and `job_details.py` duplicate the
  `with session_factory(): SET TRANSACTION READ ONLY; execute; mappings().all()` +
  `except (OperationalError, DBAPIError) → ExecutorError` block. Extract a shared
  read-only-query helper.
- **DRY:** the `load_max_rows` / `load_max_detail_ids` / `load_max_messages` config readers
  are three near-identical `settings.config_yaml["agent"][...]` validators. A small typed
  config accessor would remove the triplication (and the risk they drift).
- **Executor hardening:** no `statement_timeout`. A pathological model query (e.g. a
  large unbounded scan within the now-enforced `clean_jobs`-only allowlist, bug 1 fixed by
  T0010.3) could still run long. Consider `SET LOCAL statement_timeout` alongside the
  read-only transaction.
- **Provider churn:** `generate_sql` builds a fresh `AgentProvider()` + `ChatGroq` on every
  call. Harmless but wasteful; a cached model would do.

### Ingestion
- `classify_role` accepts `job_function_children` but never uses it (docstring admits it's a
  "tiebreaker … though first-match-wins covers the current keyword set"). Dead parameter —
  drop it or implement the tiebreaker.
- `find_tech_stack`'s `(?<!\w)…(?!\w)` guard still over-matches single-letter techs across
  non-word boundaries (e.g. tech `R` inside `R&D`). Minor precision issue.
- No per-query resilience in `VietnamWorksSource._post`: `raise_for_status()` on any page
  aborts the whole run. A single 429/5xx on page 3 loses the run. Add per-query
  try/continue (and optionally retry/backoff) for scheduled reliability.
- `loader` uses `print()` for its result; switch to the structlog `logger` for a scheduled
  job.
- ORM `id` columns declare `autoincrement=True` while the DDL uses
  `GENERATED ALWAYS AS IDENTITY`. Functionally fine (inserts omit `id`), but the ORM and
  DDL describe the identity mechanism differently — worth a comment or alignment.
- Batch inserts build one giant `VALUES` (fine at 50 rows; chunk if volume grows).

### Runtime & tracing
- `provider.py` uses `ChatGroq(model_name=…, groq_api_key=…)` — deprecated aliases for
  `model=…`/`api_key=…` (this is the mypy-flagged C3). Works today; update to the canonical
  kwargs to avoid breaking on a `langchain-groq` bump.
- `tracing/langfuse.py`: the `_langfuse = Langfuse(...)` instance is created only for its
  side effect (initializing the global client that `CallbackHandler()`/`get_client()` use)
  and is otherwise unused — add a comment so it isn't "cleaned up" as dead code.
- `get_langfuse_client()` returns `get_client()` even when tracing is disabled; guard it so
  `flush()` is a genuine no-op when there's no configured client.

### API & core
- **No CORS middleware** (`app.py`). The upcoming browser UI will need
  `CORSMiddleware` if it's served from a different origin — flag for the UI/Deploy
  milestone.
- **Health check is shallow** (`routes/health.py` returns a static `{"api": "online"}` and
  a redundant in-body `status_code`). A deploy readiness probe should optionally verify DB
  connectivity. Also `async  def` / `basicConfig(...) ` have stray double-spaces/trailing
  whitespace (cosmetic; ruff excludes none of this — consider enabling formatting).
- **Request validation:** `schemas.QueryRequest.query` has no `min_length`/`max_length`.
  Empty is now caught in the route (good), but a length cap belongs on the schema (and
  guards against oversized inputs).
- `checkpointer._checkpointer_dsn()` derives the psycopg DSN via
  `DATABASE_URL.replace("+psycopg", "")` — works, but a brittle string transform; a parsed
  URL would be safer.

---

## 📄 Doc insights (surface for decision, not auto-edited)

1. ~~**`Full_Design_Document.md` §6 overstates the SQL validator.**~~ **Resolved by T0010.3**
   (2026-07-02): it said the validator "allowlists the *table* `clean_jobs`" and that
   "adding tables, joins, or renames … crosses the validator's single-table allowlist," which
   the code did **not** enforce (bug 1). Option (a) was taken — `sql_validator` now enforces a
   true single-table allowlist — so the doc's claim is accurate again; no doc edit needed.

2. **`MVP_Technical_Design.md` §2.3 "carry the true match count".** The bounded-output
   description should note the current limitation (bug 5): the true total is only known for
   `COUNT(*)` queries; for list queries `row_count` is post-`LIMIT`. Worth an explicit
   "known limitation" line so the honesty claim isn't overstated.

3. **T0010.1 is closed, with one residual gap.** `query.py` returns 400 for empty input
   and re-raises `HTTPException`; `core/errors.py::InvalidQueryError` exists and is wired;
   `service.py` coerces a `None`/empty runtime answer into `FALLBACK_ANSWER`. However the
   coercion is currently unreachable in practice: `react_agent._extract_answer` *raises*
   `ValueError` on empty/unreadable final content rather than returning it, so
   `runtime.ainvoke` raises before the coercion runs and the exception falls through to the
   generic 500 in `query.py`. Tracked as its own open item in `Known_Issues.md` (API layer)
   rather than reopening T0010.1.
