# Documentation Conventions

> **Last verified:** 2026-08-10

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

## Encoding safety

All documentation is UTF-8 without a BOM. Never round-trip documentation through PowerShell
`Get-Content` and `Set-Content`: that workflow can corrupt punctuation such as em dashes and
add a BOM. Use an editor configured for UTF-8, or an explicit UTF-8-safe tool instead.

The linter detects known mojibake signatures. When a document must quote one literally, put it
inside a backticked code span or add `<!-- lint-allow-encoding -->` on that line.

## Documentation lifecycle

- **Rule A - state the exit.** Every capped document has a header `> **Eviction:**` line that says
  what content leaves and when.
- **Rule B - collapse corrections.** Rewrite against current truth instead of appending a
  correction.
  Git retains the superseded version. The amendment check flags `no longer`, `read every`,
  `correcting an earlier`, and `superseded above` outside code spans. Use
  `<!-- lint-allow-amendment -->` only for a necessary historical reference.

The [ticket-writing skill](../skills/generate-ticket-prompt/SKILL.md) applies these conventions
when it generates a ticket prompt.
