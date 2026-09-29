---
name: frontend-design
description: Design and review the InternHunter web UI. Use when creating or changing anything under src/api/static/ (index.html, styles.css, tokens.css, app.js), or when a task mentions layout, typography, colour, spacing, dark mode, streaming states, contrast, or "the UI looks bad" or "make it look better". Covers the pinned token system, the visual avoid-list, the two-pass art-direction workflow, the Vietnamese typography rules, and the mandatory screenshot review.
---

# Frontend design

## Scope

The UI is static: `src/api/static/`, served by FastAPI. No SPA, no client framework, no
build step. Do not introduce one without a Change proposal. Python owns everything else.

## Step 0 - always, before writing any markup or CSS

1. Read `references/tokens.md` for the pinned values and the rules behind them.
2. Read `references/antipatterns.md` for the avoid-list.
3. Read `src/api/static/tokens.css`. It is the single source of truth.
4. If you touch colour, type, or spacing, run `uv run python scripts/check_contrast.py`
   and keep it passing. If you add a colour token, add its pair in that script in the
   same commit or the token is unenforced.

**Never hardcode a colour, radius, font size, spacing value, or duration in
`styles.css` or in markup.** If a value is missing, add a token.

## Two passes - do not skip

**Pass 1, no code.** Write the plan: the colours with exact OKLCH values, the type roles
and scale, an ASCII wireframe, the alignment, the max-width. Then critique that plan
against the brief in one short paragraph. State the audience and the job-to-be-done.

**Pass 2, code.** Implement pass 1. Not a variation of it.

Constraints, not adjectives. "Make it premium" is not a constraint;
`oklch(57.2% 0.178 34.5)` is.

## Spend your boldness in one place

One accent, three jobs: primary action, focus ring, one data series. Tinting buttons,
borders, headings, and backgrounds all with the same hue reads flat because it destroys
the accent-to-neutral ratio that carries hierarchy.

## Vietnamese is a first-class language, not a localisation

Vietnamese stacks a circumflex and a tone mark above the base letter, as in `ệ ữ ỗ ặ ằ`,
and needs roughly 1.4 to 1.6 times the Latin headroom at the same size. Therefore:

- Body text is 16px or larger. Never set `line-height: 1.0` near Vietnamese text.
- The typeface is Be Vietnam Pro, self-hosted, because it draws those marks natively.
  Do not swap in a family without Vietnamese coverage.
- **Verify the glyph string `ệ ữ ỗ ặ ằ ế` renders with no mid-paragraph fallback**
  before merging any typeface change. A paragraph that starts in one family and ends in
  another is the failure this rule exists to catch.
- Do not send on Enter while an IME composition session is active
  (`event.nativeEvent.isComposing`). This is a real bug class for Vietnamese input.

## Quality floor - all of it, every time

- Responsive to 390px with no horizontal overflow at any nesting level.
- Visible `:focus-visible` ring; focus is never obscured by a growing element
  (WCAG 2.2 SC 2.4.11).
- Every interactive target at least 24x24 CSS px (WCAG 2.2 SC 2.5.8).
- Text contrast at least 4.5:1, enforced by the contrast script, not by eye.
- `prefers-reduced-motion` honoured, with no motion as the default.
- `lang="vi"` on the document element.
- Streaming text is announced exactly once; see `references/a11y.md`.

## Mandatory before declaring done

1. Run `uv run python scripts/ui_screenshots.py`. It captures 390, 768, and 1440 in
   both colour schemes into `.playwright-cli/ui/`.
2. **Read the PNGs back.** Source review cannot see hierarchy, wrapping, or contrast as
   rendered. This step is the point of the loop, not a formality.
3. Name the single highest-impact visual flaw out loud. Fix only that one.
4. Re-capture and look again. One iteration is the floor, not the ceiling.

## Out of scope here

Component structure and the streaming state machine are covered by their own change
proposals. Do not redesign the layout, shrink the masthead, or restructure the
conversation while doing token or typography work; one coherent change per pull request.
