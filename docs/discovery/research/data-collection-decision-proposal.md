# Stable, lawful, low-cost data collection — research-led decision

**Status:** Proposal only. No code, accounts, scraping, downloads, purchases, configuration changes, or production data collection were performed.

**Change tier:** **Research-led** — confirmed from `AGENTS.md`: this is an uncertain, architectural, and potentially irreversible choice. The change-proposal policy requires approval before implementation. This temporary report is not a decision-log update and is the requested approval artifact.

**Evidence labels:** **[V] verified** by a primary official API/documentation/terms/pricing page; **[PV] partially verified** (a primary source establishes part of the claim, but current Vietnam availability, permission, or field behavior is not established); **[U] unverified** (not enough primary evidence); **[I] inferred** from the documented capability and stated constraints. “Public” or unauthenticated does **not** mean permission to automate collection.

**Scope boundary:** The product may report observations in its own sourced dataset. It must not claim these observations represent all Vietnam jobs, all employers, or actual hires.

## TL;DR — decision request

**Approve:** start with a small, declared cohort of Vietnamese AI employers using direct career pages, documented ATS feeds, and written permission where possible. Preserve original URLs and evidence; report only what this cohort observes.

**Do not approve yet:** broad scraping of Vietnam job boards, use of undocumented VietnamWorks access, or a Bright Data commitment. A public endpoint or a free credit is not evidence of permission.

**Scale path:** negotiate one written job-board data licence in parallel. Use SerpApi/DataForSEO only to discover original pages, never as the canonical source. Bright Data is a later, capped pilot only if its licence and source coverage fit.

**Why:** this is the lowest-cost path that can remain traceable and lawful, but it deliberately does not claim nationwide coverage.

---

## 1. Executive summary

1. **No presently evidenced single, free, Vietnam-wide, production-safe feed exists.** [I] Local-board APIs found in this review are employer/partner-facing or undocumented for third-party analytics; several large global APIs require a partnership. [PV]
2. **Best low-cost and lawful MVP path:** start with a deliberately bounded, consent-first cohort of Vietnamese AI employers and their direct career sites, using documented public ATS feeds/APIs only after a source-by-source Terms/robots/access review. Keep original URLs and immutable raw evidence. [I]
3. **Best expansion path:** obtain a written board/data-license partnership (VietnamWorks, ITviec, CareerViet, TopCV, or another board) rather than build the product around an undocumented endpoint. Availability, price, data-use rights, and redistribution rights are currently **unverified** and must be negotiated. [PV]
4. **Discovery fallback:** a job SERP provider (SerpApi or DataForSEO) can find candidate original pages cheaply, but its results are not a durable source of truth. Ingest a full description only from the permitted original source; retain the search result merely as discovery evidence. [I]
5. **Do not make a provider or scraper actor the primary data source.** Bright Data, Apify actors, JSearch, and similar services may be operationally convenient, but their target coverage, terms, and resale/redistribution terms do not establish that InternHunterAgent can retain and publish/reproduce job descriptions. [PV]

**Recommendation for approval:** approve a **source-controlled hybrid**: (a) documented direct company/ATS feeds and explicit employer permission as the only initial ingestion sources, (b) a formal board-license track as the coverage expansion gate, and (c) paid SERP/provider discovery only as a capped, non-authoritative fallback. Do **not** approve broad source-agnostic scraping or a single-vendor feed dependency.

---

## 2. Explicit InternHunterAgent data requirements

These are user-stated requirements, recorded as acceptance criteria **[V: supplied context]**:

- Identify Vietnamese AI-related roles across seniority levels.
- Preserve title, company when available, location, published date, full job description, source URL, and a citation to the original posting.
- Support requirement extraction, frequency and career-level comparisons, and later trend analysis.
- Preserve enough provenance to reproduce or audit an observation.
- Describe findings as observations in the collected dataset, never as a census of Vietnam jobs or actual hiring.

**Non-negotiable collection contract [I]:**

| Field / control | Requirement |
|---|---|
| `source_url` | Canonical original posting URL, not only an aggregator result. |
| `retrieved_at`, `observed_at` | UTC timestamps for every observation. |
| `published_at` | Keep source value and precision; distinguish missing, relative, and inferred dates. |
| `source_name`, `source_type`, `access_basis` | Identify board/employer/ATS and whether access is explicit permission, documented public feed, license, or manual evidence. |
| Raw evidence | Store raw JSON/XML/HTML or permitted evidence excerpt, content type, status, hash, and a retrieval audit record. Do not assume indefinite retention/republication rights. |
| Description | Keep original-language description plus normalization provenance; never silently replace it with a summary. |
| Company/location | Preserve raw and normalized values; location may be remote/multi-location/unknown. |
| Record lifecycle | First observed, last observed, source-published, source-updated, closed/removed/unknown state. |
| Analysis guardrail | Every output names the source set, collection window, filtering rule, missingness, and deduplication version. |

---

## 3. Scoring method

All scores are **preliminary [I]** and use **5 = most favorable**. For **engineering complexity**, 5 means lowest complexity. Scores judge the approach for this project, not the vendor generally.

`VC` Vietnam AI coverage; `FD` full description; `PD` published date; `CT` original-URL/citation traceability; `FR` freshness; `HI` historical potential; `DD` duplicate support; `TA` terms/access clarity; `CO` genuinely free/low starting cost; `LR` long-term reliability / low vendor dependence; `EC` low engineering complexity; `MVP` small-MVP fit.

A score is not legal advice. `TA ≤ 2` is an **approval gate**, not a reason to automate around the restriction.

---

## 4. Comparison: 30 distinct approaches

### A. Boards, official programs, and source discovery

| # | Approach | Evidence status | VC | FD | PD | CT | FR | HI | DD | TA | CO | LR | EC | MVP | Score rationale / constraints |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | VietnamWorks employer API / written data licence | [PV] | 5 | 5 | 5 | 5 | 5 | 3 | 4 | 2 | 2 | 4 | 3 | 3 | Official-looking OAuth documentation is available, but evidence found is community-hosted and describes employer access; a third-party analytics licence, price, rate limits, and reuse rights remain unverified. |
| 2 | VietnamWorks unauthenticated search endpoint | [PV] | 5 | 4 | 4 | 4 | 5 | 1 | 3 | 1 | 5 | 2 | 4 | 3 | Community empirical evidence reports an unauthenticated endpoint, not a published source-data licence. Treat as unsuitable until VietnamWorks grants written permission. |
| 3 | ITviec employer API / partnership | [PV] | 4 | 4 | 4 | 4 | 4 | 2 | 3 | 2 | 2 | 4 | 3 | 2 | IT-focused Vietnam coverage is attractive, but the documented API is employer-facing and full access terms/pricing are behind a relationship/login. |
| 4 | CareerViet partner integration / licence | [PV] | 4 | 4 | 3 | 4 | 4 | 2 | 3 | 2 | 1 | 4 | 3 | 2 | An ATS integration is evidenced, not a data-extraction programme. Negotiate data rights; do not infer them from integration credentials. |
| 5 | TopCV partner integration / licence | [PV] | 5 | 4 | 3 | 4 | 4 | 2 | 3 | 1 | 1 | 4 | 3 | 2 | Employer integration evidence exists; no public third-party job-data API or terms sufficient for collection were verified. |
| 6 | LinkedIn Job Posting API | [V] | 4 | 4 | 5 | 5 | 5 | 3 | 4 | 4 | 1 | 5 | 2 | 1 | Official documentation says new partnerships are not being accepted; unsuitable for a new small MVP. |
| 7 | Google JobPosting/Google Jobs as discovery | [V] | 4 | 3 | 4 | 4 | 5 | 1 | 2 | 4 | 5 | 3 | 4 | 4 | JobPosting markup exposes candidate source fields, but Google is a discovery layer—not permission to copy source descriptions and not a historical archive. |
| 8 | Direct local-board human/manual evidence capture | [I] | 4 | 5 | 4 | 5 | 2 | 3 | 5 | 4 | 3 | 5 | 5 | Safest way to respect a source restriction when a human checks the page and captures only approved evidence; labour cost prevents scale. |
| 9 | Source-specific board data licence / partnership | [PV] | 5 | 5 | 5 | 5 | 5 | 4 | 4 | 5 | 1 | 5 | 4 | 3 | The strongest board route if a contract grants intended analytic retention/use; current Vietnamese-board availability and cost are not publicly established. |
| 10 | Generic source-agnostic board scraper | [I] | 5 | 5 | 4 | 4 | 5 | 4 | 2 | 1 | 4 | 1 | 1 | 2 | High coverage is not a permission signal; selectors, anti-bot measures, terms changes, and source drift make this a rejected primary strategy. |

### B. Commercial APIs, scraping/data providers, and aggregators

| # | Approach | Evidence status | VC | FD | PD | CT | FR | HI | DD | TA | CO | LR | EC | MVP | Score rationale / constraints |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 11 | Bright Data Jobs Data API / data feed | [PV] | 3 | 4 | 4 | 3 | 5 | 4 | 3 | 4 | 2 | 2 | 4 | 3 | API and licence/pricing are documented; Vietnam volume/field completeness are not guaranteed. Licence restrictions can conflict with redistribution or a competing-data-product model. |
| 12 | Bright Data Web Scraper / Jobs Scraper | [PV] | 3 | 4 | 4 | 4 | 4 | 2 | 3 | 2 | 4 | 2 | 3 | 3 | Reported free record allowance is a provider offer, not a target-site licence. Target-specific terms, robots, and field quality need validation. |
| 13 | Apify board-specific Actors | [PV] | 4 | 4 | 4 | 4 | 4 | 2 | 3 | 2 | 4 | 2 | 4 | 3 | Marketplace actors can target Vietnam boards cheaply, but neither an actor listing nor platform terms prove target-board permission or resilience. |
| 14 | SerpApi Google Jobs API | [PV] | 4 | 3 | 3 | 3 | 5 | 1 | 2 | 3 | 4 | 2 | 5 | 3 | `gl=vn` and free/paid quotas are documented. Use only to discover candidates; SERP provenance and legal protection differ by plan. |
| 15 | DataForSEO Google Jobs SERP API | [PV] | 3 | 3 | 3 | 3 | 5 | 1 | 2 | 3 | 3 | 3 | 5 | 3 | Low per-task cost and no subscription lock-in are documented; Vietnam result quality and original-description availability are untested. |
| 16 | JSearch / OpenWeb Ninja via RapidAPI | [PV] | 3 | 3 | 3 | 3 | 4 | 1 | 2 | 2 | 4 | 2 | 5 | 2 | Cheap request tier, but an intermediary plus Google-derived coverage increases dependency and does not prove Vietnam-local-board completeness. |
| 17 | Jooble REST API | [V] | 2 | 3 | 3 | 3 | 3 | 1 | 2 | 4 | 5 | 3 | 4 | 2 | Official help says the per-key lifetime cap is 500 requests and separate country registration is needed; useful for a bounded feasibility check, not a durable feed. |
| 18 | Adzuna API | [V] | 1 | 3 | 4 | 3 | 4 | 3 | 2 | 4 | 4 | 3 | 4 | 1 | Official documented market list does not include Vietnam; exclude. |
| 19 | Google Programmable Search JSON API | [V] | 2 | 1 | 1 | 2 | 4 | 1 | 1 | 4 | 3 | 3 | 5 | 2 | It returns web links rather than a job feed. Free quota is discovery-only and does not give permission to fetch targets. |
| 20 | Serper/general search API | [PV] | 2 | 1 | 1 | 2 | 4 | 1 | 1 | 2 | 4 | 2 | 5 | 2 | A third-party search proxy can find URLs, but it is not a job-data source and sign-up credits are not a continuing free tier. |

### C. Historical/public data and ATS/employer approaches

| # | Approach | Evidence status | VC | FD | PD | CT | FR | HI | DD | TA | CO | LR | EC | MVP | Score rationale / constraints |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 21 | Common Crawl filtered archive | [V] | 2 | 2 | 2 | 2 | 1 | 5 | 1 | 2 | 5 | 5 | 1 | 1 | Free historical web corpus; underlying page rights remain with content owners, coverage is uncurated, and it is not suitable for current operational data. |
| 22 | Public Vietnam-job research/Kaggle/HF datasets | [PV] | 4 | 4 | 4 | 2 | 1 | 4 | 3 | 1 | 5 | 3 | 5 | 2 | Useful for exploratory/offline methodology only after checking each licence and source provenance; stale and not a live, permission-cleared production feed. |
| 23 | Internet Archive/Wayback CDX | [V] | 2 | 2 | 2 | 3 | 1 | 5 | 2 | 3 | 5 | 4 | 3 | 2 | Useful only for carefully qualified historical research; archived job pages are sparse and content rights still require review. |
| 24 | Greenhouse Job Board API for identified employers | [V] | 3 | 5 | 5 | 5 | 5 | 2 | 5 | 3 | 5 | 4 | 5 | 4 | Official public job-board API documents full content and first-published fields. Vietnam employer penetration and automated-use terms still need per-company/source validation. |
| 25 | Lever Postings API for identified employers | [V] | 2 | 5 | 4 | 5 | 5 | 2 | 5 | 3 | 5 | 4 | 5 | 3 | Official public postings API supplies description and hosted URL; local Vietnam coverage is unproven. |
| 26 | Ashby public job-posting API | [V] | 2 | 5 | 5 | 5 | 5 | 2 | 5 | 3 | 5 | 4 | 5 | 3 | Strong structured fields including publication time; likely startup/MNC skew and no Vietnam adoption measure. |
| 27 | Workable public widget API | [PV] | 3 | 5 | 5 | 5 | 5 | 2 | 5 | 3 | 5 | 4 | 5 | 4 | Widget behavior is documented/observed and has rich fields; verify source-level terms and Vietnam employer cohort before reliance. |
| 28 | SmartRecruiters public posting API | [V] | 2 | 3 | 5 | 4 | 5 | 2 | 4 | 3 | 5 | 3 | 4 | 3 | Official public list feed exists; full description typically requires a detail request and Vietnam coverage is unverified. |
| 29 | Workday public career board endpoints | [PV] | 3 | 4 | 2 | 5 | 5 | 2 | 4 | 2 | 5 | 2 | 3 | 3 | Public-career endpoint behavior is empirically documented, but source discovery is nontrivial, dates can be relative, and access terms require review. |
| 30 | Company sitemaps + `JobPosting` JSON-LD | [V] | 3 | 5 | 5 | 5 | 4 | 3 | 4 | 3 | 5 | 2 | 3 | 4 | Google documents the structured fields and canonical page rules. This is source-owned evidence but each employer’s robots/terms remain a collection gate. |
| 31 | Employer-provided RSS/XML/JSON feeds or written consent | [PV] | 3 | 5 | 5 | 5 | 5 | 4 | 5 | 5 | 5 | 4 | 4 | Highest legal clarity when the employer explicitly authorizes use; no Vietnamese employer feed inventory was verified, so it requires cohort-building. |
| 32 | Multi-source, source-specific adapters under one governed pipeline | [I] | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | 3 | 3 | Best resilience and analysis quality only when every component source itself passes a permission/access gate; more initial design work. |

**Unsuitable by default:** #2, #6, #10, #18–#23; and #11–#16 until both data-use rights and Vietnam-quality evidence are validated. This does not say they are illegal; it says their documented evidence is insufficient for the stated reliability gate.

---

## 5. Primary evidence and relevant passages

The table distinguishes primary documentation from community evidence. Links are supplied for verification before any procurement or collection.

| Evidence | Status | Relevant passage / what it establishes |
|---|---|---|
| [LinkedIn Job Posting API overview](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview?view=li-lts-2025-04) | [V] | “We are currently not accepting new partnerships for LinkedIn’s Job Posting API.” This rules it out for a new MVP. |
| [Google JobPosting structured-data documentation](https://developers.google.com/search/docs/appearance/structured-data/job-posting) | [V] | Google lists `datePosted`, `description`, `hiringOrganization`, `jobLocation`, and `title` among required/recommended job data and says markup belongs on a single job page, not a listing page. It establishes a field model, not reuse permission. |
| [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html) | [V] | Documents public GET job-board endpoints and `?content=true`, with fields including `absolute_url`, `updated_at`, and `first_published`. |
| [Lever postings API](https://github.com/lever/postings-api/blob/master/README.md) | [V] | Documents the public endpoint `https://api.lever.co/v0/postings/{site}?mode=json` and job posting payload form. |
| [Ashby public job-posting API](https://developers.ashbyhq.com/docs/public-job-posting-api) | [V] | Documents the public job-board endpoint and fields such as `descriptionHtml`, `publishedAt`, `jobUrl`, and `applyUrl`. |
| [SmartRecruiters Posting API](https://developers.smartrecruiters.com/docs/posting-api) | [V] | Documents public posting search/list APIs versus authenticated administrative APIs. |
| [Workable API documentation](https://help.workable.com/hc/en-us/articles/115013356548-Workable-API-Documentation) | [V] | Distinguishes the public careers/widget path from authenticated API access. Exact availability must still be checked for each employer board. |
| [Teamtailor API support](https://support.teamtailor.com/en/articles/5963369-use-our-teamtailor-api) | [V] | Documents API-key scopes for the authenticated API; it does not by itself prove rights to every public feed. |
| [Schema.org `JobPosting`](https://schema.org/JobPosting) | [V] | Defines standard properties used for job data provenance and normalization. |
| [Bright Data Jobs Data API](https://brightdata.com/products/data-feeds/jobs-data-api) and [pricing](https://brightdata.com/pricing/web-scraper) | [V] | Product/pricing documentation reports Jobs data and a Web Scraper price/free-record allowance. It does not state a Vietnam completeness guarantee. |
| [Bright Data licence](https://brightdata.com/license) | [V] | The cited restriction is: “Client shall not distribute, transmit, reproduce, publish, license, transfer, or sell any Data in order to offer a similar or competitive product.” Obtain contract interpretation before retaining/publishing descriptions. |
| [Apify pricing](https://apify.com/pricing) and [terms](https://docs.apify.com/legal/general-terms-and-conditions) | [V] | Establish platform credits/pricing and platform terms, not target-board permission. Actor-specific claims are [PV]. |
| [SerpApi Google Jobs](https://serpapi.com/google-jobs-api), [supported countries](https://serpapi.com/google-jobs-countries), and [pricing](https://serpapi.com/pricing) | [V] | Documents Google Jobs service, Vietnam country parameter support, and free/paid query limits. It does not guarantee a stable local-board corpus. |
| [DataForSEO Google Jobs pricing](https://dataforseo.com/pricing/google-serp/google-jobs-serp-api) and [API overview](https://docs.dataforseo.com/v3/serp-google-jobs-overview/) | [V] | Documents task pricing and configurable job-SERP requests; Vietnam result quality remains [PV]. |
| [Jooble REST API documentation](https://help.jooble.org/en/support/solutions/articles/60001448238-rest-api-documentation) | [V] | Documents country-specific API keys and a 500-request lifetime limit per key. |
| [Adzuna developer overview](https://developer.adzuna.com/) | [V] | Lists supported country endpoints; Vietnam is absent from the documented list reviewed. |
| [Google Custom Search overview](https://developers.google.com/custom-search/v1/overview) and [pricing](https://support.google.com/programmable-search/answer/9069107) | [V] | Documents the JSON search API, 100 free daily queries, and paid query pricing. It is web search, not a job-description feed. |
| [Common Crawl terms](https://commoncrawl.org/terms-of-use) | [V] | States that Common Crawl does not grant a broad licence to underlying web content; the original content owner’s rights remain relevant. |
| [VietJobs repository](https://github.com/VinNLP/VietJobs) and [paper](https://arxiv.org/html/2603.05262v1) | [PV] | Establishes a Vietnam job dataset/research artefact, but its downstream commercial/republication rights and source-by-source compliance need independent review. |
| [Internet Archive CDX/Wayback entry point](https://web.archive.org/) | [V] | Establishes archive availability; it does not supply a production licence or complete current-job coverage. |
| [VietnamWorks terms](https://www.vietnamworks.com/terms-of-use) | [PV] | Must be read and recorded clause-by-clause before collection. Community-hosted [employer API material](https://github.com/chrisshayan/vietnamworks/blob/master/employer-api-docs/README.md) is not sufficient evidence of an analytics licence. |
| [ITviec personal-data/API notice](https://itviec.com/blog/personal-data-usage-agreement-feature/) | [PV] | Establishes an employer/API/consent context but not third-party access rights or pricing. |
| [CareerViet/AMIS integration guide](https://helpamis.misa.vn/amis-tuyen-dung/kb/ket-noi-voi-san-tuyen-dung-careerviet/) and [TopCV/AMIS guide](https://helpamis.misa.vn/amis-tuyen-dung/kb/ket-noi-voi-san-tuyen-dung-topcv/) | [PV] | Evidence of B2B ATS integrations, not a general licence to retrieve board inventory. |

**Evidence quality note [V]:** Community GitHub PRs, scraper repositories, marketplaces, blogs, and search snippets were used only to locate candidate routes or corroborate endpoint behaviour. They are not sufficient final evidence for permission, pricing, or operational access.

---

## 6. Shortlist: best three approaches

### 1. Direct employer cohort: explicit consent plus documented public ATS/feed adapters

**Why it is first [I]:** It has the strongest provenance (original employer URL), supports full descriptions/dates where the ATS does, is potentially free to collect, and avoids a single intermediary. Start with a modest, declared employer cohort rather than pretend national coverage.

- **Evidence:** Greenhouse, Lever, Ashby, SmartRecruiters, Workable, and Google `JobPosting` documentation above. [V]
- **Access condition:** an employer’s career page must be identified; its terms/robots must permit the planned requests, or the employer must grant written permission. [I]
- **Cost:** technically near-zero initially; labour for cohort mapping, legal review, monitoring, and evidence storage is real. [I]
- **Key drawback:** Vietnam coverage is incomplete and biased toward companies using these ATS platforms. [I]

### 2. Board data licence / explicit partnership (parallel commercial track)

**Why it is second [I]:** A written licence from a Vietnam-first board can supply the strongest local coverage, structured refresh, and stable operating relationship. This is the desirable route to meaningful scale—not a confirmed free route.

- **Evidence:** VietnamWorks, ITviec, CareerViet, and TopCV evidence only establishes employer/partner integration contexts. [PV]
- **Access condition:** contract must expressly cover job inventory, descriptions, refresh/rate limit, historical retention, internal analytics, attribution, and any display/redistribution. [I]
- **Cost:** unknown / likely commercial. [PV]
- **Gate:** no board automation before written confirmation. [I]

### 3. SERP discovery with original-page verification (DataForSEO preferred; SerpApi comparable)

**Why it is third [I]:** Useful low-cost discovery for new employer pages and sparse ATS coverage; DataForSEO has documented pay-per-task pricing while SerpApi has a documented limited free tier. Neither should be the canonical description source.

- **Evidence:** provider docs above. [V]
- **Access condition:** an original page must independently pass source policy review before field extraction. [I]
- **Cost:** free credit/trial is limited; DataForSEO is inexpensive pay-as-you-go, not free. [V/PV]
- **Key drawback:** ranking, index lag, duplicates, and country/language query bias can mislead trend analyses. [I]

---

## 7. Recommended strategy, fallback, and decision boundary

### Recommended primary approach — approval requested

**A governed, source-controlled hybrid:**

1. Create a small, transparent employer cohort selected for Vietnam AI relevance; seek direct written permission where feasible. [I]
2. For an employer, use a source-specific adapter only when one of these access bases is recorded: **written permission**, **contracted licence**, or **documented public employer feed after terms/robots review**. [I]
3. Prefer the employer’s original career URL and a documented ATS/feed (Greenhouse/Lever/Ashby/Workable/SmartRecruiters/JobPosting JSON-LD) over an aggregator. [V/I]
4. Publish/source results as “observed in the approved source cohort during [window]”; display a link to the original posting and avoid republishing a full description unless the agreed access basis permits it. [I]
5. In parallel, contact local boards for an explicit analytical data licence. A signed licence—not a hidden/public endpoint—is the scale-up prerequisite. [I]

**Why this is the recommended primary:** It turns reliability, lawful access, traceability, and non-misleading analytical claims into system gates rather than afterthoughts. It starts technically low-cost and permits a credible long-term move to licences. It sacrifices claims of broad coverage, which the product must not make anyway. [I]

### Recommended fallback

Use **DataForSEO or SerpApi only to discover candidate original pages**, with a strict per-source review and a small fixed spend cap. If an original page fails permission/access review, retain at most a compliance log that it was excluded—do not ingest the description. [I]

### Conditional later fallback

Run a **small paid Bright Data pilot only after approval** if board licensing has not materialized and counsel/contract review confirms that the intended internal analysis, raw retention, and output display are permitted. Bright Data is not preselected and should not become the sole vendor. [I]

---

## 8. Proposed resilient architecture (proposal, not implementation)

### Source strategy

- **Tier A — authoritative:** written employer permission and board licences. [I]
- **Tier B — documented public employer feeds:** source-specific ATS API/feed adapters, only after policy review. [I]
- **Tier C — discovery only:** structured-data/sitemap discovery and a capped SERP provider. Never treat results as canonical truth. [I]
- **Tier D — analyst fallback:** manual evidence capture with reviewer and citation. [I]
- Maintain two independent active source families (for example, direct ATS cohort + licensed board) before claiming the system is operationally resilient. [I]

### Metadata/evidence retention

For each observation retain: raw permitted response/evidence reference, SHA-256 hash, content type, response status, retrieval time, source URL, final redirect URL, access basis/policy version, parser/adaptor version, original field values, normalized field values, and confidence flags. [I]

If retaining raw full text is contractually restricted, store a hash plus permitted minimal excerpt/field derivation and the original link; do not silently retain prohibited content. [I]

### Deduplication boundary

- Preserve **source records** separately; do not overwrite them with a cross-source “job.” [I]
- Create a derived **canonical vacancy hypothesis** only from normalized company identity/domain, employer requisition where available, title/language-normalized text, location, employment type, date window, and description fingerprint. [I]
- Keep confidence, match features, and a human-review queue for uncertain matches. A board repost and the employer’s original listing may be one vacancy but must remain two citations. [I]
- Version the deduplication model. Never recompute historical trend totals without recording which version produced them. [I]

### Freshness and lifecycle

- Record source `published_at`, `updated_at`, `observed_at`, and `last_successful_fetch_at` independently. [I]
- Begin with a conservative 24-hour cadence for known feeds; shorten only when rate/access policy permits and business value proves it necessary. [I]
- On disappearance, mark `not_observed`/`possibly_closed`, do not assert “filled.” [I]
- Use conditional requests when offered, source-specific rate limits, `Retry-After`, exponential backoff, and a circuit breaker after repeated 429/5xx or policy changes. [I]

### Failure handling

| Failure | Safe response |
|---|---|
| Robots/terms prohibit automation or are ambiguous | Stop that source, record the decision, request written permission/legal review. |
| Login/CAPTCHA/anti-bot | Do not bypass. Route to partnership or manual review. |
| Field/schema drift | Quarantine adapter output, retain sample evidence, alert, and suspend publishing for that source. |
| Source outage/rate limit | Back off; use another approved source family; state coverage gap. |
| Duplicate surge/repost storm | Do not merge blindly; flag and disclose source/repost effect in analysis. |
| Missing/relative date | Keep source text, mark precision/confidence low; exclude from date-sensitive trend metrics by default. |

### Trend-analysis protections

Every trend output should include source mix by period, employer/ATS cohort change, retrieval cadence, date completeness, duplicate rate, closure detection method, and a warning that platform/adaptor changes can create apparent demand changes. [I]

---

## 9. Cost assumptions: free versus credit

| Route | What is actually free [V/PV] | What is only a credit/trial / paid [V/PV] | Decision implication |
|---|---|---|---|
| Direct documented ATS feeds / JSON-LD | Read access is generally unauthenticated for the documented public endpoints. [V/PV] | Employer discovery, policy review, monitoring, evidence storage, and any written permission process have labour cost. [I] | Best technical zero-spend start, not zero-cost. |
| Greenhouse/Lever/Ashby | Documented public read endpoints. [V] | No rate/permission guarantee for InternHunterAgent’s intended use was established. [PV] | Use only in a reviewed employer cohort. |
| Bright Data Web Scraper | Provider advertises a limited free-record allowance. [V] | Ongoing volume is paid; Jobs Data API is paid; account/payment onboarding is required. [PV] | Credit is a pilot, not a free production plan. |
| Apify | $5 monthly platform credit is advertised. [V] | Actors have usage/platform charges and target-site permission remains separate. [PV] | Not a permission substitute. |
| SerpApi | 250 searches/month free tier is advertised. [V] | Higher volume/legal features are paid and source descriptions remain non-canonical. [PV] | Discovery-only and small-scale. |
| DataForSEO | Registration credit reported as small; pricing is pay-per-task. [PV] | A minimum deposit is reported; no continuing free tier. [PV] | Low variable-cost discovery; validate current checkout terms. |
| Jooble | API is advertised as free with a limited key. [V] | 500 requests is a lifetime cap, not a renewable production quota. [V] | Feasibility-only. |
| Google Custom Search | 100 queries/day documented. [V] | Extra queries are paid. [V] | Link discovery only. |
| Common Crawl / Wayback | Access is free. [V] | Rights verification, storage, filtering, and labour are not free. [I] | Historical research only. |
| Board partnership | No free programme was evidenced. [PV] | Likely negotiated commercial cost. [I] | Obtain a written quote and data-use schedule. |

**Budget assumption for a safe MVP [I]:** $0–$50/month can cover a small direct employer cohort plus an optional capped discovery test; this excludes staff time, storage, legal review, and any board licence. Do not promise a national-scale, fresh corpus at that budget.

---

## 10. Risks and unknowns requiring validation

1. **Vietnam board permission:** VietnamWorks endpoint evidence is community-derived; verify current endpoint availability, rate limit, terms, and third-party analytics/retention rights directly with the board. [PV]
2. **Employer/ATS terms:** Public ATS docs demonstrate endpoints, not a universal licence to automate or redistribute every employer’s descriptions. Review platform terms and employer career-site terms before use. [I]
3. **Vietnam coverage:** No authoritative vendor-level Vietnam ATS-adoption statistic was found. All ATS Vietnam-coverage scores are estimates. [U]
4. **Copyright/contract/privacy:** Descriptions may be protected expression and can contain contact names/personal data. Terms, applicable Vietnam data-protection law, and cross-border handling need qualified legal review. [I]
5. **Provider licence fit:** Bright Data, SerpApi, JSearch, and board licences can restrict redistribution/competitive use. The user-visible product behaviour must be checked against the contract—not only internal storage. [PV]
6. **Published-date quality:** Some sources expose creation/update times, others relative strings, and boards can republish. Use date-confidence flags and prevent unknown dates from driving trends. [V/I]
7. **Sampling bias:** Employer cohort, language, platform adoption, indexing, and source outages bias requirement frequencies and career-level comparisons. [I]
8. **Anti-bot/login controls:** A challenge/CAPTCHA/auth wall is a stop signal, not a technical obstacle to circumvent. [I]
9. **Historical data rights:** Web archives and public datasets do not automatically give rights to retain/reuse original job descriptions. [V/I]
10. **Pricing changes:** Free credits, trial rules, and API limits change; re-check pricing pages at procurement time. [I]

---

## 11. Minimal, no-code / low-risk feasibility test plan

**Do not execute this plan without approval.** It is designed to validate access and evidence, not to build a scraper or collect a corpus.

1. **Create a source register (10–20 candidate employers, no automated retrieval).** For each, record career URL, declared ATS/feed, Vietnam relevance, current terms URL, robots URL, contact route, and candidate access basis. **Pass:** at least 5 employers have a written opt-in or a clearly documented public feed *and* no unresolved prohibition. [I]
2. **Request written clarification from 2–3 local boards.** Ask specifically about API/data-licence availability, Vietnam AI-job scope, description/date fields, rate limit, refresh, historical retention, internal analytics, public excerpts, price, SLA, and termination/deletion. **Pass:** one board provides terms compatible with intended use. [I]
3. **Inspect—not bulk retrieve—one documented example per ATS platform.** Use the official docs and an employer’s public page to compare title, original URL, description, location, and date. No pagination, no high-rate requests, no login. **Pass:** each candidate adapter yields all required fields and a stable original URL. [I]
4. **Policy review gate.** Read and preserve exact terms/robots clauses for every candidate source. **Pass:** written approval, explicit allowance, or qualified legal approval; otherwise mark `excluded`. [I]
5. **Discovery quality spot check.** With a fixed sample of 20 AI-related searches, compare a SERP provider’s candidate links to the original pages manually. **Pass:** original-page match rate, Vietnam relevance, duplicate rate, and date availability are measured and disclosed. [I]
6. **Evidence rehearsal with synthetic or manually permitted examples.** Validate that the proposed record can preserve source URL, raw hash, observed time, access basis, and publication-date confidence without storing disallowed material. **Pass:** an auditor can reconstruct every displayed claim. [I]
7. **Go/no-go review.** Proceed only if (a) every active source has a documented access basis, (b) at least two independent approved source families exist or a coverage-gap disclaimer is accepted, and (c) the reporting language is limited to the observed dataset. [I]

---

## 12. Community/blog/LinkedIn/Reddit/GitHub practice evidence — non-authoritative

This section answers the requested review of developer practice. It is **not permission evidence**. A GitHub repository proves that its author published code; a Reddit/LinkedIn post or blog expresses experience/opinion. None establishes a target site's current terms, an API licence, or lawfulness for InternHunterAgent.

### GitHub projects (real, inspectable implementation artefacts)

| Project | What it demonstrates | Evidence status | What InternHunterAgent should learn | Why it does **not** change the recommendation |
|---|---|---|---|---|
| [TrNguyenMQuan/vn-jobs-data-pipeline](https://github.com/TrNguyenMQuan/vn-jobs-data-pipeline) | README and source tree describe a VietnamWorks-based pipeline with raw/bronze, cleaned/silver, warehouse/marts, Airflow, dbt, retries, and trend analytics. | [V: project contents] | Preserve raw source responses before normalization; separate transformation from analytical marts; version data contracts. | It calls the route a public VietnamWorks API, but it does not prove VietnamWorks has licensed the project’s collection/reuse. Treat the endpoint claim as [PV]. |
| [tgkiet/jobs-pipeline-analysis](https://github.com/tgkiet/jobs-pipeline-analysis) | A TopCV list/detail crawler keeps a pending-detail status in PostgreSQL and explicitly notes detail-page anti-bot blocking. | [V: project contents] | List/detail work should be resumable and observable; a posting may be discovered before all required fields are available. | The repository directly demonstrates fragility/anti-bot risk, not authorization. It supports exclusion of broad TopCV automation without a licence. |
| [tunguyenn99/crawl-topcv-jobs](https://github.com/tunguyenn99/crawl-topcv-jobs) | A learning project extracts TopCV list, job, and company fields, uses randomized delays to respond to 429s, and schedules a pipeline with Airflow. | [V: project contents] | Rate limits and full-page detail enrichment are operational realities; manual/low-volume collection is simpler than a production crawler. | Its own README says it is for learning and asks users to respect terms. Delays do not make access permitted or stable. |
| [haucongle/itviec-scraper](https://github.com/haucongle/itviec-scraper) | A Playwright/Cheerio project uses resume checkpoints, URL deduplication, relative-date handling, cookies, and a Cloudflare-stealth plugin; it documents that salary can require login. | [V: project contents] | Checkpoints, raw-date confidence, source URL deduplication, and graceful resume are useful resilience patterns. | **Reject its access method:** Cloudflare evasion and reusing login cookies/session tokens conflict with the proposed policy. A technical workaround is a stop signal, not a pattern to adopt. |
| [kalil0321/ats-scrapers PR #82](https://github.com/kalil0321/ats-scrapers/pull/82) | A closed/superseded PR reports structured VietnamWorks fields, page-size clamping, pagination, retry on 429/5xx, deduplication, and timezone parsing defects flagged in review. | [V: PR contents] | If a source is later licensed, validate field mapping, date timezone, pagination, duplicate pages, error paths, and live counts before trusting trend data. | It is community evidence; the PR was closed/superseded and its author still listed a full live sweep as manual validation. It is not official API or permission evidence. |

**Practice pattern observed [I]:** projects converge on raw retention, staged normalization, detail enrichment, retries/checkpoints, deduplication, and date handling. They also repeatedly expose the exact risks this report gates: anti-bot blocks, authentication, relative dates, fragile selectors, and no evidence of source-data rights.

### Developer blogs

- [Cavuno’s developer-oriented job-scraping guide](https://cavuno.com/blog/job-scraping) **[PV: vendor blog]** says that extraction is only one pipeline step and calls out normalization, cross-source deduplication, freshness, career pages, public ATS feeds, anti-bot controls, and source attribution. Those are useful design prompts and agree with the proposed architecture.
- The same guide is **not** neutral evidence: it markets its own platform, makes pricing/legal/industry-scale assertions that were not independently verified here, and discusses anti-bot services. Its claims do not override a source’s terms or a board licence. [V/I]

### Reddit and LinkedIn

- Candidate Reddit discussions were found, including [r/webscraping: company careers pages](https://www.reddit.com/r/webscraping/comments/1siuxmq/webscraping_company_careers_pages/), [r/datascience: current job-opening APIs](https://www.reddit.com/r/datascience/comments/182viiv/current_job_opening_apis/), and [r/datascience: scraping job-site rules](https://www.reddit.com/r/datascience/comments/5psv7b/scraping_job_sites_rules_for_scraping_the_web/). **[U]** Their page contents could not be reliably extracted in this research pass, so no factual claim or recommendation in this report depends on them.
- LinkedIn developer-post search produced leads but no public post with sufficiently retrievable, primary, and source-specific evidence to rely on. **[U]** No LinkedIn post is used as proof of API availability, permission, scale, or cost.

**Takeaway from community practice [I]:** treat community material as a hazard catalogue and architecture inspiration—not as a green light. The recommended consent-first, source-specific hybrid remains unchanged; GitHub examples strengthen the need for provenance, adapter tests, date confidence, source-level deduplication, and an explicit no-login/no-evasion rule.

---

## 13. Approval required before implementation

**Decision requested:**

> Approve or reject the proposed primary strategy: a consent-first/direct-employer, source-specific ATS/feed cohort with strict provenance and policy gates; pursue a board data-licence in parallel; use capped SERP discovery only as a non-canonical fallback; do not begin broad scraping or commit to Bright Data until a separate pilot/licence decision is approved.

If approved, the next step is a separate change proposal/issue that states the approved source cohort, legal/access decisions, field contract, budget cap, and feasibility-test boundaries. No implementation should begin from this report alone.

**Not approved by this report:** scraping local job boards, calling undocumented VietnamWorks endpoints, purchasing Bright Data/Apify/SerP services, creating accounts, collecting a dataset, or changing product claims.
