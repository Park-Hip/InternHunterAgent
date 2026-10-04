# Option 1 and Option 3 research notes

**Status:** Research only.

**Scope:** Vietnam AI-job data availability through a direct employer/ATS cohort, scraping providers, Google Jobs APIs, source-specific approaches, and Firecrawl.

**Method:** Reviewed existing project evidence and public provider documentation only.

**Excluded activities:** No accounts were created.

No credits, trials, scraper executions, purchases, or new job-data collection were used.

**Important:** At the user's direction, the current recommendation is based on technical and data-quality availability only.

It is not a permission, target-board terms, or production-launch assessment.

## Scoring rubric

Technical availability evaluates source targeting, field extraction, refresh, pagination, and source metadata.

Data quality evaluates actual Vietnam evidence, original URLs, duplicate support, published-date quality, and citation lineage.

A country parameter, a product claim, or free credits do not by themselves establish viable Vietnam AI-job coverage.

## Option 1 - Direct employer/ATS cohort

### Conclusion

Option 1 is a technically strong candidate if an initial group of Vietnamese employers participates.

It begins with limited coverage, but each participating employer could supply high-quality,
employer-origin data that can be measured and refreshed. This comparison does not select
Option 1 as the project strategy.

### Candidate integration paths

| Path | Technical availability | Data-quality properties | Notes |
|---|---|---|---|
| Greenhouse Job Board API | Strong for participating employers. | The documented public job-board API can return descriptions, locations, departments, offices, URLs, and update information. | Best generic ATS candidate where a Vietnamese employer uses Greenhouse. |
| Lever employer feed or integration | Potentially strong, but employer configuration determines availability. | Job, apply, and organization data can be stable when supplied by the employer. | Treat as a separate adapter, not a universal public endpoint. |
| Workday employer career site or integration | Variable by tenant and employer configuration. | Can provide authoritative requisition, description, location, dates, and apply URL where supplied. | Requires per-employer discovery and validation. |
| Direct employer export, feed, or webhook | Strong when supplied by the employer. | Offers the clearest full descriptions, lifecycle signals, and deletion handling. | Preferred path for an initial signed cohort. |
| Employer career pages | Useful when no structured feed exists. | Quality is good only if a stable job detail URL and source fields are retained. | Firecrawl is a candidate implementation tool here. |

### Technical availability

A direct ATS cohort can provide title, company, location, full description, skills, compensation where disclosed, requisition ID, original URL, apply URL, created or updated timestamps, and removal signals.

Greenhouse documents a Job Board API with job data including descriptions, locations, departments, offices, URLs, and update information.

Employer-specific feeds can support scheduled refresh, source-specific pagination, and a stable identity key such as an ATS requisition ID.

### Data-quality availability

The employer is the primary source, so a cohort has the best traceability available in this study.

Use the employer ATS requisition ID as the first duplicate key.

Use a canonical apply URL as the next duplicate key.

Use a title, company, location, and description-hash fallback only when no stable source ID exists.

Store raw date text and a normalized ISO date separately.

Populate a normalized published date only if it is source-originated and deterministic to parse.

### Vietnam coverage

No signed Vietnamese employer cohort was identified in this study.

Therefore, Option 1 has low initial coverage but high expected precision within a participating cohort.

Example Vietnamese AI-employer career pages found during discovery included Base and KiotViet, but this study did not collect their vacancy data.

### Scores

| Criterion | Score | Rationale |
|---|---:|---|
| Technical availability | 8/10 | Standard ATSs and direct employer feeds have strong field and lifecycle support once an employer participates. |
| Data quality | 9/10 | Employer-origin data, stable requisition identifiers, and controlled refresh make source-level citation practical. |
| Research signal | Candidate primary-source model | A small employer cohort is a possible way to avoid unsupported broad-market claims. |

### Potential Option 1 evaluation criteria

If Option 1 is selected, an initial cohort could require at least three employers with distinct ATS implementations or feeds.

Each adapter should return a stable source ID, original apply URL, title, employer name, location, full description, and at least one truthful lifecycle field.

Each run should record source retrieval time, raw payload or page hash, adapter version, and a content hash.

A removal or closure signal should be measured before treating a role as active.

## Option 3 - Provider and scraper supplement

### Summary

No provider in this study demonstrated measured live Vietnamese AI-job recall without using an account or running a query.

Generic Google Jobs providers can establish Vietnam query configuration but cannot establish the coverage or quality of the resulting Vietnamese corpus from documentation alone.

JSearch is the strongest generic controlled-pilot candidate because it documents `country=vn`, full descriptions when available, apply links, and cursor pagination.

Apify has the richest documented Vietnam-board schema, but the actor reviewed is marked deprecated.

Bright Data has strong generic extraction capabilities but no verified Vietnam-local-board coverage.

### Comparison

| Provider or approach | Vietnam evidence | Fields and operations | Cost | Technical score | Data-quality score | Recommendation |
|---|---|---|---|---:|---:|---|
| Bright Data Jobs Data API and Web Scraper | No verified Vietnam AI-job or local-board coverage. | Jobs API documents title, company, description, skills, location, posted date, application URL, last-updated timestamp, daily updates, and snapshots. Web Scraper can be configured for target URLs. | Web Scraper lists 5,000 free records per month and $1.50 per 1,000 PAYG records. Jobs Data API pricing is sales-led. | 5/10 | 4/10 | Discovery-only. |
| Apify Vietnam Jobs Scraper | Targets VietnamWorks, TopCV, and ITviec, with documented Vietnamese sample output. The reviewed actor is deprecated. | Documents title, company, company URL, board URL, salary, location, skills, posted and expiry dates, descriptions, benefits, pagination controls, detail fetches, and cross-page deduplication. | Per-job usage. The actor documentation says a 200-job run costs well under one dollar. | 7/10 | 5/10 | Discovery-only until a maintained actor is identified and measured. |
| SerpApi Google Jobs | Official country table lists `gl=vn`. No Vietnamese AI-job result set was measured. | Documents title, company, location, source label, description, relative-date extensions, Google job card link, and application options. Fresh fetch can bypass cache. Job pagination is not clearly documented. | Published free and paid search plans. Confirm current plan details before purchase. | 6/10 | 3/10 | Discovery-only. |
| DataForSEO Google Jobs SERP API | Location-based targeting is supported. No Vietnam result set was measured. | Documents task-based async retrieval, webhooks, depth up to 200, job ID, title, employer URL, source URL, location, salary, contract type, timestamp, and relative time. It does not document full descriptions. | Documentation examples list standard queue pricing from roughly $0.0006 per task, with higher live and priority prices. | 7/10 | 4/10 | Discovery-only. |
| JSearch / OpenWeb Ninja | Official documentation lists `vn` as a supported country code. No Vietnamese AI-job result set was measured. | Documents real-time Google-for-Jobs and web data, detailed descriptions when available, employer data, apply links, posting expiration, and cursor pagination through `/search-v2`. | Free tier lists 200 requests per month. Paid plans start at $25 per month. | 8/10 | 5/10 | Controlled pilot candidate. |
| Source-specific VietnamWorks JSON search | Existing project spikes and frozen corpus provide historical Vietnam AI/Data evidence. | Existing project spike code shows structured search, stable IDs, full descriptions, title, company, location, salary, source URLs, dates, pagination, and refresh. | No provider cost. | 9/10 | 8/10 | Strongest direct source-specific path. |

## Bright Data Jobs Data API and Web Scraper

### Technical availability

Bright Data's Jobs Data API documents job title, company name, job description, required skills, location, employment type, salary range, seniority, posted date, application URL, and company attributes.

The provider documents daily updates, a posted-date filter, a last-updated timestamp, API delivery, webhooks, and snapshot-based retrieval.

Its Web Scraper can target arbitrary URLs, but it is a generic extraction platform rather than Vietnam-local jobs coverage.

### Data-quality availability

Bright Data documentation identifies LinkedIn, Indeed, Glassdoor, and other broad sources.

It does not evidence VietnamWorks, TopCV, ITviec, or a measured Vietnamese AI-job corpus.

The product documents deduplicated multi-source data, but no Vietnam-specific duplicate measurement was found.

The product documents application URLs, but the original employer URL rate for Vietnamese results was not established.

A later capped technical test returned HTTP 200 and ten records for one non-paginated
`AI Engineer` query in Hanoi. It returned core fields including a source URL and stable job
ID, but the sampled record had a null `country_code` and no application link. The response
was inspected in memory only; no records were retained. This verifies basic technical
viability, not Vietnam normalization, completeness, reliability, or permitted use. See
[Issue #423](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797431647).

### Cost

The Web Scraper pricing page lists a 5,000-record free tier and $1.50 per 1,000 records PAYG pricing.

The Jobs Data API is sales-led.

### Assessment

Bright Data is a temporary, technically verified pilot option. It is not a selected
Vietnam-market source until it passes the permitted-use gate and demonstrates coverage,
field quality, and reliability through the approved scorecard.

## Apify board-specific actors

### Vietnam Jobs Scraper

The actor `anxuanng/vietnam-jobs-scraper` explicitly documents support for VietnamWorks, TopCV, and ITviec.

It documents a unified record model with an ID, source, original URL, title, company, company URL, salary fields, locations, city names, addresses, work mode, level, experience, skills, posted date, expiry date, description, and benefits.

It documents pagination controls using `maxItems` and `maxPages`.

It documents optional detail-page fetches for TopCV and ITviec descriptions.

It documents cross-page deduplication and an even mix across sources.

The actor page currently labels the actor deprecated.

Therefore, its documentation supports a useful schema benchmark, but not a production recommendation.

### Data-quality observation

The documented sample output is strong evidence of field shape, not independent evidence of current AI-job coverage, uptime, completeness, or source-date accuracy.

A maintained actor would need a measured pilot before promotion.

## SerpApi Google Jobs

### Technical availability

SerpApi officially lists Vietnam as `gl=vn` in its Google Jobs country table.

The Google Jobs API example includes `title`, `company_name`, `location`, `via`, `share_link`, `description`, relative date extensions, structured extensions, `apply_options`, and `job_id`.

`apply_options` can contain direct job-board or employer ATS links.

The documentation does not clearly establish an exhaustive pagination contract for the Google Jobs engine.

### Data-quality availability

`via` identifies the indexed source and `apply_options` can preserve source links.

The example exposes relative dates such as `23 days ago`, not a source-authoritative ISO published date.

No duplicate policy or Vietnamese AI-job coverage measurement was found.

### Assessment

SerpApi is useful for discovery and market-signal experiments.

It should not be treated as an authoritative Vietnam jobs corpus.

## DataForSEO Google Jobs SERP API

### Technical availability

DataForSEO accepts keyword, location, language, depth, task tag, and callback parameters.

It exposes task IDs, polling, `postback_url`, `pingback_url`, and documented depth up to 200 results.

Its advanced response schema includes `job_id`, title, employer name, employer URL, location, source name, source URL, salary, contract type, timestamp, and relative time.

### Data-quality availability

The response has a useful source URL and source label for traceability.

The endpoint is Google Jobs SERP data rather than an employer page extractor.

It does not document full descriptions as a returned field.

No duplicate policy, Vietnam AI-job sample, or Vietnam published-date-quality measurement was found.

### Assessment

DataForSEO is a viable source-discovery tool and an API-shape fallback.

It is weaker than JSearch for full-description use cases.

## JSearch / OpenWeb Ninja

### Technical availability

JSearch officially lists `vn` among supported country codes.

It documents real-time job data from Google for Jobs and public web sources.

It documents title, descriptions, location, salary estimates, employer information, apply links, job posting expirations, and filtering.

It documents cursor pagination through `/search-v2`.

### Data-quality availability

Country configuration does not prove the number, quality, or freshness of Vietnam AI jobs.

Apply links and employer data can support citations when paired with a stored raw provider response and retrieval timestamp.

The documentation does not state a duplicate policy.

It documents expiry information, but the original published-date quality should be measured.

### Assessment

JSearch is the best generic controlled-pilot candidate.

Use it only with explicit validation targets for Vietnam coverage, source attribution, date quality, duplicates, and 30-day stability.

## Source-specific approach - VietnamWorks JSON search

### Technical availability

The project contains `scripts/scrape_spike.py`, which documents a JSON search endpoint at `https://ms.vietnamworks.com/job-search/v1.0/search`.

The spike uses a structured IT and Telecom job-function taxonomy, including a Data Engineer, Data Analyst, and AI child category.

It documents pagination and total-hit metadata.

The spike shows that titles, companies, locations, salaries, descriptions, URLs, and source lifecycle fields can be normalized from source data.

### Data-quality availability

VietnamWorks source IDs can be used for stable source identity and deduplication.

A structured job-function taxonomy is stronger for AI/Data relevance than keyword-only discovery.

The existing frozen corpus is historical evidence of Vietnam source data, not a claim that vacancies are currently open.

### Assessment

This remains the highest technical and data-quality source-specific route in the existing project.

## Firecrawl

### What Firecrawl is

Firecrawl is a crawling and extraction platform, not a jobs-data provider.

It is most useful as a direct employer-career-page and uncommon-ATS implementation tool for Option 1.

### Technical availability

The Scrape endpoint supports Markdown, cleaned HTML, raw HTML, links, screenshots, images, and schema-guided JSON extraction.

JSON extraction can use a JSON Schema and an optional extraction prompt.

The platform supports page actions for dynamic navigation.

It supports location and language settings, with country codes and corresponding proxy behavior where available.

The Crawl endpoint discovers pages through sitemaps and recursive link traversal, handles JavaScript rendering, supports path and depth filters, and reports crawl status through polling, WebSockets, or webhooks.

Crawl result payloads larger than 10 MB provide a `next` URL for result pagination.

Firecrawl exposes crawl errors and robots-blocked URLs, which must be treated as explicit evidence of incomplete coverage rather than ignored failures.

### Field extraction

For a direct employer/ATS cohort, use one extraction schema for listing pages and one for detail pages.

Suggested job record fields are `source_url`, `apply_url`, `external_id`, `title`, `company`, `location`, `employment_type`, `description`, `skills`, `salary_text`, `posted_date_raw`, `posted_date`, `expires_at_raw`, `expires_at`, `retrieved_at`, and `content_hash`.

The job-board extraction guide demonstrates schema-based extraction of titles, locations, detail URLs, full descriptions, compensation, responsibilities, skills, and application URLs from ATS pages.

### Refresh and change tracking

`maxAge: 0` forces a fresh scrape rather than a cached response.

Change tracking stores a persistent snapshot for the team and returns statuses including `new`, `same`, `changed`, and `removed`.

It can return a line-level diff or a schema-level field comparison.

Monitoring can schedule checks as frequently as every five minutes and send notifications.

### Data-quality limits

Firecrawl can extract a displayed date but cannot establish that the date is the source-authoritative publication date.

Schema-guided JSON is helpful but must be validated against captured raw content before a normalized record is accepted.

Firecrawl does not supply job-level duplicate handling.

Use ATS requisition ID first, canonical apply URL second, and content identity as a fallback.

A completed crawl is not proof that every reachable job was collected.

The Crawl API explicitly records failed and robots-blocked pages and warns that crawl results can vary across runs.

### Cost

The pricing page lists 1,000 free credits per month.

A basic scrape, crawl, or map costs one credit per page.

JSON, Question, and Highlight formats add four credits per page.

The Hobby plan lists $19 per month for 5,000 credits.

### Firecrawl assessment

| Criterion | Score | Rationale |
|---|---:|---|
| Technical availability | 8/10 | Strong browser rendering, crawling, structured extraction, refresh, change tracking, and webhooks. |
| Data quality | 7/10 | Strong only when raw evidence, schema validation, source IDs, and date rules are retained. |
| Best use | Option 1 supplement | Use for direct employer career pages and ATS implementations without a cleaner structured feed. |
| Avoid as primary use | Generic job-board crawler | VietnamWorks already has a technically cleaner structured path, while TopCV and ITviec are likely more site-specific and brittle. |

## Research comparison summary

No technical direction is selected by this research. The evidence suggests that Option 1 may
offer stronger provenance and data quality if employers participate; VietnamWorks appears to
be a strong source-specific technical lead; Firecrawl is a possible implementation tool for
employer pages; and JSearch is a possible provider-evaluation candidate.

Google Jobs providers have no measured Vietnam AI-job validation in this study, and the
reviewed Apify actor is deprecated. These observations are decision inputs, not approval to
use any source, provider, or tool.

## Potential controlled-pilot measurements

If a future decision selects a provider pilot, collect and review measurements for at least
30 days.

Measure the number of results for a fixed Vietnamese AI/Data query set across Hanoi, Ho Chi Minh City, Da Nang, remote, and nationwide queries.

Measure the percentage with original employer apply URLs.

Measure the percentage with a full description.

Measure the percentage with a source-originated ISO published date.

Measure duplicate rate within a query, between queries, and between refreshes.

Measure changed, removed, blocked, failed, and stale-record rates.

Store retrieval timestamp, query, source metadata, raw response hash, normalized record hash, and field-level provenance for every accepted record.

## Sources

- [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html)
- [Bright Data Jobs Data API](https://brightdata.com/products/data-feeds/jobs-data-api)
- [Bright Data Web Scraper pricing](https://brightdata.com/pricing/web-scraper)
- [Apify Vietnam Jobs Scraper](https://apify.com/anxuanng/vietnam-jobs-scraper)
- [SerpApi Google Jobs API](https://serpapi.com/google-jobs-api)
- [SerpApi supported Google Jobs countries](https://serpapi.com/google-jobs-countries)
- [DataForSEO Google Jobs task creation](https://docs.dataforseo.com/v3/serp/google/jobs/task_post/)
- [DataForSEO Google Jobs advanced results](https://docs.dataforseo.com/v3/serp-google-jobs-task_get-advanced/)
- [JSearch documentation](https://www.openwebninja.com/api/jsearch)
- [Firecrawl Scrape](https://docs.firecrawl.dev/features/scrape)
- [Firecrawl Crawl](https://docs.firecrawl.dev/features/crawl)
- [Firecrawl Change Tracking](https://docs.firecrawl.dev/features/change-tracking)
- [Firecrawl job-board extraction guide](https://www.firecrawl.dev/blog/scrape-job-boards-firecrawl-openai)
- [Firecrawl pricing](https://www.firecrawl.dev/pricing)
- Historical external source: `Research-Scraper/scripts/scrape_spike.py` (not present in this repository). <!-- lint-allow-link-path -->
- Historical external source: `Research-Scraper/docs/decisions/adr-0034-vietnamworks-robots-and-terms-gate.md` (not present in this repository). <!-- lint-allow-link-path -->
