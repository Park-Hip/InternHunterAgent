# Data Ingestion Stage — Deep Research

> **Status:** Research / pre-design. This document gathers the external facts needed
> before authoring the ingestion **design doc** and **technical doc**. It does not
> commit an implementation. It feeds `Full_Design_Document.md` / a future
> `Tickets.md` entry.
>
> **Scope:** how InternHunterAgent should acquire *real* internship-posting data and
> transform it into the `clean_jobs` table the existing SQL skill already queries.
> Current state: `clean_jobs` holds **7 hand-written rows** (id, title, company,
> description, tech_stack) loaded from `scripts/init_clean_jobs.sql`. There is no
> acquisition, no `raw_jobs`, no transform.

---

## 1. Headline finding (the reframe)

**You very likely do not need Scrapfly — or any scraping service — for the MVP.**

A small set of Applicant Tracking Systems (ATS) expose **public, no-auth, structured
JSON job APIs**: **Ashby, Greenhouse, Lever, Recruitee, Workable, Personio**. These
return clean per-company job data with no proxies, no anti-bot, no rendering, and no
scraping ToS exposure. For a "small fixed sample" internship MVP, pulling a curated
set of companies' ATS boards gives **real, refreshable, permissively-usable data at
zero data-acquisition cost.**

A managed scraper (Scrapfly et al.) only becomes necessary if you must target
*hostile, JS-heavy, anti-bot boards* — LinkedIn, Indeed — which are also the ones
with the **most aggressive ToS and legal history**. For the MVP that is a cost,
complexity, and legal-risk multiplier you can avoid.

This changes the earlier plan: "ingestion via Scrapfly" should be re-evaluated as
"ingestion via ATS public APIs, with a scraping provider as an optional, isolated
fallback adapter."

---

## 2. Source landscape (three tiers)

### Tier A — Public ATS JSON APIs (recommended for MVP)

No authentication, structured JSON, documented, permissive. You target *companies*,
not a board, and aggregate across a curated list.

| ATS | Endpoint pattern | Auth | Filtering at source | Notes |
|-----|------------------|------|---------------------|-------|
| **Greenhouse** | `GET https://api.greenhouse.io/v1/boards/{company}/jobs?content=true` | None | None (pull all, filter client-side) | Returns most posting fields incl. full description. |
| **Lever** | `GET https://api.lever.co/v0/postings/{company}?mode=json` | None | `team`, `department`, `location`, `commitment`, `level`, `skip`, `limit` | `commitment=Internship` is a real internship filter at source. Best filtering. |
| **Ashby** | Public posting feed; `includeCompensation=true` | None | Limited | Cleanest **compensation** support of the three. |
| **Workable / Recruitee / Personio** | Public job feeds per company | None | Varies | Round out coverage; same model. |

**Implication:** the acquisition layer is a thin HTTP client + per-ATS parser. No
vendor account, no API key, no rate-limit billing. Stable and cheap.

### Tier B — Official aggregator/job APIs (key required)

| Source | Auth | Internship filtering | Fields | Terms — **read carefully** |
|--------|------|----------------------|--------|----------------------------|
| **USAJobs** (US federal) | Free self-service key (email + User-Agent) | `hiring path` (Students/Pathways), keyword | duties, qualifications, education, salary, location, grade | Government data, **permissive**. Narrow domain (US federal only). |
| **Adzuna** | Free key | category / `contract_type` / keyword | title, company, location, salary_min/max, description, category | ⚠️ **Restrictive ToS.** Use limited to a **14-day validation trial**; data "may not be used in original format or in aggregation … to deliver any ongoing work or research" without **written consent**. **Not suitable** for a deployed app others use. |

**Implication:** USAJobs is a safe, real, keyed source but covers only federal
internships. Adzuna is effectively disqualified for a publicly-usable deployment by
its own terms — good for a one-off data sanity check, not for shipping.

### Tier C — Scraping hostile boards (Scrapfly et al.)

LinkedIn, Indeed, and similar require JS rendering + anti-bot bypass and carry the
heaviest ToS/legal baggage (these are the boards behind the well-known scraping
lawsuits). A managed scraper handles the *technical* difficulty but not the *legal*
exposure. **Recommend deferring entirely** unless a product reason forces a
specific hostile board.

---

## 3. Scrapfly assessment (if a scraper is ever needed)

- **Pricing:** free tier 1,000 credits (no card, no expiry); paid from **$30/mo**
  (Discovery, 200k credits) up to $500/mo (5.5M credits).
- **Credit model:** simple HTTP scrape = **1 credit**; **+5** for JS render or
  anti-bot; **+25** for residential IPs; 60 for screenshot. Benchmarked (June 2026)
  at ~**$4.13 per 1,000 requests**, #1 of 8 services at 99% success.
- **⚠️ Cost unpredictability:** the Anti-Scraping-Protection system can *dynamically
  upgrade* a request mid-flight to beat anti-bot, silently turning a 1-credit call
  into a 25-credit one. Budget caps must assume worst-case multipliers.
- **Verdict:** capable and well-priced **for what it is**, but it solves a problem
  (hostile boards) the MVP can avoid. If retained, it should be **one adapter behind
  a provider-agnostic acquisition interface**, not the primary path.

---

## 4. Legality / ToS summary

- **Public ATS APIs (Tier A):** lowest risk — documented public endpoints, no auth
  bypass, factual non-personal data. Industry guidance explicitly recommends these
  *instead of* scraping. Still: honor robots.txt, rate-limit politely, store factual
  fields only.
- **USAJobs:** government source, permissive.
- **Adzuna:** **contractually restrictive** — disqualifying for ongoing/aggregated
  use without written consent (see §2 Tier B).
- **Scraping (Tier C):** "mostly legal for public, non-personal, factual data," but
  risk concentrates at the edges — personal data, auth bypass, copyrighted content,
  server overload, **contract/ToS terms**. robots.txt is not a contract but ignoring
  it is bad-faith evidence. This is the tier that needs legal caution.

**Net:** Tier A + USAJobs lets the MVP ship with a clean conscience and no vendor
contract. The risk decision only becomes hard if you insist on Tier C.

---

## 5. The `tech_stack` problem (an architectural fork)

The current `clean_jobs.tech_stack` is a **curated** field ("Python, FastAPI,
PostgreSQL"). **Real postings do not have this field.** Tech skills are embedded in
free-text descriptions and must be **derived** in the transform stage. This is the
single biggest design fork in ingestion:

| Approach | Quality | Cost / complexity | Notes |
|----------|---------|-------------------|-------|
| **Keyword dictionary** (curated list of techs, match against description) | Decent for common, explicit stacks; misses synonyms/context | Trivial, deterministic, no LLM, no external calls | Strong MVP default. Fully testable. |
| **NER models** | Limited for this domain | Medium | Research finds traditional NER "ineffective for the semantically diverse, context-rich" nature of postings. |
| **LLM extraction** (prompt a model to extract techs) | Best — handles context/synonyms; research shows LLMs outperform SOTA | Adds an LLM call **into the ingestion pipeline**, with cost, latency, nondeterminism | Architecturally significant: ingestion would gain an LLM dependency. |

**Decision this forces:** does the ingestion pipeline contain an LLM step, or stay
purely deterministic? For an MVP that values "trustworthy + simple," a **keyword
dictionary first, LLM extraction as a future enhancement** path keeps ingestion
deterministic and testable, aligned with the project's "don't over-engineer the
MVP" rule. This should be an explicit decision in the design doc.

---

## 6. Schema implications (raw + clean)

Confirmed two-table design (your choice 2C):

- **`raw_jobs`** — store the source payload **verbatim**: raw JSON, `source` (ats +
  company), `source_url`, `external_id`, `fetched_at`, `content_hash`. Never lossy.
- **`clean_jobs`** — the agent-facing table the SQL skill already uses.

**Field availability across real sources (what the transform can populate):**

| Field | ATS (Greenhouse/Lever/Ashby) | USAJobs | Currently in `clean_jobs`? |
|-------|------------------------------|---------|----------------------------|
| title | ✅ | ✅ | ✅ |
| company | ✅ | ✅ (agency) | ✅ |
| description | ✅ (HTML → needs text cleanup) | ✅ | ✅ |
| **tech_stack** | ❌ derived (see §5) | ❌ derived | ✅ (curated today) |
| location | ✅ | ✅ | ❌ |
| remote/onsite | partial (Lever) | partial | ❌ |
| salary/comp | Ashby (`includeCompensation`) | ✅ | ❌ |
| posted_date | ✅ | ✅ | ❌ |
| source_url | ✅ | ✅ | ❌ |

**Implication:** real data offers *more* than today's 4 columns. Which of these get
promoted into `clean_jobs` is a product/schema decision — but each new column the
agent can see also requires updating `config/prompts.yaml` (`schema_context`, the
SQL-generation prompt, and the available-fields gate). Keep the *raw* table rich;
keep the *clean* table only as wide as the agent is prompted to use.

---

## 7. Internship filtering, identity, dedup (secondary findings)

- **Internship filter by source:** Lever `commitment=Internship` (best); USAJobs
  hiring-path/keyword; Greenhouse/Ashby — no source filter, **filter client-side on
  title/keywords** ("intern", "internship", "co-op").
- **Identity / dedup key:** ATS responses carry a stable per-posting `id` →
  combine with `source` for a natural key. Cross-source duplicates (same role posted
  to multiple boards) are rare for a curated ATS list; a `content_hash` fallback
  covers reposts. Upsert on `(source, external_id)`.
- **Description cleanup:** ATS descriptions are **HTML** — the transform needs an
  HTML→text step before storing in `clean_jobs.description`.

---

## 8. Decide vs. research — now resolved

What the earlier split flagged as **research-blocking**, and where it now lands:

| Earlier open item | Resolution from this research | Still your call |
|-------------------|-------------------------------|-----------------|
| Do we even need Scrapfly? | **No** for MVP — use Tier A ATS APIs | Whether to keep a scraper adapter as future fallback |
| Per-source ToS/legality | Tier A + USAJobs permissive; **Adzuna disqualified**; Tier C risky | Final risk tolerance if you ever want Tier C |
| Scraper features/pricing | Documented (§3); avoidable for MVP | Budget cap *if* Tier C is ever pursued |
| What fields real data has | Mapped (§6) — richer than today | Which fields to promote into `clean_jobs` |
| tech_stack extraction | Keyword (deterministic) vs LLM (best) — §5 | **Keyword-first vs LLM-in-pipeline** — key design decision |
| dedup/identity key | `(source, external_id)` + content_hash | — |
| internship filtering | Per-source mechanisms found (§7) | Title-keyword list to accept |

### Now decidable by you (no further research needed)
1. **Primary source = Tier A ATS public APIs** (recommend Greenhouse + Lever + Ashby
   to start), USAJobs optional for federal coverage.
2. **Curated company list** for the ATS boards (which companies' boards to pull).
3. **tech_stack = keyword dictionary for MVP**, LLM extraction deferred (recommended).
4. **Clean-schema width** — keep narrow (today's 4 cols) or promote location/url/
   posted_date. Recommend adding at least `source_url` + `posted_date` (cheap, high
   trust value) and deferring salary/remote.
5. **Batch, re-runnable script**; no scheduler in MVP.
6. **Provider-agnostic acquisition interface** with ATS adapter(s) now, scraper
   adapter as a future slot.

### Still genuinely needing a decision (product/risk, not research)
- Which **companies** seed the curated ATS list (affects realism & internship volume).
- Whether **USAJobs** is in-scope (adds a keyed source + federal domain).
- Final **clean_jobs schema width** (drives prompt-layer changes).
- Whether ingestion may ever contain an **LLM step** (the §5 fork).

---

## 9. Recommended shape for the design doc

Based on the above, the ingestion stage the design doc should describe:

1. **Acquisition layer** (`src/services/ingestion/`, isolated from API/agent per
   CLAUDE.md): provider-agnostic `JobSource` interface; ATS adapters
   (Greenhouse/Lever/Ashby) as the concrete MVP implementations; optional scraper
   adapter slot left unimplemented.
2. **Raw landing:** `raw_jobs` table, verbatim payload + provenance, upsert on
   `(source, external_id)`.
3. **Transform:** HTML→text, deterministic **keyword-based tech_stack extraction**,
   internship title-filter, normalize into `clean_jobs`.
4. **Loader:** idempotent batch CLI; re-running refreshes without duplicating.
5. **Config:** company list, keyword dictionary, source toggles all in
   `config/settings.yaml`; models in `models.py` (per CLAUDE.md).
6. **Schema decision:** promote `source_url` + `posted_date` into `clean_jobs`;
   update `config/prompts.yaml` accordingly; defer salary/remote.

This keeps the MVP deterministic, dependency-light, legally clean, and within the
existing layered architecture.

---

## 10. Sources

- [6 ATS Platforms with Public Job Posting APIs (Cavuno)](https://cavuno.com/blog/ats-platforms-public-job-posting-apis)
- [6 ATS Platforms with Public Job Posting APIs (fantastic.jobs)](https://fantastic.jobs/article/ats-with-api)
- [How to Scrape Job Postings in 2026: Tools, Legal Risks, Alternatives (Cavuno)](https://cavuno.com/blog/job-scraping)
- [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html)
- [Scrapfly Pricing](https://scrapfly.io/pricing) · [Scrapfly Billing docs](https://scrapfly.io/docs/scrape-api/billing) · [Scrapeway Scrapfly Review 2026](https://scrapeway.com/web-scraping-api/scrapfly)
- [Adzuna API Overview](https://developer.adzuna.com/overview) · [Adzuna Terms of Service](https://developer.adzuna.com/docs/terms_of_service) · [Adzuna Search docs](https://developer.adzuna.com/docs/search)
- [USAJobs API Reference](https://developer.usajobs.gov/api-reference/) · [USAJobs API key request](https://developer.usajobs.gov/APIRequest/Index)
- [Skill-LLM: Repurposing General-Purpose LLMs for Skill Extraction (arXiv)](https://arxiv.org/html/2410.12052v1) · [Rethinking Skill Extraction using LLMs (arXiv)](https://arxiv.org/pdf/2402.03832)
- [Is Web Scraping Legal in 2026? (Browserless)](https://www.browserless.io/blog/is-web-scraping-legal) · [robots.txt Scraping Compliance (PromptCloud)](https://www.promptcloud.com/blog/robots-txt-scraping-compliance-guide/)
