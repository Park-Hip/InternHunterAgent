# Source-level semantics evidence

> **Last verified:** 2026-09-27
>
> **Eviction:** This evidence record leaves when an approved, authorized multi-source corpus with
> retained raw evidence supersedes the historical VietnamWorks audit and the provider field-export
> observation.

## Finding

The available evidence supports preserving a platform's level label as a source fact.
It does not support treating that label as technical seniority or leadership scope.
The evidence also does not support a cross-source mapping, because the only future-provider result
is a ten-record in-memory technical test with a restricted field selection.

This is a research record for [issue #461](https://github.com/Park-Hip/InternHunterAgent/issues/461).
It makes no runtime, API, schema, source-selection, collection, retention, or deduplication change.

## Evidence classes and corpus limits

| Evidence class | Artifact or authority | What it supports | What it cannot support |
| --- | --- | --- | --- |
| Historical processed record export | `research/experiments/vietnamworks_ai_data_sample.json` on `docs-history-pre-redesign` <!-- archived-on-tag --> | One 112-record VietnamWorks AI/Data sample, field availability, source-label distribution, and title-label comparison. | Current market coverage, a current source contract, untouched raw-field behavior, or another provider's semantics. |
| Historical acquisition method | `scripts/scrape_spike.py` on `docs-history-pre-redesign` <!-- archived-on-tag --> | The original keyword, page, and structured-function selection rules. | Permission to repeat collection or a production adapter. |
| Provider technical test | [Bright Data capped-test result](https://github.com/Park-Hip/InternHunterAgent/issues/423#issuecomment-5797556656) | Ten returned records had the stated core output fields in a capped, non-paginated call. | Any retained row-level measurement, Vietnam coverage, field completeness, or semantic mapping rate. |
| Provider documentation | [Bright Data LinkedIn Jobs API reference](https://docs.brightdata.com/api-reference/scrapers/social-media-apis/linkedin-jobs-collect-by-url) | The documented example includes a listing ID, title, company, location, source seniority, function, employment type, posted date, application availability, description, and compensation fields. | That an authorized Vietnam sample will contain those fields or that their values are accurate. |

The historical export is retained through the repository's `docs-history-pre-redesign` tag rather
than in the active checkout.
Its Git blob is `f54d24f1291546ab5245bcc0371dba65b7b4b679` and its SHA-256 is
`c55b7674d7d0534b20251123bc3144e0e8f97d2c33aa070c9d948dc0c4c1d103`.
The active repository deliberately does not re-publish its individual job records.

The spike selected eight English AI/Data keyword queries, two pages per query, then deduplicated
by source ID and retained only IT/Telecommunications records with the structured
`Data Engineer/Data Analyst/AI` function child.
It was therefore a focused historical convenience sample, not a probability sample of Vietnamese
jobs or a representation of all job functions, employers, locations, or languages.

## Reproducible historical audit

The following shell and Python procedure reproduces every VietnamWorks aggregate in this document
from the tagged artifact without changing it.
Run it from a Bash-compatible shell at a checkout that retains `docs-history-pre-redesign`.

```bash
artifact="$(mktemp)"
git show docs-history-pre-redesign:research/experiments/vietnamworks_ai_data_sample.json \
  > "$artifact"
ARTIFACT="$artifact" PYTHONUTF8=1 uv run python - <<'PY'
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

path = Path(os.environ["ARTIFACT"])
raw = path.read_bytes()
rows = json.loads(raw)
assert len(rows) == 112
assert hashlib.sha256(raw).hexdigest() == (
    "c55b7674d7d0534b20251123bc3144e0e8f97d2c33aa070c9d948dc0c4c1d103"
)

nonempty = lambda value: value not in (None, "", [], {})
fields = (
    "external_id", "source", "title", "company", "description", "requirement",
    "job_function", "job_level", "is_internship", "location", "salary",
    "tech_stack_candidate", "url",
)
print({field: sum(nonempty(row.get(field)) for row in rows) for field in fields})
print(Counter(row["job_level"] for row in rows))

technical = re.compile(r"\b(?:intern(?:ship)?|entry|fresher|junior|mid(?:dle)?|senior)\b", re.I)
leadership = re.compile(r"\b(?:lead|manager|director)\b", re.I)
for label in sorted({row["job_level"] for row in rows}):
    group = [row for row in rows if row["job_level"] == label]
    print(
        label,
        len(group),
        sum(bool(technical.search(row["title"])) for row in group),
        sum(bool(leadership.search(row["title"])) for row in group),
        sum(bool(technical.search(row["title"]) or leadership.search(row["title"])) for row in group),
    )
PY
rm -f "$artifact"
```

The English word-boundary rules in that procedure are deliberately a diagnostic, not a production
classifier.
They do not interpret Vietnamese title wording, infer a person's responsibility, or prove that a
matched word has the same meaning on every platform.

## VietnamWorks field audit

| Concept | Historical representation | Available | Missing or ambiguous | Evidence interpretation |
| --- | --- | ---: | --- | --- |
| Source listing identity | `source` plus `external_id` | 112/112 | No provider-neutral identifier test. | Source-specific identity is available in this sample. |
| Acquisition provenance | `source` only | 112/112 source values | No per-row query, retrieval timestamp, response hash, or raw-payload reference in the processed export. | The export cannot independently reproduce acquisition context for an individual row. |
| Title and company | `title`, `company` | 112/112 each | No source-language or original-field fidelity audit. | Core display facts are present in the processed export. |
| Description and requirement | Sanitized `description`, `requirement` | 112/112 each | No untouched HTML, raw payload, or field-level source-null distinction. | Text exists, but raw-text preservation cannot be assessed. |
| Platform level | `job_level` | 112/112 | The field's source definition is not retained. | It is a complete platform-label observation, not a technical-seniority fact. |
| Job function | `job_function` list | 112/112 | The controlled selection already required one function child. | Presence is partly a selection artifact, not general field completeness. |
| Employment type | No field | 0/112 | No explicit employment-type semantics. | Unknown. |
| Location | `location` | 110/112 | Structured city components and geography accuracy are unavailable. | 98.2% present in this focused sample. |
| Compensation | Display `salary` string | 112/112 | No structured amount, currency, period, or disclosure-state audit. | Presence of display text is not structured-compensation coverage. |
| Skills | `tech_stack_candidate` list | 110/112 | The list was a spike candidate, not a reviewed skill taxonomy. | 98.2% have one or more candidate skill strings. |
| Publication and observation dates | No retained date fields | 0/112 | The current historical spike source shows that it considered `onlineOn`, `approvedOn`, and `expiredOn`, but those values are not in this tagged export. | No date semantic or missingness conclusion is possible. |
| Source or application URL | `url` | 112/112 | Application availability and final employer destination were not retained. | A source URL is complete in this sample. |
| Lifecycle signal | No retained field | 0/112 | No open, closed, expiry, observation sequence, or disappearance evidence. | Unknown. |

## VietnamWorks source-level audit

The five observed platform labels and their exact counts are below.
Percentages use the 112-record historical sample as the denominator.

| Source `job_level` | Records | Share |
| --- | ---: | ---: |
| `Experienced (non-manager)` | 89 | 79.5% |
| `Manager` | 11 | 9.8% |
| `Fresher/Entry level` | 8 | 7.1% |
| `Intern/Student` | 2 | 1.8% |
| `Director and above` | 2 | 1.8% |

The diagnostic title rules found an explicit English technical-level word in 26/112 titles
(23.2%), an explicit English leadership word in 12/112 titles (10.7%), and either kind in 35/112
titles (31.2%).
The remaining 77/112 titles (68.8%) have no such English marker under this deliberately narrow
rule and must remain unknown rather than be inferred.

| Source `job_level` | Records | Technical-title marker | Leadership-title marker | Any diagnostic marker |
| --- | ---: | ---: | ---: | ---: |
| `Experienced (non-manager)` | 89 | 20 | 4 | 22 |
| `Manager` | 11 | 1 | 8 | 8 |
| `Fresher/Entry level` | 8 | 3 | 0 | 3 |
| `Intern/Student` | 2 | 2 | 0 | 2 |
| `Director and above` | 2 | 0 | 0 | 0 |

In particular, 22/89 `Experienced (non-manager)` titles carry one of the diagnostic words.
Those include junior, middle, senior, lead, or manager wording despite the platform's broad
non-manager label.
Eight of eleven `Manager` titles carry a diagnostic word, including senior, lead, manager, or
director wording.
Neither result establishes a title-derived mapping.
Together, they falsify the simpler claim that one source label fully determines technical seniority
or leadership scope.

## Provider field-export observation

The authorized capped Bright Data test reported HTTP 200 and ten returned records after a single
non-paginated LinkedIn job-scraper query for `AI Engineer` in Hanoi.
The reported output selection was `url`, `job_posting_id`, `job_title`, `company_name`,
`job_location`, `job_posted_date`, `apply_link`, `country_code`, and `discovery_input`.
The first sampled record had a source URL, no application link, and a null `country_code` despite
the Vietnam query context.

The response was inspected in memory only.
No raw payload or job record was retained, so no aggregate missingness, seniority-label
frequency, title conflict rate, or Vietnamese coverage rate can be measured from it.
A field omitted from this restricted output selection is unknown, not evidence that the provider
cannot supply it.
The provider documentation is consequently recorded only as a schema claim until an authorized
retained export can test it.

## Cross-source evidence matrix

| Concept | VietnamWorks processed export | Bright Data capped test | Bright Data documentation | Current conclusion |
| --- | --- | --- | --- | --- |
| Identity | Source and external ID complete. | `job_posting_id` reported for the output selection. | Listing ID documented. | Preserve provider and source-specific identifiers separately. |
| Origin and acquisition provenance | Source name only. | Query context reported, but no retained record export. | Not a field-quality claim. | A future contract needs explicit collection and retrieval provenance. |
| Title and company | Complete. | Both fields reported. | Both fields documented. | Core facts have evidence in both sources. |
| Description | Processed text complete. | Not in restricted output. | Summary and formatted description documented. | Provider capability and value quality remain unmeasured. |
| Source level | Complete five-label distribution. | Not in restricted output. | `job_seniority_level` documented. | Keep source labels as source facts. No cross-source mapping exists. |
| Title-level signal | 31.2% English-marker coverage under a non-semantic diagnostic rule. | No retained titles for analysis. | Not a mapping claim. | A later rule must be versioned, language-aware, and measured. |
| Job function | Complete, but selection-conditioned. | Not in restricted output. | `job_function` documented. | No equivalence is established. |
| Employment type | Absent. | Not in restricted output. | `job_employment_type` documented. | Unknown for VietnamWorks and untested for the provider. |
| Location | 98.2% present. | Field reported, with one observed null country code. | Location documented. | Keep source location plus normalization provenance. |
| Compensation | Display string complete only. | Not in restricted output. | Pay range and structured base salary documented. | No common compensation semantics exist yet. |
| Dates | Absent from the processed export. | `job_posted_date` reported. | Posted date documented. | Do not equate a provider date with VietnamWorks dates. |
| URLs and application availability | Source URL complete. | Source URL and application link reported. | Application availability documented. | Preserve each URL and its declared meaning. |
| Lifecycle | Absent. | No retained observation sequence. | Application availability is documented. | No lifecycle equivalence or availability claim is justified. |

## Evidence boundary

This audit does not authorize a provider, collection, retention, source selection, data-contract
implementation, or cross-source deduplication decision.
The provider eligibility, commercial, and authorization gates are now recorded per source in the
[ingestion gate register](../../refactor/ingestion-gate-register.md).
The issue #423 rows above are dated measurements, and the
[issue #455](https://github.com/Park-Hip/InternHunterAgent/issues/455) blueprint remains the
governing data contract.
