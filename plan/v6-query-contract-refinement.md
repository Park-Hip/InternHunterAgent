# V6 Query Contract Refinement Plan

> **Status:** Approved planning artifact, written 2026-08-24.
> This plan implements the first, focused correction identified by
> [the V6 evaluation run review](../research/v6-evaluation-run-review-2026-08-24.md).

> **Last verified:** 2026-08-24 against the V6 replay, the current query tool, caveat detector,
> evaluation registry, and focused tests.

> **Eviction:** This plan leaves when the new prompt-version capture and its human review confirm
> the query and answer contract, or when a recorded decision supersedes its scope.

## Goal and expected outcome

Make ordinary job queries use the smallest useful SQL projection, so tool results contain only
information that the response needs.
Make generated answers include the original source link for each listed posting when a link exists,
including after the source listing expires, without claiming that the posting remains open.
Make date and salary caveats appear only when the query actually concerns those subjects.
Make a cross-currency salary request return separate USD and VND results rather than one global
winner.

The expected outcome is a new prompt-version capture in which ordinary lists no longer carry
incidental lifecycle and salary values, count queries use `COUNT(*)`, source links are rendered for
listed jobs, and the agent does not rank raw values across currencies.

This is a planned change because it changes the model-facing contract, tool behavior, evaluation
contracts, and release evidence across several files.

## Decisions already made

| Decision | Direction |
| --- | --- |
| First scope | Limit this change to the query contract, minimal projections, intent-scoped caveats, source-link output, and cross-currency presentation. |
| Source links | When a listed job has a `source_url`, include that original link in the answer even after `listing_expires_on`. Label it as a source link and do not imply the job is still open. |
| Cross-currency salary | Return separate, non-ranked currency groups instead of asking the user to choose a currency. |
| Safety routing | Exclude a deterministic pre-tool guardrail for destructive and discriminatory requests from this change. |

## Scope

### In scope

- Add a precise projection and answer contract to `config/prompts.yaml` and increment
  `prompt_version` from v7.
- Keep `source_url` as the intentional exception to minimal projection for list results, because
  the product will now show it to the user.
- Revise caveat detection so merely projecting `created_on`, `listing_expires_on`, or salary fields
  does not create a mandatory caveat.
- Add query-contract tests that make a count query require an aggregate rather than accepting a
  coincidentally equal number of retrieved rows.
- Add scenario-owned assertions for source-link output, selected-column expectations, and
  cross-currency grouping.
- Add deterministic answer checks for the observable semantic requirements in this scope.
- Capture and review a new versioned evaluation artifact after the code and focused tests pass.

### Explicit exclusions

- Do not add a profanity, sexual-content, destructive-request, or discriminatory-request guardrail.
- Do not change the SQL validator's read-only and single-table security boundary.
- Do not modify fixture data, schema, models, ingestion, or `CHANGELOG.md`.
- Do not change the frozen V6 replay or treat it as comparable to the new prompt version.
- Do not enable or calibrate the LLM semantic judge.
- Do not add a general URL-checking service or attempt to validate that source links are live.
  A retained URL is a source reference, not evidence that a listing is open.
- Do not bundle the broader English-prose, salary-period, senior-title, role-fallback, ML-abstraction,
  or safety-routing corrections into this pull request.

## Implementation steps and file ownership

### 1. Specify the new query and answer contract

**Files:** `config/prompts.yaml`, `tests/agents/runtime/test_prompts.py`, and
`tests/test_prompt_consistency.py` if its prompt parsing expectations require an update.

Add compact rules to the SQL-generation prompt.

- A count uses only `COUNT(*) AS count` and never selects row columns, `id`, or `source_url`.
- A normal list selects `id`, `title`, `company`, `location`, and `source_url`.
- Add a column only when it is required to answer the user's requested attribute.
  A field used only for filtering, ordering, grouping, or aggregation stays out of the projection.
- `description` remains filter-only and never appears in a projection.
- `source_url` is included for a normal list so the final answer can show the original posting link.
- A source link remains useful after listing expiry, but it must be labelled as the original source
  link and must not be presented as an availability signal.
- A salary comparison across multiple currencies returns one non-ranked group per currency, ordered
  only within that currency.
- Salary amounts have no payment-period field, so the answer must not add a monthly or other period.
- When reporting a canonical job-level value, preserve it verbatim rather than shortening it.

The contract is deliberately a projection-and-rendering pair.
The SQL generator must not retrieve information merely because it can use that information to find
or sort rows, and the answer generator must not imply facts beyond the selected result.

| Query family | Required SQL projection | Required answer shape |
| --- | --- | --- |
| Count | `COUNT(*) AS count` only | One concise count sentence. No job list, source links, or follow-up question. |
| Normal list | `id`, `title`, `company`, `location`, `source_url` | Each displayed posting names its title, company, and location, then shows its non-null URL as an `original source link`. The link is not evidence that the posting is open. |
| Attribute list | The normal-list projection plus only the requested display attribute | Report the requested attribute without adding incidental salary, lifecycle, level, or internship detail. |
| Aggregate or grouped result | Only the aggregate expression and its grouping keys | Report the aggregate or groups. Do not select `id` or source links unless the user also asks for postings. |
| Salary comparison across currencies | The requested salary values plus `salary_currency` | Present a separate non-ranked group for each currency, ordered only inside that group. Do not invent a payment period or name a global winner. |

An `ORDER BY`, `WHERE`, or `GROUP BY` field does not by itself authorize that field in the answer.
For example, a newest-job query may order by `created_on` without rendering the raw date unless the
answer needs it to explain the ordering and preserve the creation-date caveat.

Keep the rules close to the existing count, salary, and schema instructions instead of adding a
second prompt block or a list of scenario-specific examples.
Bump the prompt version exactly once with this prompt-surface change.

### 2. Make caveat injection follow query intent

**Files:** `src/services/query/obligations.py`, `tests/services/query/test_obligations.py`, and
`tests/agents/tools/test_query_clean_jobs.py` when the rendered contract changes.

Refine `detect_obligations` so the following rules are driven by meaningful SQL use rather than a
column merely appearing in the select list.

- `CREATED_ON_CAVEAT` fires when `created_on` is used for filtering or ordering, including a
  newest or oldest result.
- `LISTING_EXPIRY_NOT_DEADLINE` fires when listing expiry is filtered, ordered, or requested as the
  answer subject, not on every ordinary list.
- `NEGOTIABLE_SALARY` fires only when salary is being returned to answer a salary request and at
  least one displayed salary is missing or negotiable.
- Existing zero-results and free-text obligations remain unchanged.

Keep obligation detection deterministic and local to the query layer.
Do not make caveat selection depend on the synthesis model or on a new classifier.
Document in tests the deliberate limitation that a direct request to display a lifecycle field needs
an explicit SQL signal that preserves its caveat, rather than relying on an incidental projection.

### 3. Extend the deterministic evaluation contract

**Files:** `evals/scenarios_v1.yaml`, `evals/execution_accuracy.py`, `evals/grader.py`,
`tests/evals/test_execution_accuracy.py`, `tests/evals/test_grader.py`, and
`tests/evals/test_scenarios.py`.

Add registry-owned projection expectations for the scenarios touched by this change.
The execution layer must report a projection violation separately from an incorrect row set, so
the agent cannot pass by returning the right rows with a wide or unsuitable select list.

At minimum, cover these contracts.

| Behavior | Required evaluation contract |
| --- | --- |
| Count | Require one `COUNT(*)` aggregate result, not a row list whose length happens to equal the count. |
| Ordinary list | Require the normal-list projection, including `source_url`, and prohibit incidental lifecycle and salary columns. |
| Salary answer | Allow salary fields only for a salary request. Require separate USD and VND groups and prohibit a single cross-currency winner. |
| Newest result | Permit `created_on` for ordering and require the creation-date caveat without calling it a posting date. |
| Source link | For list scenarios, require every non-null returned source URL to be present as a clearly labelled source link in the final answer. |

Use the registry as the owner of scenario-specific expectations under D-041.
Do not make the grader infer a required projection from user-language heuristics.
Update the existing currency scenario to expect and validate separate groups, not only the absence of
a single winner.

### 4. Add focused offline and end-user verification

**Files:** no production file beyond the tests above, plus a new ignored capture generated by the
evaluation driver.

Run unit and fixture-backed tests first.
Then load the frozen fixture and capture the changed scenarios under the new prompt version before
attempting a full capture.
Read all answers that differ from V6, with special attention to list, count, newest, salary, and
source-link output.
Only after this review succeeds, capture the full registry and preserve the new replay according to
the existing sanitization and replay rules.

## Verification

### Automated

- `uv run pytest tests/services/query/test_obligations.py`
- `uv run pytest tests/agents/tools/test_query_clean_jobs.py`
- `uv run pytest tests/agents/runtime/test_prompts.py tests/test_prompt_consistency.py`
- `uv run pytest tests/evals/test_execution_accuracy.py tests/evals/test_grader.py tests/evals/test_scenarios.py`
- `uv run python scripts/docs_lint.py`
- `uv run python scripts/docs_build.py --check`
- `uv run pytest`

The fixture-dependent evaluation tests require the local fixture database at port 5433.
If it is unavailable, identify that as the existing infrastructure blocker rather than reporting an
incomplete test run as a product regression.

### Manual checklist

1. Ask for AI Engineer listings.
   Expected: title, company, location, and a labelled source link for each listed posting.
   The answer must not add salary, expiry, or record-creation commentary unless asked.

2. Ask how many AI Engineer jobs exist.
   Expected: one concise count sentence, no job list, no source links, and no follow-up question.

3. Ask which job has the highest salary.
   Expected: separate USD and VND groups, each ranked only within its currency, with no global
   highest-paid claim.

4. Ask for the newest job.
   Expected: one result, clearly described as ordered by the source record's `created_on`, not as a
   confirmed publication date.

5. Ask for a normal technology or location list.
   Expected: no unrelated lifecycle or negotiable-salary caveat.

6. Open a source link from a listed job whose listing expiry is in the past.
   Expected: the agent has labelled it as the original source link and makes no claim about whether
   the job is still open.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Requiring source links increases list-result context slightly. | It is an explicit product decision and replaces much larger, unrelated date and salary projections. |
| A prompt rule alone may not reliably constrain projections. | Add registry-owned execution checks so a fresh capture reveals any violation deterministically. |
| Removing incidental caveats could omit a caveat for a direct lifecycle-field request. | Test lifecycle filter and order cases explicitly, and preserve the caveat when the field participates in the query. |
| The model may still render a source link as proof that a job is open. | Require source-link wording that separates the link from availability, then inspect the changed answers before full capture. |
| Cross-currency groups may be long on a larger corpus. | Reuse the row bound and group only the displayed results. A future product decision can add a per-currency limit. |
| V6 score comparisons may be misread across prompt versions. | Retain V6 unchanged, stamp the new capture with the bumped version, and describe the result as a new baseline. |

## Follow-up work deliberately deferred

- Deterministic pre-tool safety routing for destructive and discriminatory requests.
- The dedicated senior-title, ML-abstraction, canonical-role fallback, and `Other` role fixes.
- Broader answer-style enforcement for English prose and invented salary periods outside the focused
  query-contract scenarios.
- A machine-readable human-disposition record that resolves the V6 aggregate-count discrepancy.
- Semantic-judge calibration and use as a release gate.
