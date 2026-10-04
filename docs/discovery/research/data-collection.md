# Data-collection research register

> **Last reviewed:** 2026-09-22
>
> **Boundary:** These findings do not authorize scraping, systematic collection, provider
> purchase, account creation, or production deployment.

## Source inventory

| ID | Durable record | Scope | Evidence status |
|---|---|---|---|
| R-001 | [Direct-employer source availability](direct-employer-source-availability.md) | Vietnam direct-employer/ATS technical availability, field visibility, and access posture. | Completed desk research and manual inspection; authority unresolved. |
| R-002 | [Option 1 and Option 3 research](option-1-option-3.md) | Direct cohorts, providers, APIs, source-specific paths, and Firecrawl. | One capped Bright Data technical test; no retained records or source selection. |
| R-003 | `TEMP_MVP_DISCOVERY_DECISIONS.md` | Original product discovery decisions. | Migrated into problem, decision, and solution records; temporary input retained. |
| R-004 | `TEMP_DATA_COLLECTION_RESEARCH.md` | Original source-strategy comparison and collection contract. | Migrated summary; temporary input retained. |

## Research findings

### R-001: Direct-employer source availability

| Field | Finding |
|---|---|
| Claim | A technically meaningful Vietnam-relevant direct-employer/ATS cohort exists. |
| Confidence | Partially verified |
| Supporting evidence | The study identified 33 deduplicated employers and manually reopened six original AI-related pages. Descriptions, original URLs, employer context, and often location were visible. |
| Material gap | Technical accessibility did not establish permission, licence, or operational approval for collection. |
| Date finding | Publication dates were inconsistent; some pages exposed closing dates instead. |
| Implication | Direct employers are a feasible candidate only with source-specific authority and truthful date handling. |

### R-002: Option 1 and Option 3 availability

| Field | Option 1 — direct employer/ATS cohort | Option 3 — provider/scraper supplement |
|---|---|---|
| Conclusion | Strongest technical/data-quality path if employers participate. | Discovery or controlled-pilot candidates only. |
| Confidence | Partially verified | Partially verified |
| Strength | Employer-origin provenance, stable IDs where supplied, and controlled refresh. | Some providers document country configuration, fields, pagination, or extraction. |
| Material gap | No signed Vietnamese employer cohort. | No measured Vietnam AI-job recall, authority, or production stability. |
| Research interpretation | Candidate primary-source model if authority is obtained; no selection is in force. | Bright Data is a temporary technical pilot option; no provider or source strategy is selected. |

### R-003: Original data-source research

The original research found no evidenced single, free, Vietnam-wide production-safe feed. It
proposed a consent-first employer cohort, a board-licence track for expansion, and
SERP/provider discovery only as non-canonical support. These are historical research inputs,
not current project decisions. It also documented that a free credit or accessible endpoint
is not permission.

## Source-authority boundary

- Public visibility, robots files, contact routes, and accessible APIs do not establish
  authority to collect or reuse a source.
- Some reviewed ATS/platform terms expressly restrict automation or data mining; those
  sources remain excluded unless a source-specific authorised arrangement changes that.
- Any active source must record its access basis, agreed use, retention, attribution, and
  deletion/withdrawal handling.

## Research-proposed field and provenance contract

The following controls are decision inputs, not selected project requirements.

| Field/control | Research proposal |
|---|---|
| Source identity | `source_name`, `source_type`, canonical `source_url`, and original `apply_url` where available |
| Authority | `access_basis`, relevant policy/permission version, and allowed use/retention scope |
| Retrieval | `retrieved_at`, `observed_at`, content type/status, adapter version, and raw response or permitted evidence/hash |
| Job content | Original title, description/evidence, company, location, employment type, skills/salary when exposed |
| Dates | Raw source date text plus type: `published`, `closing`, `collection`, `not_shown`, or `unknown`; normalize only deterministic source-originated dates |
| Identity/deduplication | Source/external ID first, canonical apply URL second, documented content fallback last; retain match confidence and deduplication version |
| Lifecycle | First/last observed, source updated, active/changed/removed/unknown state, and source evidence for state transitions |
| Analysis guardrail | Output declares source cohort, collection window, filters, missingness, and deduplication version |

## Unresolved gate: initial-cohort threshold

The research inputs contain different candidate thresholds. One proposes at least three
participating employers with distinct feeds/adapters; another no-code plan proposes at
least five approved employers and two independent source families. No final threshold is
selected. See [D-010](../decisions.md#d-010--select-the-data-collection-strategy).

## Potential validation inputs for a future production decision

The following checks are research-proposed inputs, not approved project gates:

1. Confirm the selected source’s authority basis and permitted use.
2. Select and test a cohort diversity/volume threshold with required fields and lifecycle evidence.
3. Measure removal/closure behavior before treating postings as active.
4. If a provider pilot is selected, measure fixed Vietnam AI/data query coverage,
   original-source URL rate, description rate, source-originated date rate, duplicate rate,
   and thirty-day stability.
5. Validate retention, citation display, and deletion/withdrawal behavior against the selected source terms.
