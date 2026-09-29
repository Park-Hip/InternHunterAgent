# Visual avoid-list

> **Last verified:** 2026-09-27

These are defaults, not errors of taste. Each one is the high-probability centre that
unguided output converges on, which is exactly what makes it read as generated. Two of
them are *our* historical defaults, not the model's, and they were the reason the page
read as cheap despite a coherent palette.

## Typeface defaults

- **Times or Georgia as the unconsidered default.** This was the single largest visual
  cost in the original stylesheet: one system serif, no webfont, no Vietnamese-aware
  drawing. It reads as a default in the same way `Inter` does.
- **Inter as the unconsidered default.** The mirror image of the above, and the most
  common output of a model asked for a clean interface.
- A synthesised oblique where a real italic should be. The family ships italics; use them.

## Colour defaults

- Indigo or violet gradients, especially `#6366f1`. The strongest single tell.
- One hue used for everything: tinted buttons, tinted borders, tinted headings, tinted
  background. This flattens the page by destroying the accent-to-neutral ratio.
- Pure grey neutrals at zero chroma. Use a near-neutral with a warm or cool hue.
- Hex or HSL authored by hand. OKLCH, always.

## Layout defaults

- Three identical feature cards: same icon in the same rounded square, same copy length,
  same height. Real interfaces have two, four, or varied ones.
- Everything centred, including content that should be left-aligned.
- An unbounded container. A real max-width, always.
- Nested spacing that does not decrease as you go inward.

## Surface defaults

- Shadow on every element, and a uniform `rounded-2xl` at a uniform gap everywhere.
- Glassmorphism and `backdrop-blur` applied to everything rather than to an overlay.
- A hero containing a fake dashboard screenshot with a coloured glow behind it.

## Content defaults

- Emoji as UI icons. Use an icon set or, here, nothing.
- Tracked all-caps eyebrow labels used decoratively.
- `A · B · C` meta strings.
- Fade-and-slide-up on every section.
- Lorem ipsum. Real data exposes the layout failures that actually matter: a
  500-character company name, a 3,400-record count, a zero-result state.

## What reads as human

Name a specific audience and a specific job-to-be-done. State the type pairing and its
scale. Give one accent hue with its exact OKLCH value. State the max-width. Say which
elements get shadows and which do not. State the density target. State the motion budget.
State the mobile story separately.

Concrete constraints are what produce specific output. Adjectives produce the defaults
above, because an adjective is compatible with every default at once.
