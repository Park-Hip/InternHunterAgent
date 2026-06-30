# Milestone T0009 — Data Ingestion Stage (working scratchpad)

> **Status: DISPOSABLE / temporary working doc.** Staging scratchpad for the technical
> detail of the data-ingestion milestone. It is **not** a doc of record. Once settled, its
> content is **delivered into** `docs/Full_Design_Document.md`,
> `docs/MVP_Technical_Design.md`, and `docs/Tickets.md`, then this file is deleted. No other
> doc should reference it.
>
> **Research behind every decision here (do not re-derive):**
> `research/data-ingestion-stage.md` (✅ VietnamWorks JSON-API experiment, §0.1) and
> `research/job-site-comparison.md`. The spike lives at `scripts/scrape_spike.py` with a
> captured sample at `research/experiments/vietnamworks_ai_data_sample.json`.
>
> **Locked decisions (this milestone):** v1 source = **VietnamWorks only**; ticket id =
> **T0009**; `tech_stack` = **deterministic keyword finder** over a curated technology
> dictionary; **`role` = deterministic normalization of the messy title into a fixed role
> taxonomy** (AI Engineer, Data Scientist, Data Engineer, Data Analyst, ML Engineer,
> Software Developer, …); **`location` = normalized to city/province only in a unified form**
> (Ha Noi/Hanoi → `Hanoi`; HCM/TPHCM/Ho Chi Minh/hcm → `Ho Chi Minh City`); agent-visible
> `clean_jobs` = **Rich** (adds `role`, `source_url`, `posted_date`, `is_internship`,
> `location`, structured salary); fixtures = **replaced** by real IT/AI-Data postings only;
> **`description` is a single merged free-text blob** (no separate `requirement`/`benefits`
> columns — the cross-source common shape; VietnamWorks' split fields are concatenated back);
> **salary is structured** (`salary_min`, `salary_max`, `salary_currency`,
> `is_salary_negotiable`), not a display string; volume =
> **~50 cap**, tunable. All schema, cleaning, and models are designed **source-agnostic so
> future boards drop in without reshaping the tables** — the role taxonomy and city alias
> map are source-neutral and shared.

---

## 1. Milestone summary & objective

Stand up the first real data-ingestion pipeline: fetch live **IT / AI-Data** postings from
the VietnamWorks public JSON search API, land them verbatim in a new `raw_jobs` table,
transform them deterministically (HTML→text, `tech_stack` keyword finder, internship
flag), and upsert into an enriched `clean_jobs` that the SQL agent already queries.
Re-running is idempotent. The 7 hand-written fixtures are replaced by real postings.

The pipeline is built behind a **provider-agnostic `JobSource` interface** and a
**source-agnostic schema**, so adding ITviec/TopDev/TopCV later is a new adapter + a new
normalizer — no table reshape, no change to the cleaning core. This is the explicit
forward-compatibility requirement.

## 2. Scope

**In scope**
- `raw_jobs` landing table (source-agnostic, verbatim payload + provenance).
- Enriched, source-agnostic `clean_jobs` (Rich agent-visible schema).
- `JobSource` interface + **one** adapter: `VietnamWorksSource` (graduates the spike).
- Deterministic transform: HTML→text, internship flag, **`tech_stack` keyword finder**.
- Idempotent batch loader (re-runnable CLI), upsert on `(source, external_id)`.
- Config in `config/settings.yaml`; models in `models.py` (CLAUDE.md).
- Agent-layer follow-through for the Rich columns (schema_context, prompts, validator,
  T0008 honesty rules) — required because the new columns are agent-visible.

**Out of scope** (deferred — pointer where it lives)
- Other boards (ITviec/TopDev/TopCV/LinkedIn) → adapters are future tickets; interface is
  built now so they slot in. See `research/job-site-comparison.md`.
- `cloudscraper` / Scrapfly managed scraping → not needed for the VietnamWorks JSON API.
- **Scheduler / cron** → deploy-research track (`research/deployment-research-plan.md` §4).
- **LLM-based tech extraction** → deferred; keyword dictionary only (research §5).
- Cross-board dedup heuristics → only `(source, external_id)` + `content_hash` here.
- Deploy / hosting / where data lives in prod → `research/deployment-research-plan.md`.
- Language behaviour (agent answers VI/EN) → cross-cutting, agent/prompt design, not here.

## 3. Decisions — all locked

Source set, ticket id, tech_stack method, schema width, fixture replacement, and volume cap
are locked in the banner. The three normalization defaults are now **confirmed locked**:

1. **Role taxonomy + fallback (LOCKED).** Canonical role set: **AI Engineer, Data
   Scientist, Data Engineer, Data Analyst, ML Engineer, Software Developer**, plus
   **`Other`** for unmatched titles (the row is **never dropped**). Mapping = keyword/pattern
   rules over `jobTitle` with `jobFunction` child id as a tiebreaker.
2. **Multi-city handling (LOCKED).** `location` is unified **city/province only**; a posting
   with several `workingLocations` → **comma-separated canonical cities**; unknown → `Other`.
3. **`role` is an agent-visible queried column (LOCKED).** Lets the agent answer "show data
   scientist roles" via `role ILIKE`, not brittle `title` matching. Folds into the T0009.7
   prompt / honesty / validator update.

4. **`description` is a single merged blob (LOCKED).** The cross-source common shape is one
   free-text `description`; **no `requirement`/`benefits` columns** on `clean_jobs`. Only
   VietnamWorks splits these (`jobRequirement`, structured `benefits`) — its normalizer
   **concatenates `jobDescription` + `jobRequirement` + benefit values back into one
   `description`** so every source produces an identical shape, matching what ITviec/TopCV/
   TopDev already return as a single blob. The verbatim split fields survive in `raw_jobs`
   (re-splittable later by the resume/RAG milestone at zero MVP cost).
5. **Salary is structured, not a display string (LOCKED).** A text `prettySalary` can't be
   range-filtered or sorted — it kills the core "pay ≥ X" query. VietnamWorks already hands
   us the numbers, so `clean_jobs` carries **`salary_min`, `salary_max` (numeric, nullable),
   `salary_currency` (e.g. USD/VND, mandatory when a number is present), and
   `is_salary_negotiable` (bool)**. The normalizer fills them per source: VietnamWorks maps
   `salaryMin`/`salaryMax`/`salaryCurrency` directly and sets `is_salary_negotiable = not
   isSalaryVisible`; a future string-only board parses its salary string deterministically,
   else leaves min/max NULL with `is_salary_negotiable = true`. `prettySalary` stays in
   `raw_jobs` only.

Supporting defaults locked for a concrete spec (tunable later in `settings.yaml`):
- **City alias map** seed: `ha noi/hanoi → Hanoi`, `hcm/tphcm/ho chi minh/hcmc →
  Ho Chi Minh City`, `da nang/danang → Da Nang`, extended as gaps surface.
- **Tech keyword dictionary** seed: spike-observed techs (Python, SQL, Airflow, AWS,
  PyTorch, …) plus a curated popular-tech list, ~50–100 terms.

## 4. Requirements

### 4.1 Functional
- Fetch IT/AI-Data postings via keyword-recall + `jobFunction` precision (research §0.1).
- Land every fetched posting verbatim in `raw_jobs` before any transform (never lossy).
- Transform deterministically into `clean_jobs`; **no LLM, no network calls in transform.**
- Merge source text into a **single `description`** — for VietnamWorks, concatenate
  `jobDescription` + `jobRequirement` + benefit values (one common shape across all boards;
  no separate `requirement`/`benefits` columns on `clean_jobs`).
- Map salary into **structured** fields — `salary_min`, `salary_max`, `salary_currency`,
  `is_salary_negotiable` — so the agent can range-filter/sort, not a display string.
- Flag internships (`is_internship` from `jobLevelVI`/`jobLevel`), collect all levels.
- Derive `tech_stack` from a deterministic keyword finder (skills array + description text
  matched against the dictionary), technologies-only, deduped, comma-separated string
  (matches the existing `clean_jobs.tech_stack` format from T0008.2).
- **Normalize the messy `title` into a canonical `role`** via a deterministic role
  taxonomy (keyword/pattern rules over the title, `jobFunction` child id as tiebreaker);
  keep the raw `title` untouched, write the canonical label to `role`, unmatched → `Other`.
- **Normalize `location` to a unified city/province** via a deterministic alias map (e.g.
  `Ha Noi`/`Hanoi` → `Hanoi`; `HCM`/`TPHCM`/`Ho Chi Minh`/`hcm` → `Ho Chi Minh City`);
  store city/province only, no street address; multi-city → comma-separated canonical set.
- Idempotent: re-run upserts on `(source, external_id)`, no duplicates, refreshes changes.
- Replace the 7 fixtures; final `clean_jobs` is 100% real IT/AI-Data postings.

### 4.2 Architectural constraints (CLAUDE.md)
- New code under `src/services/ingestion/` — **isolated from API / agent / tracing**; the
  serving request path must not import the ingestion package.
- All models in `models.py`; all parameters in `config/settings.yaml`.
- One ticket at a time; no over-engineering; follow-ups reported, not auto-fixed.
- Loader is a **batch CLI**, not wired into FastAPI startup.

### 4.3 Data / schema (source-agnostic by design)
- `raw_jobs`: surrogate `id`, `source`, `external_id`, `source_url`, `raw_payload`
  (JSON/JSONB), `content_hash`, `fetched_at`. Unique `(source, external_id)`.
- `clean_jobs` (enriched): existing `id`, `title`, `company`, `description`, `tech_stack`
  **+** `role` (canonical), `source`, `external_id`, `source_url`, `posted_date`,
  `is_internship`, `job_level`, `location` (canonical city/province), `salary_min`,
  `salary_max`, `salary_currency`, `is_salary_negotiable`. Unique `(source, external_id)`.
  Every column is source-neutral — VietnamWorks-specific names are mapped away in the
  adapter/normalizer, not stored. `title` keeps the raw posting title; `role` and `location`
  hold the normalized canonical values. **`description` is a single merged free-text blob**
  (desc + requirements + benefits) — there are deliberately **no `requirement`/`benefits`
  columns** (cross-source common shape; the split fields live only in `raw_jobs`).
- Any agent-visible column change cascades to `config/prompts.yaml` (`schema_context`,
  SQL-generation prompt, honesty rules) and the SQL validator (§4 of T0006.5 allowlists the
  table, not columns — validator change is minimal but the prompt/honesty change is real).

### 4.4 Non-functional
- Politeness: realistic User-Agent, ~0.6 s delay, capped pages (spike-proven, 100% success).
- Determinism & testability: transform + keyword finder are pure functions, unit-tested.
- Store source text **as-is** (no translation at ingest).
- **Pre-build gate:** check `ms.vietnamworks.com/robots.txt` + VietnamWorks ToS for the API
  host before first production run (research §4); store only factual, non-personal fields.

## 5. Architecture & dataflow

The source-specific knowledge lives only in the **adapter** (fetch) and the **normalizer**
(payload → common shape). Everything downstream is shared and source-agnostic.

```
                    config/settings.yaml          config/settings.yaml
                  (API params, queries,            (tech keyword dict)
                   jobFunction ids, cap)                   │
                          │                                │
                          ▼                                ▼
  ┌──────────────────────────────┐   verbatim   ┌─────────────────────────┐
  │ JobSource (interface)        │  RawPosting   │ raw_jobs (landing)      │
  │  └ VietnamWorksSource (v1)   │ ───────────▶  │  source, external_id,   │
  │    httpx POST /job-search    │  upsert       │  source_url, raw_payload│
  │    keyword recall +          │  (source,     │  content_hash, fetched_at│
  │    jobFunction precision     │   external_id)│                         │
  └──────────────────────────────┘               └───────────┬─────────────┘
        (ONLY source-specific code)                          │ read raw_payload
                                                             ▼
                              ┌──────────────────────────────────────────┐
                              │ Normalizer (per-source map → NormalizedJob)│
                              │   VietnamWorks fields → common field names │
                              └───────────────────┬────────────────────────┘
                                                  ▼
                              ┌──────────────────────────────────────────┐
                              │ Transform (SHARED, source-agnostic)        │
                              │  • HTML → text, merge → one description     │
                              │    (desc + requirement + benefits)         │
                              │  • is_internship from level                │
                              │  • tech_stack = keyword finder(skills+text)│
                              │  • role = role taxonomy(title, jobFunction)│
                              │  • location = city alias map(address)      │
                              │  • salary_min/max/currency/negotiable       │
                              └───────────────────┬────────────────────────┘
                              (role taxonomy + city alias map live in settings.yaml)
                                                  ▼  upsert (source, external_id)
                              ┌──────────────────────────────────────────┐
                              │ clean_jobs (agent-facing, Rich schema)     │
                              │  title (raw), role (canonical),            │
                              │  company, description (merged), tech_stack, │
                              │  source_url, posted_date, is_internship,   │
                              │  job_level, location (canonical),          │
                              │  salary_min, salary_max, salary_currency,  │
                              │  is_salary_negotiable                      │
                              └──────────────────────────────────────────┘
                                                  ▲
                                          SQL agent (T0006) queries here
```

**Local vs deploy storage** = the existing app Postgres locally; production placement is
the deploy-research track, **not decided here** (`research/deployment-research-plan.md` §3).

## 6. Step-by-step build plan (T0009 sub-tickets, dependency-ordered)

Mirrors the `Tickets.md` T000x.y style; each slice is independently mergeable.

- **T0009.1 — Schema & migration.** Add `raw_jobs`; enrich `clean_jobs` with the new
  columns (single `description`; structured `salary_min`/`salary_max`/`salary_currency`/
  `is_salary_negotiable`; **no `requirement`/`benefits` columns**) + `unique(source,
  external_id)`. Update `scripts/init_clean_jobs.sql` (drop the 7 fixtures path). Models for
  both tables in `models.py`.
- **T0009.2 — Config & models.** `config/settings.yaml`: API URL, keyword queries,
  `jobFunction` ids (parent 5 / child 27), page/`max_jobs` cap, delay, User-Agent, the
  **technology keyword dictionary**, the **role taxonomy** (canonical role → match rules),
  and the **city alias map** (alias → canonical city/province). `models.py`: `RawPosting`,
  `NormalizedJob`.
- **T0009.3 — `JobSource` interface + `VietnamWorksSource`.** Graduate `scrape_spike.py`:
  provider-agnostic interface, VietnamWorks adapter does fetch + keyword-recall/jobFunction
  precision, yields `RawPosting`. Constants move spike→`settings.yaml`. Unit-tested on a
  captured fixture (no live call in tests).
- **T0009.4 — Raw landing.** Upsert `RawPosting` into `raw_jobs` on `(source, external_id)`
  with `content_hash`. Idempotent.
- **T0009.5 — Normalize + transform (role, location, tech_stack, salary, description).**
  Per-source normalizer → `NormalizedJob` — for VietnamWorks this **merges
  `jobDescription` + `jobRequirement` + benefit values into one `description`**, and maps
  `salaryMin`/`salaryMax`/`salaryCurrency`/`not isSalaryVisible` into the structured salary
  fields. Shared transform: HTML→text, `is_internship`, the deterministic `tech_stack`
  finder (skills + description → dictionary → dedup → comma-separated), the **`role` taxonomy
  mapping** (title + jobFunction → canonical role, unmatched → `Other`), and the
  **`location` city alias mapping** (address/workingLocations → unified city/province). All
  pure functions, fully unit-tested (include alias/edge cases like `TPHCM`, `Ha Noi`,
  multi-city, unmatched title, a hidden-salary → `is_salary_negotiable = true` + NULL
  min/max, a merged-description shape).
- **T0009.6 — Loader (idempotent upsert into `clean_jobs`).** Batch CLI under
  `src/services/ingestion/`; replaces fixtures; re-run = no duplicates. Manual entrypoint.
- **T0009.7 — Agent-layer follow-through (Rich schema).** Update `prompts.schema_context`,
  the SQL-generation prompt, and the **T0008 honesty rules** for the new columns (`role`,
  `salary_min`/`salary_max`/`salary_currency`/`is_salary_negotiable`, `location`,
  `source_url`, `posted_date`, `is_internship`). Tell the SQL prompt that `role`/`location`
  are **canonical** values (query `role ILIKE '%Data Scientist%'`, `location ILIKE '%Ho Chi
  Minh%'`), that salary is **numeric and currency-scoped** (filter within a `salary_currency`,
  e.g. `salary_min >= 1000 AND salary_currency = 'USD'`), and that salary may be NULL /
  `is_salary_negotiable = true` ("may be missing or negotiable for some postings"). Minimal
  SQL-validator touch.
- **T0009.8 — End-to-end manual verification.** Full-stack run + idempotency + agent answers
  over real data (see §8).

## 7. Completion criteria (definition of done)

- A documented command runs the loader end-to-end against local Postgres.
- `raw_jobs` holds verbatim VietnamWorks payloads with provenance; `clean_jobs` holds
  ~≤50 **real IT/AI-Data** postings, **fixtures gone**.
- Re-running the loader produces **zero duplicates** (upsert on `(source, external_id)`).
- `tech_stack` values are **technologies only** (keyword finder), no role/category labels.
- `role` holds a **canonical taxonomy value** (no messy raw titles); unmatched titles are
  `Other`, never dropped. `location` holds a **unified city/province** (no street address;
  `TPHCM`/`Ha Noi` variants collapsed to one canonical form).
- Internships are flagged; all levels present.
- `description` is a **single merged blob** (desc + requirements + benefits); there are no
  `requirement`/`benefits` columns on `clean_jobs` (the split fields survive only in
  `raw_jobs`).
- Salary is **structured** (`salary_min`, `salary_max`, `salary_currency`,
  `is_salary_negotiable`) and range-filterable; hidden-salary rows have NULL min/max and
  `is_salary_negotiable = true`.
- New Rich columns are populated (salary/location may be NULL where source hides them) and
  the agent can answer over them; honesty rules updated so it never guesses a NULL field.
- Transform + keyword-finder unit tests pass; adapter tested on a captured fixture.
- `robots.txt` / ToS check for the API host recorded.
- Schema/cleaning/interface are demonstrably source-agnostic (a second adapter would need
  no table change) — noted in the design doc.
- Completion report + `docs/Repo_Current_State.md` updated (CLAUDE.md §5/§6).

## 8. Manual verification checklist

1. `docker compose up -d` → Postgres healthy.
2. Run the ingestion CLI; confirm it reports N fetched / N landed / N upserted.
3. Inspect `raw_jobs`: a row's `raw_payload` is the real VietnamWorks JSON; `source_url`
   opens a live posting.
4. Inspect `clean_jobs`: recognizable VN companies, real titles; `tech_stack` is techs
   only; `role` is a canonical label (e.g. `Data Scientist`, not the raw title); `location`
   is a unified city (e.g. `Ho Chi Minh City`, never `TPHCM`/`Q.1, HCM`); at least one
   `is_internship = true`; the 7 fixtures are gone.
5. Re-run the CLI → row count unchanged (idempotent), no duplicate `(source, external_id)`.
6. Ask the agent: a tech filter ("show Python jobs"), a **role filter** ("data scientist
   roles"), a **city filter** ("jobs in Hanoi" and "jobs in HCM" should hit the same
   canonical city), a **salary range filter** ("internships paying at least $500" → uses
   `salary_min`/`salary_currency`), a freshness/`posted_date` question, a `source_url`/link
   question, an internship-only question, and a salary question on a hidden-salary row
   (expect an honest "not available / negotiable", not a guess).

## 9. Risks & follow-ups

- **Undocumented API shape change** — pin the request/response behind the adapter; treat
  parse failures as a reliability signal (research §0.1, `job-site-comparison.md` risk
  table). Adapter is the only place to fix.
- **Keyword-dictionary gaps** — finder misses uncommon techs / synonyms; dictionary is
  tunable in `settings.yaml`; LLM extraction stays a deferred follow-up (research §5).
- **Role taxonomy / city alias gaps** — an unseen title falls to `role = Other`; an unseen
  city variant falls to `Other` for `location`. Both maps live in `settings.yaml` and are
  extended as gaps surface; an unexpectedly high `Other` rate is a tuning signal, not a
  failure. Keep the maps source-neutral so they serve future boards.
- **Rich schema blast radius** — agent-layer edits (T0009.7) are the main regression
  surface; the T0008 manual checklist should be re-run as a follow-up guard.
- **Salary/location sparsity** — many postings hide salary; honesty rule must cover NULLs.
- **Scheduler still manual** — daily cron deferred to deploy research.

## 10. Delivery map — where this goes in `docs/`

- §1–§2, §5 → `docs/Full_Design_Document.md` (ingestion stage description + dataflow).
- §3, §4, §5, §6 → `docs/MVP_Technical_Design.md` (technical design, schema, config, models).
- §3, §6, §7, §8 → `docs/Tickets.md` (new **T0009** milestone + sub-tickets with
  per-ticket manual verification).
- After delivery: update `docs/Repo_Current_State.md`, then **delete this file**.
