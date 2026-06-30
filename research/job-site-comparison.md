# Job-Site Comparison — Vietnamese Boards for AI/Data Ingestion

> **Status:** Research / pre-design. A running comparison of candidate job boards as
> data sources for InternHunterAgent's ingestion stage. Each candidate is scored on the
> same axes so the final source choice is evidence-based, not assumed. Findings here feed
> `data-ingestion-stage.md` and the eventual ingestion design doc.
>
> **Target data (decided 06/2026):** IT jobs focused on **AI/Data** roles (AI Engineer,
> Data Scientist, Data/ML Engineer, Data Analyst). **All seniority levels** collected;
> internships only **flagged** (`is_internship`).

---

## Comparison axes (what we score every site on)

| Axis | Question it answers |
|---|---|
| **Access method** | Public JSON API, SSR HTML, or JS-rendered SPA? |
| **Anti-bot** | Cloudflare / rate-limit / login wall on the data path? |
| **Reliability** | Repeatable with the *simplest* client (no browser, no captcha)? |
| **Schedulable** | Headless, non-interactive, safe to cron? |
| **AI/Data scoping** | Can we precisely isolate AI/Data IT jobs? |
| **`tech_stack` quality** | Are postings tagged with real **technologies** vs. roles? |
| **Field richness** | What structured fields come back per job? |
| **Volume / freshness** | Enough AI/Data postings, kept up to date? |
| **Language** | Vietnamese / English / bilingual? |

> **Legend:** ✅ good · ⚠️ usable with caveats · ❌ blocked / unavailable · ❔ not yet tested

---

## Candidate scorecard (summary)

| Site | Access | Anti-bot | Reliability | AI/Data scoping | `tech_stack` | Verdict |
|---|---|---|---|---|---|---|
| **VietnamWorks** | ✅ public JSON API | ✅ none on API | ✅ 5/5, ~0.43s | ✅ `jobFunction` taxonomy (child 27) | ⚠️ skills mix tech + role | **✅ selected (baseline)** |
| **ITviec** | ✅ SSR via cloudscraper | ✅ CF cleared **5/5** | ✅ 5/5, ~0.82s | ✅ curated **AI/Data segment** (no noise) | ✅ **real tech tags, role/domain split out** | **✅ tested — strongest `tech_stack` source** |
| **TopDev** | ✅ RSC payload in HTML | ✅ **zero anti-bot** (plain httpx) | ✅ 5/5, ~1.07s | ⚠️ paginate + client-side filter (~23% density) | ✅ **real tech tags** (`skills_str`, no role mixing) | **✅ tested — zero anti-bot, strong `tech_stack`** |
| TopCV | ⚠️ SSR HTML via cloudscraper | ⚠️ CF: listing OK, **search 403-walls** | ⚠️ listing 5/5; **scoped 1/4** | ⚠️ keyword-slug only (no taxonomy) | ❌ roles, not tech | **⚠️ tested — free path insufficient for scoped crawl** |
| LinkedIn | ❔ JS render, heavy anti-bot/ToS | ❌ heaviest | ❔ | ❔ | ❔ | ❔ deferred |

---

## Candidate 1 — VietnamWorks ✅ (selected baseline)

**One-line verdict:** the only candidate reachable with the *simplest* client (a plain
HTTP POST, no auth, no browser, no anti-bot), and its structured `jobFunction` taxonomy
lets us scope AI/Data precisely. Measured **5/5 reliable, ~0.43s/request, schedulable.**

### How it's accessed
A single public JSON endpoint that the website itself calls:

```
POST https://ms.vietnamworks.com/job-search/v1.0/search
```

No login, no API key. We send the same headers a browser would (`User-Agent`,
`Origin`/`Referer`) and receive the same JSON. The SSR HTML page is **not** the data path
— it carries only ~5 promoted jobs; the API has the real result set. (The site's old
**Algolia** search keys are dead — DNS no longer resolves.)

### How you search (request body)
```json
{
  "userId": 0,            // anonymous
  "query": "data engineer", // keyword — matches title AND description (broad/noisy)
  "filter": [],           // exact-match on TOP-LEVEL SCALAR fields only
  "ranges": [],           // numeric ranges (e.g. salary)
  "order": [],            // sort, e.g. onlineOn desc = newest first
  "hitsPerPage": 50,      // page size (~50 max)
  "page": 0               // 0-indexed; paginate by incrementing
}
```

- **`query`** drives *recall* but is noisy (matches description text, so a Marketing role
  mentioning "data" can appear).
- **`filter`** only works on flat scalar fields — verified: `jobLevelId`, `typeWorkingId`,
  `companySizeId`, `yearsOfExperience` are honored; **`jobFunction` is ignored** because
  it's a nested object. So the server **cannot** narrow to AI/Data for us.
- **`order: onlineOn desc`** = newest-first → enables cheap incremental scheduled runs.

### How we get precision — the `jobFunction` taxonomy
Every job carries a structured category, not just free text:

```json
"jobFunction": {
  "parentId": 5, "parentName": "Information Technology/Telecommunications",
  "children": [ { "id": 27, "name": "Data Engineer/Data Analyst/AI" } ]
}
```

IT = `parentId 5`. Its child categories (mapped from live data):

```
25 Business/System Analysis      32 System/Cloud/DevOps Engineer
26 Database Administration        33 IT Project/Product Management
27 Data Engineer/Data Analyst/AI  34 QA/QC/Software Testing
30 IT Management                  35 Security
                                  36 Software Developer
```

`child 27` = exactly the AI/Data roles. (ML/AI roles occasionally land in `36 Software
Developer`; a keyword-gated widen to {27, 36} would lift recall if needed.)

### Search strategy: keyword recall + structured precision
1. **Recall** — fire several AI/Data keywords (`data scientist`, `AI engineer`,
   `machine learning`, …), paginate, dedupe by `jobId`.
2. **Precision** — in our code, keep jobs where `parentId == 5` **and** child `27` present.
   This drops the keyword noise. Server-side filtering can't do this (see above).

### Fields available per job (~90 total; useful subset)
| Field | Use |
|---|---|
| `jobId` | stable external id (our key) |
| `jobTitle`, `companyName`, `companyId` | core identity |
| `jobLevel` / `jobLevelVI` / `jobLevelId` | seniority (string + structured id) |
| `jobFunction` | structured category → AI/Data precision |
| `skills` (`{skillName, skillWeight}`) | `tech_stack` candidate + relevance score |
| `jobDescription`, `jobRequirement` | full text (HTML, needs stripping) |
| `address`, `workingLocations[].cityId` | free-text + structured city id |
| `prettySalary`, `salaryMin/Max`, `isSalaryVisible` | pay (often hidden) |
| `onlineOn`, `approvedOn`, `expiredOn` | freshness / dedup / drop expired |
| `industriesV3`, `benefits`, `yearsOfExperience`, `numOfApplications` | enrichment |

### Measured results (`scripts/scrape_spike.py`)
| Metric | Result |
|---|---|
| Reliability | **5/5 runs OK (100%)**, zero 403/429 |
| Latency | **~0.43s median** |
| Yield (8 keywords × 2 pages) | **251 unique → 145 IT → 112 AI/Data** |
| Levels | all collected; **2 interns flagged** |
| Core / description / skills completeness | **100% / 100% / 98%** |
| Schedulable | **YES** — daily cron is ample |

### Reliability & scheduled-run risks
The 5/5 measurement above is a *single short run*. Sustained scheduled scraping carries
risks the one-off test does not surface. Each is rated by **likelihood** (for a small,
polite daily job) with a mitigation.

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Rate-limit / 429** from too many requests | Low (8 keywords × 2 pages ≈ 16 calls/day, 0.6s apart) | Run yields partial data | Keep the polite delay; cap pages; back off + retry on 429; spread keywords over time |
| **IP block / ban** after repeated runs | Low–Med (single IP, fixed UA, no auth) | Source goes dark | Rotate UA modestly; honor robots.txt; daily (not hourly) cadence; alert on a run of failures |
| **API contract change** (fields renamed, endpoint moved, payload shape) | Med (undocumented API, no versioning guarantee) | Silent bad/empty data | Validate response schema each run (assert `meta.nbHits`, required fields); pin shape behind an adapter; fail loud, don't write garbage |
| **`jobFunction` taxonomy changes** (child 27 renumbered/split) | Low–Med | AI/Data filter silently drops everything | Assert the focus set is non-empty; log child-id distribution; alert if IT→AI ratio collapses |
| **Cloudflare added to the API** (currently absent) | Low today, possible anytime | Plain client starts 403-ing | Detect 403/challenge HTML; fall back to a cloudscraper path (same as ITviec/TopDev) |
| **Empty / promoted-only response** (the SSR-HTML trap) | Low (we use the API, not HTML) | Looks successful but near-zero real jobs | Assert minimum expected yield; compare against last run's count |
| **Duplicate / expired postings** accumulating | Med | Stale `clean_jobs` | Dedup by `jobId`; drop rows past `expiredOn`; use `onlineOn` for incremental pulls |
| **ToS / legal** (scraping an undocumented endpoint) | — | Project-level | Review robots.txt + ToS before production; keep volume low and identifiable |

**Health checks a scheduled run should emit** (so failures are visible, not silent):
HTTP success rate, total + per-keyword yield, IT→AI/Data ratio, field-completeness %, and
a delta vs. the previous run. A sharp drop in any is the early-warning signal that one of
the risks above has materialized.

**Overall scheduled-run posture:** **green for a small daily cron today** — no anti-bot on
the API, stable shape, low volume. The dominant *residual* risk is the **undocumented API
changing or gaining Cloudflare** with no warning; that is a detection + fallback problem,
not a blocker, and the health checks above turn it from silent corruption into a loud,
recoverable alert.

### Strengths
- Simplest possible client; no anti-bot path → high reliability, easy to schedule.
- Structured `jobFunction` taxonomy gives precise AI/Data scoping for free.
- Rich per-job fields (dates, skills with weights, structured location/level).
- Good volume of genuine AI/Data postings (112 in one small run).

### Weaknesses / caveats
- **`skills` mixes technologies with role/soft terms** (e.g. "Power BI & Data Analytics",
  "Business Intelligence") — deriving a clean `tech_stack` still needs a technology filter.
- General-board keyword noise requires the client-side `jobFunction` precision step.
- It's an **undocumented** site API — request shape can change; pin it behind an adapter
  and check the host's robots.txt / ToS before production.
- Salary is hidden on most postings (`isSalaryVisible=false`).
- Postings are predominantly **Vietnamese** (cross-cutting language decision still open).

### Evidence
- Spike: `scripts/scrape_spike.py`
- Sample output: `research/experiments/vietnamworks_ai_data_sample.json` (112 records)
- Detailed write-up: `research/data-ingestion-stage.md` §0.1

---

## Candidate 2 — ITviec ✅ (tested — strongest `tech_stack` source)

**One-line verdict:** the only candidate that wins on **all three** axes this project cares
about at once — free `cloudscraper` **clears Cloudflare reliably (5/5, ~0.82s)**, a curated
**AI/Data segment** gives noise-free scoping, and every posting carries **real technology
tags** with roles/industry kept in *separate* fields. It directly fixes VietnamWorks' one
real weakness (dirty `tech_stack`) and is the obvious lead source for tech tags.

### How it's accessed
SSR HTML through a `cloudscraper` client. A *plain* `requests` GET returns **403
Cloudflare**; `cloudscraper` cleared it on **5/5** requests with zero challenges — so the
"403 Cloudflare" noted earlier is a non-issue for the free anti-bot path.

```
GET https://itviec.com/segments/viec-lam-ai-data            # curated AI/Data listing (SSR)
GET https://itviec.com/it-jobs/{role-company-slug}-{job-id} # detail page
```

- **Crawl surface:** the **"Việc làm AI, Data" segment** is fully **server-rendered**
  (~1.5 MB, ~274 jobs in one page) — no pagination needed for a spike, no JS. (By
  contrast the `/it-jobs/<skill>` *category* pages are JS-rendered — job cards are absent
  from static HTML — so the **segment page is the crawl surface**, not the category page.)
- **`{job-id}`** is the trailing number on the detail slug (`…-money-forward-…-3051` →
  `3051`) → a stable `external_id` for dedup.
- **robots.txt** allows everything except `/subscriptions/new`; our paths are clear.

### AI/Data scoping — curated segment (no keyword noise)
ITviec **curates** an AI/Data segment, so scoping needs **no keyword recall + no
client-side precision filter** at all — unlike VietnamWorks (keyword recall → `jobFunction`
precision) and TopCV (keyword-only, noisy). The 15 sampled jobs were *all* on-target:
*Senior AI Developer (ML/Python/SQL)*, *Middle Data Analyst (SQL, Power BI, English)*,
*Senior Data Analyst*, *Chuyên gia xây dựng mô hình phát hiện gian lận*, etc.

### `tech_stack` quality — the headline (real technologies, role/domain separated)
Each detail page splits its tags into **three labelled boxes**, which is exactly the
distinction every other board forces us to reconstruct:

| Box | Example values | Maps to |
|---|---|---|
| **Skills:** | `Python, SQL, Golang, Azure, MLOps, ERP, Power BI, C++, Unreal Engine, LLM, Prompt Engineering, Pandas` | **`tech_stack` — usable as-is** |
| **Job Expertise:** | `Backend Developer, AI Architect, Data Analyst` | role label (kept separate) |
| **Job Domain:** | banking, games, … | industry enrichment |

So `tech_stack_candidate` = the **Skills box verbatim** — no technology-vs-role filtering
needed (the work VietnamWorks' `skills` and TopCV's tags both require). **Caveat:** the
Skills box displays a **capped set (~5–6 tags/job** in the sample: median 6, max 6), so it
may under-list the full stack; the description still carries the rest for backfill.

### Fields available per detail page
`external_id` (trailing job-id), `title` (h1), `company` (`.employer-name`), `Skills` /
`Job Expertise` / `Job Domain` (labelled boxes), `description` (`section.job-content`,
bilingual), `last_updated` (explicit *"Last updated: …"* stamp → great freshness signal),
`location`/working-model (labelled chips when present). **Salary is usually gated**
("*Sign in to view salary*") — same hidden-pay limitation as VietnamWorks.

### Measured results (`scripts/scrape_itviec_spike.py`)
| Metric | Result |
|---|---|
| Bypass reliability | **5/5 real HTML, 0 challenges** |
| Latency | median **0.82s** / max 0.85s |
| AI/Data scoping | curated segment → **264 detail URLs** → **15 parsed** |
| Field completeness | external_id / title / company / description / **tech_stack = 100%** |
| Tech tags/job | median **6**, real technologies; role + domain in separate fields |
| Anomalies | none (reliability and detail) |

### Strengths
- Free `cloudscraper` **clears Cloudflare reliably** — no paid anti-bot needed today.
- **Curated AI/Data segment** = precise scoping for free, zero keyword noise.
- **Real technology tags, pre-separated from roles/industry** → cleanest `tech_stack` of
  any candidate; directly fixes VietnamWorks' main weakness.
- IT-only board (no Sales/RE/Marketing noise); **bilingual EN/VI** eases text handling.
- Explicit `Last updated` stamp + stable trailing-id `external_id`.

### Weaknesses / caveats
- **SSR HTML, not a JSON API** → selector-fragile, more maintenance than VietnamWorks'
  structured JSON; pin behind an adapter and validate the labelled-box structure each run.
- **Skills box is capped (~5–6 tags)** → may under-list the full stack (backfill from
  description if a fuller `tech_stack` is needed).
- Salary usually **gated** behind sign-in.
- Depends on `cloudscraper` holding against future Cloudflare tightening (today: clean);
  Scrapfly remains the fallback if that changes.

### Evidence
- Spike: `scripts/scrape_itviec_spike.py`
- Sample output: `research/experiments/itviec_ai_data_sample.json` (15 AI/Data records)
- Structural probes (cloudscraper clears CF, segment is the SSR surface, detail-URL shape,
  three-box tag separation): run live this session.

### Net call
**ITviec is now a co-lead with VietnamWorks — and the better source for `tech_stack`.**
This matches the ingestion-doc recommendation to *"lead with ITviec for clean technology
tags."* Suggested split: **VietnamWorks** for structured-JSON reliability + numeric fields,
**ITviec** for clean technology tags and noise-free AI/Data scoping — dedupe cross-board by
title+company. The only thing keeping VietnamWorks as the *primary* baseline is its no-
anti-bot JSON path; on the AI/Data + `tech_stack` axes that define this project, ITviec is
ahead.

---

## Candidate 3 — TopDev ✅ (tested — strongest anti-bot posture; strong `tech_stack` source)

**One-line verdict:** plain `httpx` clears TopDev with **zero anti-bot friction** (no
Cloudflare, no `cloudscraper` — simpler than every other candidate). Job data is
embedded in a **React Server Components (RSC) streaming payload** in the HTML, parsed
with plain regex + `json.loads`. `skills_str` carries **real technology tags** (SQL,
Python, Machine Learning, Spark, Kafka…) pre-separated from role labels — matching
ITviec's quality. Measured **5/5 reliable, ~1.07s median, 100% field completeness.**

### How it's accessed
Next.js App Router with React Server Components streaming. The HTML response (~1.9 MB)
contains the job data embedded in `self.__next_f.push([1, "..."])` chunks that together
form a 1.3 MB RSC payload — parseable entirely with regex + `json.loads`. No
`__NEXT_DATA__` blob (Pages Router style); no hidden JSON/GraphQL API discovered at
`api.topdev.vn` (all REST path guesses returned 404).

```
GET https://topdev.vn/jobs?page=N          # listing page — 15 promoted IT jobs/page
GET https://topdev.vn/detail-jobs/{slug}-{id}  # detail page — full job record
```

- **Anti-bot**: plain `httpx` GET returns 200 every time. The only "cloudflare" in the
  HTML is a `cdnjs.cloudflare.com` CDN asset link — **no challenge, no interstitial**.
  This is the best anti-bot posture of any candidate tested; `cloudscraper` is not
  needed and was not used.
- **Crawl surface**: the listing page always embeds the same 15 promoted/paid IT jobs
  regardless of query string (`?q=...` has **no effect** on the embedded RSC jobs). Only
  page number (`?page=N`) changes the job set. AI/Data filtering is done client-side
  by matching `skills_str` and `title` against AI/Data keywords.

### How we scope to AI/Data
No dedicated AI/Data segment (unlike ITviec's `/segments/viec-lam-ai-data`). Instead:
- Paginate `https://topdev.vn/jobs?page=N` to collect 15 promoted IT jobs per page.
- Filter by `skills_str` + `title` for AI/Data keywords (Python, Machine Learning, Data
  Science, Data Engineer, Spark, NLP, etc.).
- Measured AI/Data density: **~23% of promoted jobs are AI/Data** (17 found in 75 jobs
  across 5 pages). With MAX_PAGES=3 (45 jobs scanned), typically 10–15 AI/Data jobs
  found per run.

### Detail URL shape and `external_id`
- **URL pattern**: `https://topdev.vn/detail-jobs/{slug}-{job_id}` — `detail_url` field
  in the listing RSC gives the full URL directly.
- **`external_id`**: the integer `id` field in the RSC job object (e.g., `2115417`).
  Also embedded as the trailing numeric segment of the slug.

### `tech_stack` quality — real technology tags (no role mixing)
The `skills_str` field in the RSC listing payload is a **comma-separated string of real
technology tags**: no roles, no vague soft-skill labels. Example values:

| Job | `skills_str` |
|---|---|
| Data Analytics Consultant | `SQL, Python, Data Analytics, Machine Learning, Data Science, Azure, PySpark` |
| AI Engineer | `Python, Git, Docker, Database, Machine Learning, API, AI` |
| Data Engineer (pipeline) | `Data Engineer, Spark, ETL, Kafka, Data Architecture` |
| Senior Data Analyst | `SQL, Python, VBA, Tableau, Data Analyst, Power BI` |

This is on par with ITviec's Skills box — **real technologies as-is, no role/tech
entanglement** — and it comes directly from the listing RSC (no detail page fetch needed
for tech tags).

**Caveat**: `skills_str` is capped (~4–7 tags/job in the sample; median 4, max 7),
similar to ITviec. The detail page's `requirements`/`responsibilities` blocks provide
the full description for supplementary tech mining.

### Fields available per record
From the **listing RSC** (no detail fetch needed for these):

| Field | Value |
|---|---|
| `id` | stable numeric `external_id` |
| `title` | job title (Vietnamese/English bilingual) |
| `skills_str` | real tech tags (comma-separated) |
| `company.display_name` | company name (RSC reference, resolved inline) |
| `addresses.address_region_list` | location string (RSC reference, resolved inline) |
| `salary.value` | salary info (often "Negotiable"; RSC reference) |
| `job_levels_str` | seniority string ("Junior, Middle, Senior") |
| `expires.date` | deadline date (RSC reference) |
| `detail_url` | full detail page URL |

From the **detail page RSC** (richer):

`requirements`, `responsibilities`, `why_you_should_apply`, `why_you_stay` — HTML
blocks with full job description text; decoded and concatenated for `description`.

### Measured results (`scripts/scrape_topdev_spike.py`)
| Metric | Result |
|---|---|
| Acquisition reliability | **5/5 real RSC data, 0 challenges** |
| Latency | median **1.07s** / max 1.24s |
| AI/Data scoping | 3 listing pages (45 jobs) → **12 AI/Data** → **12 parsed** |
| Field completeness | external_id / title / company / description / **tech_stack = 100%** |
| Tech tags/job | median **4**, max **7** (real technologies) |
| Anomalies | none (reliability + detail) |

### Strengths
- **Zero anti-bot** — plain `httpx` works; no `cloudscraper`, no paid anti-bot.
  Simplest access path of all candidates.
- **Real technology tags** (`skills_str`) with no role mixing — comparable to ITviec's
  Skills box; directly usable for `tech_stack` without filtering.
- IT-developer-only board → lower noise than general boards (VietnamWorks, TopCV).
- Bilingual EN/VI content; `detail_url` is directly embedded; stable numeric `id`.
- Rich detail page content (requirements, responsibilities, why-join sections).

### Weaknesses / caveats
- **No curated AI/Data segment** — must paginate promoted listing and filter client-side
  (~23% density); ITviec's curated segment gives 100% on-target precision.
- Scoping relies on the **promoted/paid** job set (not full site inventory). Job density
  depends on which paying employers are actively promoted at crawl time.
- RSC payload structure is **proprietary and undocumented** — a Next.js upgrade or RSC
  format change could break the parser silently. Pin behind an adapter and validate
  job record count each run.
- `skills_str` is **capped at ~4–7 tags** — may under-list a full stack; detail
  description backfills the rest.
- `description` field requires **detail page fetch** (listing RSC has empty `content`
  for most jobs).
- Salary is usually `"Negotiable"` — hidden salary is common on Vietnamese IT boards.

### Evidence
- Spike: `scripts/scrape_topdev_spike.py`
- Sample output: `research/experiments/topdev_ai_data_sample.json` (12 AI/Data records)
- Phase-0 probes: anti-bot floor (plain httpx 200/5), RSC payload structure, no
  discoverable public API at `api.topdev.vn`, pagination behavior, detail URL shape,
  field locations — all confirmed live this session.

### Net call
**TopDev is a viable third source alongside VietnamWorks (baseline) and ITviec
(tech_stack leader).** Its zero-anti-bot access is the simplest of any candidate; its
`skills_str` real-tech tags rival ITviec's quality; and being IT-only reduces noise.
The main limitation vs. ITviec is the absence of a curated AI/Data segment (must
paginate and filter). Suggested role: **supplementary source** for broadening AI/Data
coverage with a higher `tech_stack` signal than VietnamWorks — schedule alongside
ITviec in the daily crawl.

---

## Candidate 4 — TopCV ⚠️ (tested — free path insufficient for an AI/Data crawl)

**One-line verdict:** `cloudscraper` clears Cloudflare on TopCV's *generic* listing
reliably (5/5, ~0.87s), but the **AI/Data-scoped search path we actually need gets one
200 then a wall of 403 "Just a moment…" challenges** (1/4 reliable, even at 5s spacing).
Add that TopCV has **no structured taxonomy** (keyword-slug scoping only) and **tags are
roles, not technologies**, and it loses to VietnamWorks on every axis that matters here.
Usable only as a *supplementary* source, and only behind a paid anti-bot (Scrapfly).

### How it's accessed
SSR HTML (not the API path VietnamWorks offers) reached through a `cloudscraper` client:

```
GET https://www.topcv.vn/tim-viec-lam-internship            # generic listing
GET https://www.topcv.vn/tim-viec-lam-ai-engineer           # keyword-slug "search"
GET https://www.topcv.vn/viec-lam/{title-slug}/{job-id}.html # detail page
```

- **Scoping is URL-keyword-based:** `tim-viec-lam-<keyword>` slugs act as the search.
  `…-ai-engineer` resolves to a real result page (title: *"Tuyển dụng 91 việc làm Ai
  Engineer [Update 30/06/2026]"*, 43 detail links on page 1) — so AI/Data *recall* via
  keyword exists.
- **`{job-id}`** in the detail URL (`/viec-lam/{slug}/{id}.html`) is a stable
  `external_id` for dedup — the one clearly good primitive.
- There is **no public JSON endpoint** and **no structured category object** on the job;
  everything is HTML-scraped with fragile selectors.

### Anti-bot — the decisive finding (two-tier Cloudflare)
TopCV's Cloudflare posture is **not uniform**, and the difference is exactly backwards
for our needs:

| Path | Behaviour with free `cloudscraper` |
|---|---|
| **Generic internship listing** + detail pages | Clears reliably — **5/5** listing runs returned real HTML, ~0.87s median; 13/15 detail pages parsed (two `429`s at the tail). |
| **AI/Data keyword search** (`…-ai-engineer`) | **One 200, then 403 `Just a moment…` JS-challenge on every subsequent request** — measured **1/4**, with ≥5s spacing and a fresh scraper. cloudscraper cannot solve the interstitial. |

The scoped search endpoints (the ones an AI/Data crawler must paginate) are behind a
**stricter managed-challenge rule** than the SEO-cached generic listing. So the free path
clears the page we *don't* want and walls the page we *do*.

### AI/Data scoping
- **Possible but weak.** Recall exists via keyword-slug URLs (91 AI Engineer hits), but
  there is **no `jobFunction`-style taxonomy** to enforce precision the way VietnamWorks
  does with `parentId 5 / child 27`. TopCV is a **general board**, so keyword search drags
  in noise with no structured field to filter it back out server- or client-side.
- The generic internship listing confirms the noise concretely: a 2-page crawl yielded
  **Real Estate, Marketing, Accounting, PCCC-maintenance** interns — essentially **zero**
  AI/Data IT roles (see sample below).

### `tech_stack` quality — roles, not technologies
TopCV's on-page tags are **SEO role/category anchors** (`tim-viec-lam-<role>`), e.g.
*"Sales bất động sản/Môi giới"*, *"B2C"*, *"Telesales"*, *"Marketing/PR/Quảng cáo"*,
*"Kinh doanh/Bán hàng"* — plus breadcrumb/location chips. There is **no structured skills
array** (no VietnamWorks-style `{skillName, skillWeight}`). A real `tech_stack` could only
be **mined from the free-text description with NLP**, not harvested from tags. This is
strictly worse than VietnamWorks (whose `skills` at least *mix in* technologies) and far
worse than ITviec's expected pure-tech tags.

### Fields available per detail page
Scraped from HTML (selector-fragile, no structured ids): `title`, `company`, `location`
(free-text address), `salary` (often *"Thu nhập Từ 2 triệu"*), `deadline` (text, e.g.
*"Hạn nộp hồ sơ: 22/07/2026"*), `description` (HTML→text), raw `tags` (roles). **Missing
vs. VietnamWorks:** structured seniority id, structured city id, skill weights, online/
approved/expired dates, application counts, salary min/max.

### Measured results
| Metric | Generic listing path | AI/Data scoped path |
|---|---|---|
| Bypass reliability | **5/5** real HTML, 0 challenges | **1/4** (3× 403 `Just a moment…`) |
| Latency | median 0.87s / max 0.95s | 1.25s on the one success |
| Collected | 2 pages → 94 detail URLs → **13 parsed** | 1 page → 43 detail URLs → **0 parsed** (detail 403'd) |
| Field completeness (on the 13) | external_id/title/company/description/tags = **100%** | — |
| AI/Data relevance of yield | **~0%** (RE/Marketing/Accounting interns) | would be high *if reachable* |
| Anomalies | 2× `429` on detail tail | wall of `403` challenges |

### Strengths
- Free `cloudscraper` **does** clear the generic listing reliably and fast.
- Stable `{job-id}` `external_id` in the URL; core fields present when a page loads.
- Large general-board volume; keyword recall for AI/Data exists (91 AI Engineer hits).
- Freshness is signposted (listing title carries an *"[Update DD/MM/YYYY]"* stamp).

### Weaknesses / caveats
- **The scoped path is the protected path.** Free `cloudscraper` walls after one request
  on keyword search → cannot paginate a scoped AI/Data crawl without a paid anti-bot
  (Scrapfly), which the design is trying to avoid.
- **No structured taxonomy** → AI/Data precision is keyword-only and noisy.
- **Tags are roles, not technologies** → `tech_stack` needs description NLP, not tag
  harvesting.
- **No JSON, selector-fragile HTML** → higher maintenance, silent breakage risk.
- Predominantly **Vietnamese**; salary usually a vague band.

### Evidence
- Spike (generic listing, reliability + field yield): `scripts/scrape_topcv_spike.py`
- Sample output: `research/experiments/topcv_cloudscraper_sample.json` (13 records — all
  non-AI/Data, illustrating the general-board noise)
- Scoping + tag-box probes (keyword search reachability, two-tier 403 wall): run live this
  session; reproduce by pointing the spike's listing URL at `…-ai-engineer`.

### Net call
**Keep VietnamWorks as the baseline.** TopCV is a *supplementary* candidate at best: its
free path can't sustain a scoped AI/Data crawl, it lacks the taxonomy that makes
VietnamWorks precise, and its tags don't give us `tech_stack`. Only revisit TopCV **if**
the project (a) adopts Scrapfly for other sources anyway, and (b) wants TopCV's general
volume on top of VietnamWorks' precision.

---

## Candidate 5 — LinkedIn ❔ (deferred)

*Not tested.* JS-rendered with the heaviest anti-bot and the strictest ToS. Included only
for its Vietnam-localized postings; lowest priority for the baseline.
