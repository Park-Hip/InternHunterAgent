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

## 🐞 Bugs found (one-line index — full status in Known_Issues.md)

`Known_Issues.md` is the living source of truth for bug status. These are pointers only —
do **not** maintain fix-history here; strike through / update the entry in `Known_Issues.md`.

1. ~~[HIGH] SQL validator did not enforce a single table.~~ **Fixed by T0010.3** →
   `Known_Issues.md` § Query tooling & SQL safety.
2. ~~[MED-HIGH] Blocking LLM call on the async event loop.~~ **Fixed by T0010.4** →
   `Known_Issues.md` § Query tooling & SQL safety.
3. ~~[MED] Ingestion aborts inconsistently on one bad payload.~~ **Fixed** (per-record guard;
   DN-1 redesign still open) → `Known_Issues.md` § Resolved.
4. ~~[MED] Denylist matched keywords inside string literals.~~ **Fixed** →
   `Known_Issues.md` § Resolved.
5. **[MED] OPEN — "Showing N of M" can understate the true match count.** `format_rows` sets
   `row_count = len(rows)` (post the model's own `LIMIT`), not the true total → `Known_Issues.md`
   § Query tooling & SQL safety.
6. ~~[MED] `normalize_location` only matches on an exact full-string lookup.~~ **Fixed by
   T0010.6** → `Known_Issues.md` § Resolved.
7. ~~[LOW] Per-request `client.flush()` on the event loop.~~ **Fixed** →
   `Known_Issues.md` § Capacity & performance.
8. ~~[LOW/latent] `replace_clean_jobs` would crash on intra-batch duplicate keys.~~ **Fixed** →
   `Known_Issues.md` § Data & ingestion / database schema.

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

---

## 🏗️ Deploy / multi-source design notes (record before scaling past one source)

These are **broader architectural notes**, not bugs and not yet tickets — captured so the
decisions are on record before the Deploy and multi-source milestones. They inform (but are
larger than) bug 3 above (now fixed at the per-record-guard level; DN-1 move 1, transforming
from `raw_jobs` instead of the fetch batch, remains open).

### DN-1. `clean_jobs` should be a re-derivable projection of `raw_jobs`, not of the fetch batch.
**Current:** `loader.run_ingestion` upserts `raw_jobs`, then transforms the **in-memory fetch
batch** (`[to_normalized_job(p.raw_payload) for p in postings]`) and `TRUNCATE`s + rebuilds
`clean_jobs` from that batch. So `raw_jobs` is the durable, accumulating store while `clean_jobs`
only ever contains what *this run* fetched — the two are coupled through the fetch, not through
the table. Consequences:
- A posting that drops out of search results one day vanishes from `clean_jobs` even though it
  still lives in `raw_jobs`.
- `raw_jobs` and `clean_jobs` are written in **separate transactions**, so a failure between them
  can still desync the two (bug 3's per-record normalization guard prevents one bad *payload*
  from aborting the whole batch, but a crash between the two writes is still possible).
- `content_hash` is stored but **never read** — the intended "filter existing / skip unchanged"
  delta step does not exist; every run re-processes the whole batch.

**Suggested deploy flow.** Make `raw_jobs` the source of truth and `clean_jobs` a pure function
of it:
```
[scheduler: daily]
      │
      ▼
fetch per source ──► upsert raw_jobs (source, external_id) + content_hash + last_seen_at
      │                    │  (content_hash unchanged? → skip re-transform for that row)
      ▼                    ▼
 run summary  ◄──  transform FROM raw_jobs (per-record, guarded) ──► load clean_jobs
```
Five moves, in rough priority:
1. **Transform from `raw_jobs`, not the batch** → `clean_jobs` becomes fully reproducible; a run
   that fetches nothing new can still rebuild clean correctly.
2. ~~**Per-record guard in normalization (fixes bug 3)**~~ **Done** — `try/except` around
   `to_normalized_job`, skip + log the bad record. One malformed payload can no longer abort
   the whole normalization pass.
3. **Scheduler** — cheapest MVP is an external cron / container scheduler invoking the ingestion
   entrypoint; avoid an in-process scheduler dependency. (Deploy-milestone item.)
4. **Use `content_hash` for the delta** — compare incoming vs stored hash, skip re-transform of
   unchanged rows. This is the missing "filter existing" step; optional for correctness but it's
   the reason the hash is stored.
5. **Keep the clean load simple** — `TRUNCATE + rebuild from raw` is safe *once (1) is in place*
   (clean = full projection of raw, atomic in one transaction). Only move to per-row upsert +
   `last_seen`/`is_active` if freshness/expiry semantics are later required. Do **not** build
   that now (no over-engineering).

Not yet built and explicitly out of MVP scope: the daily scheduler itself, and any
raw-row pruning/expiry policy.

### DN-2. `content_hash` does not (and cannot) dedup the *same job across two sources*.
The identity model is safe; the hash is a **within-row change-detector**, not a cross-source
merge key. Three layers:
- **Row identity — safe.** PK is `(source, external_id)`; `source` namespaces the id. The same
  real-world job on VietnamWorks and (future) TopCV becomes two *different* keys → two rows, no
  collision, no overwrite.
- **Hash collision — not a real risk.** `content_hash` is sha256 of the payload; it is only ever
  compared against the prior hash of the *same* `(source, external_id)` row. Cryptographic
  collision is negligible and irrelevant to identity.
- **The actual gap — cross-source duplicate *jobs*.** The same job on two boards produces two
  `clean_jobs` rows (user sees it twice). `content_hash` cannot merge them: each site's payload
  has different fields/formatting/IDs → **different hashes even for the identical job**. Real
  cross-source dedup needs a *semantic* identity (normalized `(title, company, location)` or a
  canonicalized apply-URL) with fuzzy/near-duplicate matching — a genuinely harder problem.

**Status:** acceptable today (single source ⇒ cross-source duplication can't occur). Becomes a
real "duplicate listings" problem the moment a second source is added, and `content_hash` will
**not** solve it. Deliberate later-milestone item, not a bug.
