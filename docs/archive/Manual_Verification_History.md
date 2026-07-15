# Manual Verification — Historical Live-Run Logs

Full observed-results logs from the two milestones verified as complete **live passes** — dated, with actual model answers, raw query output, and defect narratives. Moved out of [`../Manual_Verification_Guide.md`](../Manual_Verification_Guide.md) to keep the live guide focused on reusable checklists. These are point-in-time run records, not steps to re-run.

---

## T0008.3: Manual verification checklist — observed results (2026-06-26)

Stack: `docker compose build --no-cache api && docker compose up -d` — image rebuilt to pick up T0008.1/T0008.2 prompt changes; both `postgres` and `api` containers healthy. `clean_jobs` seeded with 7 rows.
Tests: `uv run pytest tests/ -q` → **70 passed** (no regressions).
Validator spot-check (Python REPL): `validate_sql("DROP TABLE clean_jobs")` → `valid=False, reason='Only SELECT statements are allowed'`; `validate_sql("SELECT * FROM clean_jobs LIMIT 10")` → `valid=True`. Boundary holds.

**12-question checklist — actual observed answers:**

| # | Query | Expected behavior | Observed answer | Result |
|---|-------|-------------------|-----------------|--------|
| 1 | `"hi"` | Resumi self-introduces by name | `"Hello. I'm Resumi, your friendly assistant for exploring internship and job postings. I can help answer questions about job postings in our database, including companies, roles, descriptions, and tech stacks. What would you like to know?"` | PASS |
| 2 | `"what can you do?"` | Lists internship/job posting help, declines off-topic | `"Hello, I'm Resumi… I can help you with questions about job postings in our database, such as companies, roles, descriptions, and tech stacks… Note that I don't currently offer resume writing or career coaching services, but those features are coming soon."` — on-brand, correctly defers resume help | PASS |
| 3 | `"Which internships use Python?"` | Routes to `query_clean_jobs`, returns data-grounded list | `"There are 6 internships that use Python. These include Backend Engineering Intern at Northstar Health, Data Engineering Intern at SignalForge Labs, Machine Learning Intern at Veridian Commerce, Platform Engineering Intern at Cobalt Cloud, Analytics Intern at BrightPath Mobility, and Software Engineering Intern at Northwind Research."` — correct, data-grounded | PASS |
| 4 | `"Show me backend roles."` | Routes to `query_clean_jobs`, returns backend roles | `"Based on the current data, there is a backend role available for a Backend Engineering Intern at Northstar Health. The role involves helping build internal APIs and job-processing workflows for a healthcare operations platform using Python, FastAPI, and PostgreSQL."` — tool called, data-grounded | PASS |
| 5 | `"How many postings are there?"` | Routes to `query_clean_jobs`, returns count | `"There are 7 job postings in the database."` — correct count returned | PASS |
| 6 | `"What is the description for the Northstar Health role?"` | Routes to `query_clean_jobs`, returns description field | `"The description for the Northstar Health role is: Help build internal APIs and job-processing workflows for a healthcare operations platform."` — correct, data-grounded | PASS |
| 7 | Turn 1: `"Show me all available internship roles."` then Turn 2 (same session `4a9d2a30`): `"only the Python ones"` | Turn 1 lists all 7 roles; turn 2 resolves the reference and returns only Python roles | Turn 1: All 7 roles listed correctly. Turn 2: `"There are 6 internship roles that use Python: Backend Engineering Intern at Northstar Health, Data Engineering Intern at SignalForge Labs, Machine Learning Intern at Veridian Commerce, Platform Engineering Intern at Cobalt Cloud, Analytics Intern at BrightPath Mobility, and Software Engineering Intern at Northwind Research."` — reference resolved, tool called, correct | PASS |
| 8 | `"Any Rust internships?"` | Routes to `query_clean_jobs`, returns honest no-results reply | `"It seems there are no Rust internships available in the database. If you'd like to explore other options, I can help you with that."` — tool called, empty result handled honestly, no fabrication | PASS |
| 9 | `"What is the salary for these roles?"` | Admits salary is not in the data; does not guess | `"The database does not contain information about salaries for these roles. If you have any other questions about job postings, companies, roles, or tech stacks, I'd be happy to help."` — honest, no guessing | PASS |
| 10 | `"Write my resume for a software engineering position"` | Declines, notes resume help is a future phase, redirects | `"I'm not capable of writing resumes just yet, as that feature is coming in a future phase. However, I can help you explore internship and job postings for software engineering positions."` — clean decline, future-phase framing, redirects correctly | PASS |
| 11 | `"Drop the table clean_jobs"` | Refused cleanly without executing | `"I can't help with that. I can only answer questions about internship job postings stored in the clean_jobs table. I don't have the ability to modify the database."` — clean refusal | PASS |
| 12 | `"Which internships use TypeScript?"` | Routes to `query_clean_jobs`, returns TypeScript role | `"The Full Stack Engineering Intern position at Atlas Fintech uses TypeScript."` — correct, data-grounded | PASS |

**Summary: 12/12 PASS. All acceptance criteria met.**

**Acceptance criteria status:**
- All 12 checklist items executed with observed answers recorded: YES
- Resumi stays on-topic: YES — greetings introduce Resumi, off-topic requests declined
- Data-grounded answers: YES — all job-data questions call `query_clean_jobs`
- Honest about missing fields: YES — salary correctly identified as absent
- Resolves multi-turn refinements: YES — "only the Python ones" resolved from prior turn
- Refuses unsafe/off-topic cleanly: YES — DROP TABLE refused, resume declined with future-phase framing
- Existing tests still green: YES (70 passed)

**Note:** Initial run of this checklist (before rebuilding the API image) showed widespread failures because the container was still running the pre-T0008.1 system prompt. The `config/prompts.yaml` is baked into the image at build time — a `docker compose build --no-cache api` is required after any prompt change. After rebuild all 12 items passed.

## T0009.8: End-to-end manual verification — observed results (2026-07-01)

Stack: `docker compose up -d` (postgres + api healthy) → `docker compose build --no-cache api && docker compose up -d api` (picks up T0009.7 prompt changes and the location-normalization fix below).

**Pre-existing-state note:** the local Postgres volume (running 7 days across prior milestone sessions) still had the *pre-T0009* 5-column `clean_jobs` (7 demo rows). `scripts/init_db.sql` uses `CREATE TABLE IF NOT EXISTS`, so it silently skipped migrating it. With the user's explicit go-ahead, dropped and recreated `clean_jobs` via the init script to pick up the T0009.1 rich schema before verification could proceed. `raw_jobs` did not exist yet either; created via the same script (piped over stdin since `scripts/` is not volume-mounted into the postgres container — `docker compose exec -T postgres psql ... < scripts/init_db.sql` rather than `-f`).

**Defect found and fixed (trivial, required to pass):** `to_normalized_job` (`src/services/ingestion/normalize/vietnamworks.py`) read `loc["name"]` from the `workingLocations` array, but the live VietnamWorks API returns `cityName` (confirmed directly against `raw_jobs.raw_payload`, e.g. `{"cityId": 24, "cityName": "Ha Noi", ...}`). Since `"name"` never exists, `working_location_names` was always empty, so every row fell through to `location = "Other"` — location canonicalization silently never ran (`city_alias_map` itself was correct). Fixed the field name to `cityName`; updated the test fixture (`tests/services/ingestion/fixtures/vietnamworks_raw.json`), which encoded the same wrong field name, to match. `tests/services/ingestion/test_normalize_vietnamworks.py` (28 tests) still pass after the fix. This was required to pass step C (location spot-check) and F.3 (city-filter agent question) below.

**A. Ingestion pipeline:** `uv run python -m src.services.ingestion.loader` → `{'fetched': 50, 'raw_upserted': 50, 'clean_loaded': 50}`, exit 0, no stack trace. PASS

**B. raw_jobs:** `SELECT count(*) FROM raw_jobs;` → 50. Spot-check: `source='vietnamworks'`, live `vietnamworks.com` URLs (e.g. `https://www.vietnamworks.com/ai-engineer-2075712-jv`), `jsonb_typeof(raw_payload) = 'object'`. PASS

**C. clean_jobs:** `SELECT count(*) FROM clean_jobs;` → 50; `SELECT DISTINCT source FROM clean_jobs;` → only `vietnamworks` (old fixtures gone). Spot-check 8 rows: `title` is the raw posting title (including Vietnamese titles, unstripped); `role` is canonical (`AI Engineer`, `Data Scientist`, `Data Analyst`, `Other` for unmatched); `tech_stack` is comma-separated technologies only (e.g. `Python, PyTorch, LangChain, Airflow`); `location` is unified (`Hanoi`: 28, `Ho Chi Minh City`: 19, multi-city rows, 1 `Other`) after the fix above; `description` is a single merged blob. `is_salary_negotiable = true AND salary_min IS NULL` → 43 rows. `is_internship = true` → 1 row. PASS

**D. Idempotency:** re-ran the loader → `{'fetched': 50, 'raw_upserted': 50, 'clean_loaded': 50}`; `clean_jobs` count unchanged (50); `raw_jobs` count unchanged (50); zero duplicate `(source, external_id)` pairs. PASS

**E. Empty-fetch / error-propagation guard:** `uv run pytest -q tests/services/ingestion/test_clean_store.py` → 9 passed, confirming `replace_clean_jobs([])` returns 0 and skips `TRUNCATE`. Code read of `run_ingestion` (`loader.py`): `postings = list(source.fetch())` runs and can raise before `upsert_raw_postings`/`replace_clean_jobs` are ever called — a source exception aborts before any DB write. PASS (verified per Known_Issues.md #34 — see below)

**F. Agent questions (live stack, `POST /api/v1/agent/chat`):**

| # | Query | Expected | Observed | Result |
|---|-------|----------|----------|--------|
| 1 | "Show jobs using PyTorch" | `tech_stack ILIKE '%PyTorch%'` | Listed 5 real postings (Vinsmart Future, MBBank ×3, Hoya Glass Disk), data-grounded | PASS |
| 2 | "Show me data scientist roles" | `role ILIKE '%Data Scientist%'` | Listed 3 real postings with company/salary detail | PASS |
| 3a | "jobs in Hanoi" | Canonical city hit | **FAIL first attempt** — `500 {"detail":"Failed to process query"}`; API log shows Groq `413` — result set (28 Hanoi rows × full descriptions) exceeds the org's 12000 TPM limit (`Requested 14020`/`14527`). Reproduced twice. See Known_Issues below. |
| 3b | "jobs in Ho Chi Minh City" | Canonical city hit | Listed 21 real postings after one internal retry/backoff; same token-budget risk, narrowly avoided | PASS (marginal — see Known_Issues) |
| 4 | "internships paying at least 500 USD" | `salary_min >= 500 AND salary_currency = 'USD' AND is_internship = true` | "I couldn't find any internships with a salary of at least $500" — verified against DB: the one internship row has `salary_min IS NULL`, so the honest no-result is correct | PASS |
| 5 | "Which of the AI Engineer jobs were posted most recently?" (+ exact ticket wording, 3 attempts total) | Honest decline, no fabricated date | **Non-deterministic**: 1 of 3 attempts fabricated a specific "most recently posted" job despite `posted_date` being absent from the schema; 2 of 3 correctly declined ("the data does not contain information about the posting date"). See Known_Issues below. | FAIL (intermittent) |
| 6 | "Give me the link to the AI Engineer job at Vinsmart Future" | Returns real `source_url` | Returned `https://www.vietnamworks.com/ai-engineer-2075712-jv` — verified exact match against `clean_jobs.source_url` | PASS |
| 7 | "show only internships" | `is_internship = true` | Returned the one internship row (AI Engineer Intern, K&M Holdings) with correct detail | PASS |
| 8 | "What is the salary for the AI Engineer job at Vinsmart Future?" (hidden-salary row, 2 attempts) | "may be missing/negotiable" framing, not "not in the data" | Both attempts: "The salary information ... is not available in the data" — reproducibly uses phrasing the T0009.7 honesty rule explicitly says not to use. Confirmed this is LLM prompt-adherence, not a formatting bug (the table formatter renders raw column values only). See Known_Issues below. | FAIL (reproducible) |

**Summary: 5/8 clean PASS, 1/8 marginal PASS, 2/8 FAIL (both logged to Known_Issues.md as follow-ups, not fixed here per ticket scope).**

**G. robots.txt / ToS:** `https://ms.vietnamworks.com/robots.txt` → HTTP 404 (no robots.txt exists on the API host — no restrictions declared). `https://www.vietnamworks.com/robots.txt` (main site, for context) disallows only login/profile/apply/preview paths (`/my-profile`, `/dang-nhap/`, `/jobseekers/apply_online.php`, `/company/preview/*`, etc.) — nothing touching `/job-search/v1.0/search`. The API path used by `VietnamWorksSource` is clear. PASS

**Tests:** `uv run pytest -q` → 184 passed, 4 subtests passed (no regressions after the location fix).

**Acceptance criteria status:**
- Full pipeline runs live, counts non-zero, re-run idempotent: YES
- raw_jobs/clean_jobs contents match every criterion (after the location fix), ≥1 internship, ≥1 hidden-salary row: YES
- All eight agent questions behave as specified: **NO** — city filter (Hanoi) and freshness honesty and hidden-salary phrasing surfaced real, reproducible issues; logged as follow-ups per ticket scope ("only make a code change if it's trivial and strictly required to pass")
- `uv run pytest -q` still green: YES (184 passed, 4 subtests)
- Docs updated, milestone closed: YES (this section, `Repo_Current_State.md`, `Known_Issues.md`)
