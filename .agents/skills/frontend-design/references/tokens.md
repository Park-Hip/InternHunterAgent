# Pinned values

> **Last verified:** 2026-09-27

Everything here is enforced, not advisory. The contrast script fails the build if a
token drifts below its floor.

## Where the values live

`src/api/static/tokens.css` is the single source of truth. `styles.css` consumes it and
must contain no literal colour, radius, size, or duration. This file explains the values
and the reasoning; it does not override the CSS.

## Colour

OKLCH, because HSL lightness is not perceptual, so ramps cannot be derived from it.
Neutral hue is held at 85, which is warm and near-neutral: chroma 0 at zero chroma reads
as a screenshot of a design rather than a choice. The accent hue is 34.5.

The palette was derived from the previous hex values so the art direction is continuous:
`#FBFAF7` became the paper, `#1B1A17` the ink, `#CB4322` the accent. The one deliberate
change was the lowest-emphasis text token, which measured **3.16:1** on the paper and now
clears 4.5:1. That was the only WCAG failure in the original stylesheet.

| Role | Light | Dark | Job |
|---|---|---|---|
| `--paper` | `oklch(98.5% 0.004 85)` | `oklch(16% 0.008 85)` | page background |
| `--surface` | `oklch(100% 0 0)` | `oklch(21.5% 0.008 85)` | raised cards |
| `--surface-2` | `oklch(96.3% 0.008 85)` | `oklch(25.5% 0.009 85)` | quiet fills, the dateline |
| `--user-fill` | `oklch(95.3% 0.013 85)` | `oklch(24.5% 0.008 85)` | the reader's own words |
| `--hairline` | `oklch(90.5% 0.015 85)` | `oklch(100% 0 0 / 11%)` | borders |
| `--hairline-2` | `oklch(94.1% 0.013 85)` | `oklch(100% 0 0 / 6%)` | faintest fills, code blocks |
| `--ink` | `oklch(22% 0.01 85)` | `oklch(94% 0.005 85)` | body text |
| `--ink-2` | `oklch(38.2% 0.012 85)` | `oklch(82% 0.007 85)` | secondary reading ink |
| `--muted` | `oklch(46.1% 0.013 85)` | `oklch(69% 0.01 85)` | labels and captions |
| `--faint` | `oklch(51.5% 0.014 85)` | `oklch(65% 0.011 85)` | lowest-emphasis text |
| `--accent` | `oklch(57.2% 0.178 34.5)` | `oklch(70% 0.165 34.5)` | the rule, focus ring, primary |
| `--accent-ink` | `oklch(48.9% 0.153 34.5)` | `oklch(80% 0.135 34.5)` | accent as text |
| `--on-ink` | `oklch(98.5% 0.004 85)` | `oklch(16% 0.008 85)` | label on a solid button |
| `--ok` | `oklch(52% 0.11 155)` | `oklch(78% 0.12 155)` | status |
| `--warn` | `oklch(55% 0.13 70)` | `oklch(80% 0.12 70)` | status |
| `--bad` | `oklch(52% 0.19 27)` | `oklch(72% 0.16 27)` | status |

**Dark mode is a token swap.** Shadows are nearly invisible on a dark surface, so
elevation is expressed as a *lighter* surface. Dark borders are alpha so they composite
on any surface. Never write a second dark stylesheet.

**Every surface has a paired foreground.** That is what keeps text-on-surface contrast
correct in both themes without auditing each component.

## Typography

Be Vietnam Pro, self-hosted from `src/api/static/vendor/fonts/`. Three weights, three
subsets, plus one italic. The browser downloads only the subsets a page uses, so a
Vietnamese page pays for `latin` and `vietnamese` and never fetches `latin-ext`.

Measured transfer cost: `latin` plus `vietnamese` at 400, 600, and 700 is 99 KB, plus
33 KB if the italic is used.

**There is no variable build of this family.** The variable package does not exist, and
the three static weights are cheaper here than a comparable variable file: the Noto Sans
variable latin-ext weight-only file is 164 KB on its own.

Scale, ratio 1.25: 12 / 14 / 16 / 20 / 25 / 31 / 39 / 49. Each size carries its own line
height and tracking rather than a shared one.

| Size | Line height | Tracking |
|---|---|---|
| 12-13px | 1.4 | +0.01em |
| 14-16px | 1.5-1.6 | 0 |
| 20-24px | 1.3 | -0.01em |
| 32-48px | 1.1-1.15 | -0.02em to -0.03em |

Negative tracking on large type is the single highest-leverage detail. The measure is
34rem, set on the text element rather than the container. Tabular numerals on any date,
count, or salary. Real italics, never a synthesised slant.

## Spacing, radius, depth, motion

One spacing scale on a 4px base. An off-scale gap means the layout is wrong, not that the
gap needs a magic number. Section spacing must be larger than the internal spacing of its
contents or it turns to mush.

One base radius, `--radius: 0.5rem`, derived at 0.6, 0.8, 1, 1.4. Never mix radius
families on one surface.

Flat with borders. `1px solid var(--hairline)` on cards, inputs, and tables; shadow only
for genuinely floating things. Shadow on everything is a dated tell.

Motion: 120ms micro, 200ms standard, 320ms large surfaces. Anything past 400ms feels
broken. Animate only `transform` and `opacity`. No motion is the default and enhancement
is opt-in, with `prefers-reduced-motion` overriding both.

## Adding a token

1. Add it to `src/api/static/tokens.css`, in both themes.
2. Add its contrast pair to `scripts/check_contrast.py` in the same commit.
3. Run `uv run python scripts/check_contrast.py` and keep it green.
