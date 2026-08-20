# Documentation Conventions

> **Last verified:** 2026-08-20

Use these conventions for every Markdown document in this repository.

> **Eviction:** A convention leaves when a replacement convention is adopted and every affected
> document is brought into compliance.

## Readability

- Wrap prose at 100 characters or fewer. Table rows, fenced code, link-only lines, and long
  URLs are exempt.
- Keep paragraphs to five lines or fewer after wrapping.
- Lead with the answer: use a brief summary, table, or bullets before explanatory prose.

## Dates and verification

- Write dates as absolute ISO dates: `YYYY-MM-DD`.
- Living documents state when their operational claims were checked with a
  `> **Last verified:** YYYY-MM-DD` stamp.

## Links and historical references

- Use relative Markdown links and backticked repository paths only when they resolve locally.
- Retain references to files intentionally preserved only on a release tag by adding
  `<!-- archived-on-tag -->` to that same line.
- A historical audit may list paths that were intentionally missing when it was measured.
  Keep that evidence intact and wrap the measured region in
  `<!-- lint-allow-link-path:begin -->` and `<!-- lint-allow-link-path:end -->`.

## Evaluation scenario IDs

`evals/scenarios_v1.yaml` owns every scenario definition, so a scenario ID written in documentation
is a reference to that registry rather than a fact of its own. The `scenario-id` check reads every
`HLP-`, `HON-`, and `SAF-` identifier in tracked Markdown and fails on any the registry does not
define, which catches a renamed or deleted scenario that left a stale name behind.

Add `<!-- lint-allow-scenario-id -->` to a line that must name an ID on purpose, such as an example
of what the check rejects.

## Encoding safety

All documentation is UTF-8 without a BOM. Never round-trip documentation through PowerShell
`Get-Content` and `Set-Content`: that workflow can corrupt punctuation such as em dashes and
add a BOM. Use an editor configured for UTF-8, or an explicit UTF-8-safe tool instead.

The linter detects known mojibake signatures. When a document must quote one literally, put it
inside a backticked code span or add `<!-- lint-allow-encoding -->` on that line.

## Documentation lifecycle

- **Rule A - state the exit.** Every living document has a header `> **Eviction:**` line that
  says what content leaves and when.
- **Rule B - collapse corrections.** Rewrite against current truth instead of appending a
  correction. Git retains the superseded version.

Both rules are conventions an author applies, not checks. The `amendment` check that used to
flag correction-on-correction phrasing was retired by **D-047**, along with the
`<!-- lint-allow-amendment -->` marker that suppressed it.

The [planning skill](../skills/plan/SKILL.md) applies these conventions when it prepares a change
plan.
