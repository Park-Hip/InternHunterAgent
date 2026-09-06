# Structural Checks — Layer 2

> **Source:** `evals/grader.py`

Structural checks are the **highest-priority** deterministic checks. They verify observable
facts about the agent's behavior regardless of answer wording. A structural failure always
produces FAIL, even if all literal checks pass.

## Tool Routing Checks

| Check | What it verifies | Applies to |
|---|---|---|
| `required_tool_called` | Was the expected tool in `tools_called`? | All scenarios with `expected_tools` |
| `allowed_tools_called` | Were only allowed tools called? | Conversational scenarios with `turn_tool_expectations` |
| `no_tool_called` | Was no tool called? | SAF-OFF-TOPIC-REDIRECT-1, HLP-CLARIFY-1, HLP-REFERENT-2 |

## Answer Style Checks

| Check | What it verifies | Pattern / Logic |
|---|---|---|
| `no_decorative_symbols` | No emoji or decorative symbols in answer | Regex: `[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff\ufe0f\u20e3]` |
| `no_schema_identifier_leak` | No database column names quoted in answer | Checks compound identifiers with `_` not in sanctioned glossary |

## Vietnamese Prose Purity

| Check | What it verifies | Applies to |
|---|---|---|
| `vietnamese_agent_prose` | Answer prose (after removing row values and schema IDs) contains no English prose words | All `language: vi` scenarios with current prompt version |

Implementation: strips all returned row values and schema identifiers from the answer, then
checks if any remaining ASCII words (2+ chars) match the English prose stopword list (`a an
and are as at be but by can does for from has have how i in is it job jobs my not of on or
that the these this to was were what which with you your`). Accented Vietnamese words like
`toàn` are not treated as English because `\w` is Unicode-aware.

## Salary Period Check

| Check | What it verifies | Pattern |
|---|---|---|
| `salary_period` | When a salary amount is stated, it must not be paired with a payment period word | `\b(?:monthly|yearly|hourly|per\s+(?:month|year|hour)|tháng|thang|năm|nam|giờ|gio)\b` |

Only triggers when the answer actually mentions a returned salary amount (currency + number
both present). Calendar references like "tháng 5" or "năm 2026" are not flagged — only
explicit payment frequency indicators trigger the check.

## Job Level Fidelity

| Check | What it verifies | Logic |
|---|---|---|
| `job_level_fidelity` | Reported structured job levels match returned canonical values exactly | Rejects shortened forms ("Experienced" when row says "Experienced (non-manager)") and invented levels |

## Title-to-Level Inference

| Check | What it verifies | Logic |
|---|---|---|
| `senior_title_level_inference` | "Senior" in a job title cannot be mapped to the structured level "Experienced (non-manager)" | If answer claims a structured level but returned rows don't contain that level, it fails |

## Lifecycle Date Substitution

| Check | What it verifies | Pattern |
|---|---|---|
| `no_lifecycle_date_substitution` | An absent application deadline must not be replaced by listing expiry or record creation dates | Forbids lifecycle date mentions unless clarified with "not an application deadline" language |

## Source Link Checks

| Check | What it verifies | Pattern |
|---|---|---|
| `source_links` | Every returned source URL must be labelled (nguồn / source link / Link: / đường dẫn / url) | Checks for label keywords in answer text |
| `source_links.availability` | Source links must not claim the posting is still open/available | `\b(?:is|are|currently|still)\s+open\b`, `(?:đang|vẫn|còn)\s+(?:mở|tuyển)\b` |

### Source links cascade fix (2026-09-04)

When `execution_accuracy` fails, the grader previously used the agent's wrong
`generated_rows` to validate `source_links`, causing a false double-fail cascade.
The fix adds an `execution_passed` parameter to `_source_link_check`; when execution
has failed, it extracts URLs directly from the answer text instead of requiring URLs
from the incorrect returned rows.

## Tests

- `tests/evals/test_grader.py` (~1,480 lines) — Unit tests for every structural check function
