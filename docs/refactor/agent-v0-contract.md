# Agent v0 behavior and metric contract

> **Last verified:** 2026-09-29
>
> **Eviction:** This contract is replaced when the agent-v0 cutover in
> [#486](https://github.com/Park-Hip/InternHunterAgent/issues/486) is measured against the
> evaluation baseline and adopted, or when a successor contract is approved. Until then it is the
> active specification of what the agent may claim about job postings.

This is the Stage 1 deliverable of the agent-v0 track under
[#472](https://github.com/Park-Hip/InternHunterAgent/issues/472).
It is a documentation-only contract.
It changes no code, no prompt, no schema, and no scenario, and it is written so that a maintainer
can decide what a correct answer looks like without reading a prompt.

The legacy behavior rules `G01` through `G47` are historical evidence.
Their disposition is recorded in
[the legacy rule disposition](agent-v0-legacy-rules.md), and no rule is inherited by default.

## The maintainer decisions this contract implements

Recorded on 2026-09-29, before any line below was written.

| Decision | Resolution |
| --- | --- |
| Product scope for v0 | Search over recorded postings, plus the defined analyses in this contract. |
| Comparisons in v0 | Yes, limited to one metric over two filter sets with identical metric definitions. |
| Open-ended novel analysis for ordinary users | Not in v0. That is the decision of [#487](https://github.com/Park-Hip/InternHunterAgent/issues/487). |
| Track ordering | The agent-v0 track runs in parallel with the module-layer backlog under a recorded exception, bounded to documentation, dataset, and additive tool work. |
| v1 registry placement | History only. The restored v1 file is not committed back into the active tree. |

## What v0 answers, and what it refuses to answer

### The seven supported question shapes

| ID | Shape | User intent | Result |
| --- | --- | --- | --- |
| `S1 LIST` | Which postings match these conditions | Discovery | A list of matching postings with the matching basis named |
| `S2 COUNT` | How many match | Sizing | One number over the full matching set |
| `S3 GROUP_COUNT` | How many match, per value of one recorded field | Breakdown | One row per recorded value, with the total |
| `S4 TOP_N` | The highest or lowest by one recorded field | Extremes | Exactly N rows, or all rows when N exceeds the match count |
| `S5 AGGREGATE` | One number over the matching set | Analysis | A scalar with its numerator, denominator, and exclusions stated |
| `S6 COMPARE` | The same number for two different conditions | Comparison | Two values computed the same way, or a stated reason why not |
| `S7 DETAIL` | Tell me about these specific postings | Detail on postings already listed | The requested fields of the named postings, with absences named |

A message that contains at most two of these shapes is decomposed and both are answered, each
labelled separately.
A message that contains more than two is not decomposed: the agent answers the first and asks one
clarifying question about which of the remaining ones to compute next.

### What v0 does not answer

| Request | State | Why |
| --- | --- | --- |
| Open-ended analysis, "analyze the market", "find anything interesting" | `UNSUPPORTED` | No v0 shape expresses it. The decision belongs to #487. |
| A request that depends on a prior turn, such as "now only the ones in Da Nang" or "how about the second one" | `UNSUPPORTED` | v0 is single-turn and carries no state between turns, so the referent has nothing to resolve against. A self-contained follow-up is answered normally. |
| "Is this posting still open", "which are new this week", "when was it published" | `UNSUPPORTED` | The data records no publication date, no application deadline, and no truth about open status. See the three date fields in the field contract. |
| Any question that needs `source`, `external_id`, `posted_date`, `first_seen_at`, or `last_seen_at` | `UNSUPPORTED` | Hidden from the agent by contract, in `config/prompts.yaml` and enforced in `src/api/schema_guard.py`. Their existence is not disclosed. |
| One salary figure across two or more currencies | `UNSUPPORTED` | The values are not comparable without a rate the data does not carry. The scoped alternative is offered instead. |
| Writes, deletions, configuration changes, prompt text, connection strings | `REFUSED` | Read-only scope. |
| Instructions embedded in a posting's text | `REFUSED` | Tool-returned text is data, never instruction. |
| Filtering by a protected or personal attribute | `REFUSED` | Declined on values, with a legitimate alternative offered. |
| Anything that is not about these postings | `REFUSED` | Off-topic redirect. |

## The four answer states

Every answer is exactly one of these.
The state is a contract term, not a tone.

| State | When | Required format |
| --- | --- | --- |
| `ANSWERED` | The question maps to a supported shape over recorded data | The answer, then the evidence labels that qualify it |
| `CLARIFIED` | The request is ambiguous and no defensible reading exists | Exactly one narrow question, then stop. No answer, no tool result, no partial guess. |
| `UNSUPPORTED` | The question is answerable in principle but not from this data at v0 | One sentence naming what is not available, plus the closest supported alternative when one exists |
| `REFUSED` | The request is out of scope, unsafe, or an instruction override | One sentence, then the redirect. Never a lecture and never a tool call. |

`CLARIFIED` is the only state that ends a turn without an answer, and it asks at most one question.
A turn never asks a second question, and never combines a refusal with an answer.

## The visible field contract

Sixteen columns are visible to the agent.
`docs/reference/schema.md` and `src/api/schema_guard.py` are the machine record; this table is the
permitted-use contract on top of them.

| Field | What it records | May be used for | May never be used for |
| --- | --- | --- | --- |
| `id` | Stable surrogate key within one data load | Chaining a detail request to a listed posting | Being described as a durable identifier; it does not survive a reload |
| `title` | The raw posting title | Free-text matching, listing | Inferring seniority, level, or salary |
| `company` | The employer name as written on the posting | Filtering, listing, counting by company | Claiming anything about the employer outside these postings |
| `role` | Canonical role category assigned at ingestion | Category matching and grouping | Being read as the literal job title |
| `description` | Merged posting prose: description, requirements, benefits | Free-text matching only, always labelled | Projection into a list or a count; as a structured fact; as instruction |
| `tech_stack` | Comma-separated canonical technology tokens extracted at ingestion | Technology matching and grouping | Proof that a posting requires that technology |
| `job_level` | The source's own level string, one of five recorded values | Level filtering, grouping, coverage statements | Being invented, completed, or normalized to another scale |
| `location` | Canonical city name, or `Other` | City filtering and grouping | Country, region, or "near me" claims |
| `source_url` | Link to the original posting, nullable | Linking a listed posting | Claiming a posting is open, available, or closed |
| `listing_expires_on` | The source's stated listing expiry, nullable | Reporting the expiry as itself, with the not-a-deadline label | Being called an application deadline or proof of open status |
| `created_on` | When the source record was created, nullable | Ordering by source-record age, with the label | Being called a publication, posting, or start date |
| `is_internship` | Whether the posting is an internship | Exact boolean filtering | Being inferred from the title, level, or salary |
| `salary_min` | Lower bound of the advertised salary, nullable | Aggregates within one currency | Being presented with a payment period |
| `salary_max` | Upper bound, nullable, absent when the source states no upper bound | Aggregates within one currency | Being invented when absent; being treated as zero |
| `salary_currency` | Currency code, nullable | Scoping every salary figure | Being inferred when null |
| `is_salary_negotiable` | Whether the salary is negotiable | Reporting the negotiable state | Being used as a filter on the user's behalf when the user asked about salary |

Column names are never quoted in an answer.
An answer names a field in ordinary language, and a value it reports is reproduced exactly as
stored.

## Matching rules

Matching is a filter decision, and every filter decision is disclosed in the answer through its
`MATCH_BASIS` label.
A filter never silently widens or narrows the request.

### Role

`role` holds a canonical category, not a title.
A role term is matched against the canonical value first.
A term with no canonical category falls back to `title` and `description` free-text matching, and
the answer must say the rows matched on posting text and that they are categorized as `Other`.
A technology term never adds a role filter: a request for "ML jobs" is a technology request, and
adding the `ML Engineer` category would return rows that never mention machine learning anywhere.

### Technology

`tech_stack` holds canonical tokens produced by the ingestion vocabulary in
`config/tech_vocabulary.yaml`, which already maps `ML` to `Machine Learning`, `NLP` to
`Natural Language Processing`, `LLM` to `Large Language Models`, `AI` to `Artificial Intelligence`,
and `CV` to `Computer Vision`.
That file is the single expansion table for v0. No second table is introduced.

Matching is by whole token, not by substring.
`%ML%` is forbidden, because the 24-row fixture contains `MLOps` and `MLflow` in `tech_stack`, so a
substring match on `ML` returns postings that never name machine learning.
A multi-technology request is an intersection by default, and the answer states that reading.

Membership in `tech_stack` is a recorded extraction, not a requirement.
A posting can require a technology the extractor did not record, and can record one only in passing.
Every technology claim carries the `FREE_TEXT_HEDGE` label.

### Location

`location` holds canonical, unaccented city names produced by the city alias map in
`config/ingestion.yaml`, which currently resolves `Hanoi`, `Ho Chi Minh City`, `Da Nang`, `Can Tho`,
and `Hai Phong`, and `Other` when no known city is recognized.
The fixture holds three distinct values: `Hanoi` (11), `Ho Chi Minh City` (9), and `Da Nang` (4).

The stored values carry no diacritics, and the query path has no diacritic folding: there is no
`unaccent` extension in any migration and no folding function in the query layer.
The v0 answer to this is an explicit table, not a claim of folding.
The v0 query core resolves the user's city term through the same canonical names, plus `Saigon` for
`Ho Chi Minh City`, and reports the canonical value it matched.
A term that is not in the table and returns nothing is answered with `UNSUPPORTED` for that term and
the list of canonical city values, never with a guess.

Making matching genuinely diacritic-insensitive for arbitrary text needs a database extension or
function, which is a schema change.
It is recorded as an open decision below, not implemented here.

### Level

`job_level` is populated in every fixture row, with four distinct values:
`Experienced (non-manager)` (15), `Intern/Student` (5), `Manager` (2), and
`Fresher/Entry level` (2).
The prompt's schema context also names `Director and above`, which no fixture row carries, and
production coverage of any value is unmeasured.

So `job_level` is a queryable recorded field at v0, and the legacy assumption that level is absent
is retired.
A level answer reports the recorded value verbatim and states its coverage: how many matched rows
carry a level and how many do not.
`Senior` inside a `title` is title text and is never reported as a structured level, under any
phrasing.

### Free text

Free-text matching reads `description` only, and it is always hedged.
A concept with a known Vietnamese form is matched in both languages, for example `remote` and
`từ xa`.
A free-text match never becomes a denominator, a group value, or a claim of requirement.
In the fixture only two postings mention `remote` in their prose, which is why a free-text result is
a lead and not a count of remote jobs.

## Metric definitions

Every number the agent reports is computed by one of these definitions.
A number with no definition here is not reported.

### `COUNT`

The count of rows matching the stated filters, computed over the whole matching set, never over the
displayed rows.
The answer is one number plus the base it was computed on.
The 20-row display cap is a display limit and is never an input to a count.

### `GROUP_COUNT`

One row per distinct recorded value of the grouped field, plus a total.
Values are the stored values, reproduced exactly, ordered by count descending and then by value.
A null value is its own group, labelled as not recorded, and is never merged into another value.

### `SHARE`

A percentage over an explicitly stated base.

- The denominator is every row matching the base filter, including rows where the tested field is
  null.
- The numerator is the subset of the denominator that satisfies the test.
- The answer states the numerator, the denominator, and how many denominator rows were excluded
  because the tested field was null.
- When the denominator is zero, the answer is a share of nothing and is reported as such.

Worked on the fixture: "What percentage of AI Engineer postings list Python?" has a denominator of
the 5 `AI Engineer` rows, a numerator of the 5 of those whose `tech_stack` records `Python`, and 0
rows excluded for a null stack. The answer is 5 of 5.
The wrong answers a maintainer must be able to reject are 5 of 24, 5 of 12, and any answer that
counts only postings which already have a stack.

### `SALARY_AGGREGATE`

Salary is the most constrained metric in v0, because the data constrains it.

- **No payment period exists anywhere.** `clean_jobs` has no pay-period column, and the
  VietnamWorks normalizer copies `salaryMin`, `salaryMax`, and `salaryCurrency` and nothing else.
  Every salary figure therefore carries the `PERIOD_UNKNOWN` label. "Average monthly salary" is
  `UNSUPPORTED`: the data has no monthly salary to average.
- **One currency per figure.** A salary aggregate is scoped to exactly one `salary_currency`. Rows
  in other currencies are excluded and counted. A request that names no currency and matches more
  than one is answered per currency, never as one number.
- **Three stored states, reported as themselves.** A range with both bounds; a lower bound only,
  which the ingestion normalizer produces when the source states no upper bound and which must
  never be completed to zero or to an estimate; and no number at all, which splits into negotiable
  and not disclosed through `is_salary_negotiable`.
- **The aggregate is over a declared basis.** `AVERAGE` and `MEDIAN` are defined over `salary_min`,
  and the answer names `salary_min` as the basis.
- **A per-posting midpoint is computed, not stored, and is labelled.** It is computed only when both
  bounds are present. On the fixture no row has a lower bound without an upper bound, but production
  can, and a lower-bound-only row is excluded from a midpoint aggregate and counted.
- **The denominator is always stated**, with the count of rows excluded for having no number.

Worked on the fixture: "What is the average Data Scientist salary?" matches 5 `Data Scientist`
postings.
One of them records no salary at all, and that one is negotiable.
Of the remaining 4, one is USD and three are VND, so no single figure is answerable and the
scoped answer is one figure per currency, each over `salary_min`, each naming its own basis count
and the 1 excluded row.
The wrong answers to reject are a figure spanning USD and VND, a figure labelled monthly, and a
figure computed over all 5 rows.

### `TOP_N`

- One recorded attribute, one direction, one `N`.
- `N` is honored exactly. If fewer rows match, all of them are returned and the shortfall is stated.
- Ties at the boundary are broken deterministically by `id`, and the answer says a tie existed.
- Null values are never silently skipped without being counted: the answer states how many matching
  rows had no value for the sorted attribute and were therefore not ranked.
- For salary, the currency rule applies: `N` highest USD salaries is a different question from `N`
  highest salaries, and mixing them is `UNSUPPORTED`.

### `COMPARE`

- Both sides compute the same metric under the same definition, and the answer says so.
- Both sides state their own numerator, denominator, and exclusions.
- Salary comparisons must share one currency on both sides.
- When the two sides cannot be computed on the same basis, the answer is `UNSUPPORTED` with the
  reason, never two numbers that do not mean the same thing.

## The question shape contract

| Shape | Eligible records | Predicates | Denominator | Null treatment | Labels | States and format |
| --- | --- | --- | --- | --- | --- | --- |
| `S1 LIST` | All rows matching the filters, up to the display cap | Role, technology, city, level, company, internship, salary filters within the matching rules | Not applicable | A null field is omitted from the row and named once, not left as a gap | `MATCH_BASIS`, `TRUNCATION`, `LINK_MISSING`, `FREE_TEXT_HEDGE`, `PERIOD_UNKNOWN` for a salary column | `ANSWERED`, or `CLARIFIED`, or `UNSUPPORTED` |
| `S2 COUNT` | All rows matching the filters | Same as `S1` | The full matching set | No null effect: a row is counted or it is not | `MATCH_BASIS` | `ANSWERED` with one number, or `UNSUPPORTED` |
| `S3 GROUP_COUNT` | All rows matching the filters | Same as `S1` plus one groupable field | The full matching set | Null is its own group, labelled as not recorded | `MATCH_BASIS` | `ANSWERED`, or `UNSUPPORTED` for an ungroupable field |
| `S4 TOP_N` | All rows matching the filters, ranked | Same as `S1` plus one sortable recorded field and a direction | Not applicable | Nulls are not ranked, are counted, and are named | `MATCH_BASIS`, `CURRENCY_SCOPED` for salary | `ANSWERED`, or `UNSUPPORTED` for an unsortable field |
| `S5 AGGREGATE` | All rows matching the filters | Same as `S1` | The declared basis of the metric, always stated | Nulls are excluded from the computation and counted in the answer | `DENOMINATOR_STATED`, `CURRENCY_SCOPED`, `PERIOD_UNKNOWN` | `ANSWERED` with the scalar and its basis, or `UNSUPPORTED` |
| `S6 COMPARE` | Two filter sets, each evaluated independently | Two filter sets over the same field set | Each side's own | Each side reports its own exclusions | `DENOMINATOR_STATED`, `CURRENCY_SCOPED` | `ANSWERED` with two like-for-like values, or `UNSUPPORTED` |
| `S7 DETAIL` | The named postings only | An id the user received from `S1`, or that the agent showed | Not applicable | An absent field is reported as not recorded | `MATCH_BASIS` | `ANSWERED`, or `UNSUPPORTED` for an id that is not in the set |

### The display cap and the total

The display cap is 20 rows.
It is a presentation limit only.
A list answer always states the total number of matching rows, so 20 displayed out of 23 is
visible as `23` matching, not as `20`.
`TRUNCATION` is attached whenever the cap bites, and the answer names the field to narrow on.
The cap is never applied to an aggregate input.

### Links

`source_url` is nullable in the schema and comes from a source field that may be absent, so a listed
posting may have no link.
A link is shown when it exists.
When any listed posting has no link, the answer says how many of the listed postings have no source
link recorded, once, and never invents a link, a search URL, or a shortened form.
Every fixture row carries a link, so the fixture alone cannot demonstrate this case; the behavior is
required by the nullable column, not by the fixture.

## Answer language and evidence

Answers are written in Vietnamese.
Source values and canonical values are reproduced verbatim, which is data and not English prose.
An English question is answered in Vietnamese.

The 19 canonical strings in `config/prompts.yaml` remain the reference wording for the honesty,
safety, and refusal states.
They are reference text, not a phrase library the agent emits verbatim: an answer may rephrase as
long as the substance is preserved, and a caveat is never weakened or dropped.

The analytics states in this contract add the labels the legacy set has no phrase for.
Stage 6 wires them into the prompt; Stage 2 and Stage 5 grade against them.

| Label | Required when | Substance |
| --- | --- | --- |
| `MATCH_BASIS` | Any filter was applied | Which field the match came from, and for a fallback match, that it is free text |
| `DENOMINATOR_STATED` | Any aggregate, share, or comparison | The numerator, the denominator, and the excluded count |
| `CURRENCY_SCOPED` | Any salary figure or aggregate | Which currency, and how many rows in other currencies were excluded |
| `PERIOD_UNKNOWN` | Any salary figure | That the stored number carries no payment period |
| `LINK_MISSING` | A listed posting has no `source_url` | How many listed postings have no recorded link |
| `COVERAGE_STATED` | A claim about level, salary, or any nullable field | How many matching rows carry the field and how many do not |
| `TRUNCATION` | The display cap bit | The total matching count and the displayed count |
| `FREE_TEXT_HEDGE` | A match or claim rests on posting prose | That the match is based on how the posting is worded and may be imprecise |

## Worked examples

Five cases, each walked against the 24-row fixture in `evals/fixtures/seed_eval_db.sql`.
The fixture is engineered to make assertion counts deterministic, and no number here is a production
statistic.

### 1. A percentage with an explicit denominator

Question: "What percentage of AI Engineer postings mention Python?"

Eligible records: the 5 rows whose `role` is `AI Engineer`.
Predicate: the `tech_stack` token is `Python`.
Denominator: all 5, including any row with a null stack; the fixture has none, and 0 are excluded.
Answer: 5 of 5, with the basis named.
Rejected answers: 5 of 24, 5 of 12, and any figure that first filters to rows having a stack.

### 2. A salary average that the data cannot support as asked

Question: "What is the average salary for Data Scientists?"

Eligible records: the 5 rows whose `role` is `Data Scientist`.
State: `ANSWERED` only in the scoped form, `UNSUPPORTED` in the asked form.
Asked form rejected: "the average salary" implies one figure and a period.
Scoped answer: per currency, over `salary_min`, with the 2 rows that record no salary named as
excluded and the `PERIOD_UNKNOWN` label attached.
Rejected answers: one number spanning USD and VND, any figure described as monthly or yearly, and a
figure computed over all 5 rows.

### 3. A deadline the data does not contain

Question: "What is the application deadline for these jobs?"

State: `UNSUPPORTED`.
The data has no application deadline field.
`listing_expires_on` is the source's listing expiry and 4 fixture rows have none recorded, so it can
be reported as itself with the not-a-deadline label, and only if the user wants that field.
Rejected answers: treating an expiry date as a deadline, inventing a deadline, or reporting a date
from `created_on`.

### 4. A free-text match that is not a count

Question: "How many remote jobs are there?"

Eligible records: every row, because `remote` is not a structured field.
Predicate: `description` contains `remote` or `từ xa`.
State: `ANSWERED` as a hedged lead, never as a structured count.
Answer: 2 postings mention it in their prose, with `FREE_TEXT_HEDGE`, and the answer says this is
posting text and not a remote-work field.
Rejected answers: presenting 2 as the number of remote jobs, or claiming a remote count is
unavailable.

### 5. A listed posting with no link

Question: "List the Data Analyst jobs in Ho Chi Minh City."

Eligible records: the fixture holds one such row, and it carries a link, so the fixture cannot
demonstrate the case.
State: `ANSWERED`.
Required behavior: the link is shown when present; when a listed posting has none, the answer
reports how many of the listed postings have no recorded source link, once, and never substitutes
a constructed or searched URL.
Rejected answers: omitting the row because it has no link, or fabricating a URL for it.

## Recorded open decisions

These are recorded rather than guessed, and each needs its own approval.

1. **Diacritic-insensitive matching for arbitrary text.** Requires a database extension or function,
   which is a schema change. The v0 behavior is an explicit alias table, stated above.
2. **Production coverage of `job_level` and salary disclosure.** The fixture is engineered and says
   nothing about production. The contract requires `COVERAGE_STATED` rather than assuming a
   populated field, and the number is unmeasured.
3. **Exploratory SQL for ordinary users.** Decided in #487, not here.
4. **Multi-turn support.** Retired at v0. Whether it returns is a product decision, not a contract
   detail.

## Verification of this contract

| Check | Command or method | Expected result |
| --- | --- | --- |
| Every named field exists in the agent-visible contract | Compare this table with `docs/reference/schema.md` and the `schema_context` prompt | The 16 fields match exactly, with no addition and no omission |
| Every named field exists in the ORM | Compare with `src/services/ingestion/models.py` | Every field above is a real mapped column |
| The no-pay-period claim is true | `clean_jobs` has no pay-period column, and `src/services/ingestion/normalize/vietnamworks.py` copies only `salaryMin`, `salaryMax`, and `salaryCurrency` | No period can be stated without invention |
| The diacritics claim is true | No migration creates an extension, and no query module folds diacritics | Matching is case-insensitive only |
| The fixture numbers are true | Parse `evals/fixtures/seed_eval_db.sql` | 24 rows; 5 `AI Engineer`; 5 of 5 with `Python`; 12 VND, 6 USD, 6 with no salary, of which 3 negotiable; 4 rows with no expiry |
| Documentation hygiene | `uv run python scripts/docs_lint.py` | Exit 0 |
| Manual walk | Give a maintainer the four questions from the issue: the AI Engineer percentage, the salary average, the missing application deadline, and an ambiguous analytics request | The maintainer states the denominator, the salary and missing-data policy, and the clarify-or-answer boundary from this document alone |
