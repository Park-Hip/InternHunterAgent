# Job-Site Comparison — Vietnamese Boards for AI/Data Ingestion

> **Status:** Research / pre-design. A running comparison of candidate job boards as
> data sources for InternHunterAgent's ingestion stage. Each candidate is scored on the
> same axes so the final source choice is evidence-based, not assumed. Findings here feed
> `research/archive/data-ingestion-stage.md` and the eventual ingestion design doc.
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
- Detailed write-up: `research/archive/data-ingestion-stage.md` §0.1

---
## Candidate 2 - ITviec (tested)

**Verdict:** Strongest tested `tech_stack` source, but not selected as the initial source.
See `scripts/scrape_itviec_spike.py` and D-034 for the retained evidence and source decision.

## Candidate 3 - TopDev (tested)

**Verdict:** Viable supplementary source with a simple access path, but not selected as the
initial source.
See `scripts/scrape_topdev_spike.py` and D-034 for the retained evidence and source
decision.

## Candidate 4 - TopCV (tested)

**Verdict:** The free AI/Data crawl path is insufficient because its scoped search is unreliable.
See `scripts/scrape_topcv_spike.py` and D-034 for the retained evidence and source decision.

## Candidate 5 - LinkedIn (deferred)

**Verdict:** Deferred from the Vietnamese-board MVP source path.
See D-034 and the source-market notes in `research/archive/data-ingestion-stage.md`.