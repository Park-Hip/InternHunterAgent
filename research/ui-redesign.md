# UI Research: making the InternHunter web UI credible

> **Eviction:** This record leaves `research/` when the stack decision in finding 4 and the
> token system in finding 2 are both decided in issues, at which point the surviving content is
> harvested into `docs/` or into the issue bodies and this record is archived.
>
> **Last verified:** 2026-09-27

## Summary

The current page is not the usual AI-generated slop. It has genuine art direction - a warm
paper palette, one restrained vermilion accent, hairline rules, a 34rem measure, a skip link.
What it lacks is a token system, a real typeface, a dark theme, and designed interaction states.
The problem is visual craft plus accessibility, not architecture, which makes it fixable inside
`Planned` and `Direct` change tiers rather than a research-led re-platform.

Three findings drive the rest:

1. The largest single "ugly" factor is `styles.css:26` - `Times New Roman` as the only typeface -
   which is a default in exactly the way `Inter` is a default for model-written UI. The 2026
   diagnosis of generic agent UI is *distributional convergence*; the remedy is identical, namely
   pinned numeric values instead of adjectives.
2. A dataset-bounded agent is judged on honesty before beauty. The current page has no design
   for the tool trace, for citations, or for the "no data" outcome, which are the three states
   this product actually lives or dies by.
3. Streaming token-by-token into a `role="log"` live region is unusable with a screen reader, and
   there is still no W3C normative technique for it. It must be engineered and hand-verified.

## Method

- Six parallel researcher agents, one per angle: chat/agent UX, frontend stack, design system
  and visual craft, agent skills, design-to-code tooling, and accessibility/performance/security.
  Each returned a cited brief with an explicit kept/dropped source ledger and a gaps section.
- One direct read of the working tree: `src/api/static/index.html`, `src/api/static/styles.css`,
  `AGENTS.md`, and the skill conventions under `.agents/skills/`.
- One direct read of the Pi harness documentation for skills, extensions, custom tools,
  `promptGuidelines`, and `before_agent_start`, so the harness recommendations match the real API
  rather than a generic agent description.
- Screenshots of the running page captured read-only through Playwright at 1440x1000 and
  390x900, plus a target mock rendered in the proposed token system at 1440x1020 light, 1440x1020
  dark, and 390x860, so current and target could be compared as images rather than prose.

## Measurement

| Observation | Measurement |
|---|---|
| Display typeface | `styles.css:26` resolves to Times New Roman, then Georgia |
| Body type | `styles.css:45` is 1.0625rem with line-height 1.7 in a serif stack |
| Theme support | `styles.css:10` declares light theme only; no `prefers-color-scheme` |
| Token layer | 11 ad-hoc hex values at `styles.css:12`–`28`, no OKLCH, no paired foreground |
| Lowest-contrast text | `--faint: #928D83` on `--paper: #FBFAF7` at `styles.css:21` is about 3.4:1, under the 4.5:1 AA floor for the captions it carries |
| Reading column | `--measure: 34rem` inside a `max-width: 43rem` sheet, leaving roughly half of a 1440px viewport empty |
| Interaction surface | `index.html:40`–`49` is a bare `<input type="text">` plus `<button>`; no Stop control, no per-turn actions, no designed empty or error state |
| Perceived performance floors | LCP <= 2500ms, INP <= 200ms, CLS <= 0.1, TTFB <= 800ms at p75; no Long Animation Frame above 50ms |
| Conformance target | WCAG 2.2 Level AA is a W3C Recommendation; WCAG 3.0 remains a Working Draft, so 3.0 conformance must not be claimed |

## Findings

### 1. The current page has six concrete, fixable problems

| # | Problem | Evidence | Consequence |
|---|---|---|---|
| 1 | System serif as the only typeface | `styles.css:26` | Reads as an unconsidered default; the largest single visual cost |
| 2 | No Vietnamese type system | `styles.css:45` | Stacked diacritics need more headroom than Latin; no subset, no `ccmp`, no NFC normalisation |
| 3 | Light theme only | `styles.css:10` | Half of dark-mode users get a white slab |
| 4 | Ad-hoc hex values, no semantic role layer | `src/api/static/styles.css:12` | Every new component and the dark theme become manual decisions |
| 5 | Native input and button, no interaction states | `src/api/static/index.html:40` | No cancel path on a 40-second database search; no designed failure states |
| 6 | Contrast and streaming region unguarded | `styles.css:21` | Fails AA on captions; no reserved height, so streaming risks layout shift and unusable announcements |

### 2. The visual system worth copying in 2026

**Colour.** Author in OKLCH, not HSL: HSL lightness is not perceptual, so equal lightness steps
look equally bright across hues when they do not, which makes ramps underivable. Tailwind v4's
entire default palette is already OKLCH, so there is no reason to write hex in 2026. Copy the
Radix 12-step role assignment, because components must reference roles rather than step numbers:
1 app background, 2 subtle background, 3 component background, 4 hover, 5 active, 6 subtle
border, 7 interactive border, 8 strong border and focus ring, 9 solid background, 10 solid
hover, 11 low-contrast text, 12 high-contrast text. On top of that, the shadcn semantic layer,
where **every surface token has a paired foreground** so text-on-surface contrast holds in both
themes without auditing each component. Dark mode then becomes a token swap, and dark borders
are expressed as alpha so they composite on any surface.

**Accent discipline.** One accent, three jobs: primary action, one focus ring, one data series.
Tinting buttons, borders, headings, and backgrounds all with the same hue reads flat because it
destroys the accent-to-neutral ratio that carries hierarchy. Neutrals should be *near* neutral,
chroma around 0.01 at a warm or cool hue; zero chroma looks like a screenshot of a design.

**Typography.** A modular scale, 1.25 for editorial work, paired with a per-size line height and
tracking rather than a shared one: 12–13px at 1.4 with +0.01em, 14–16px at 1.5–1.6, 20–24px at
1.3 with −0.01em, 32–48px at 1.1–1.15 with −0.02em to −0.03em. Negative tracking on large type is
the single highest-leverage detail. Set the measure on the text element at about 65ch, not on the
container. Use tabular numerals for any salary, count, or date column, because proportional
digits visibly jitter in columns.

**Vietnamese is the hard constraint.** Vietnamese stacks a circumflex and a tone mark above the
base letter, as in `ệ ữ ỗ ặ ằ`, and needs roughly 1.4 to 1.6 times the Latin headroom at the
same size. So body text stays at 16px or above, `line-height: 1.0` is never used near Vietnamese
text, text is NFC-normalised server-side, and the glyph test string is rendered before a family
is adopted. Confirmed Vietnamese coverage: Be Vietnam Pro, Noto Sans, Noto Serif, Inter.
Shortlist but **unverified**: Geist, Instrument Sans, Instrument Serif, Fraunces, Bricolage
Grotesque, Atkinson Hyperlegible. Self-host through Fontsource rather than a Google Fonts CDN
link, which is a third party on the critical path, a GDPR exposure, and a source of layout shift.

**Depth.** Flat with borders beats card with shadow in 2026; shadow on every element is a dated
tell. Use `1px solid var(--line)` on cards, inputs, and tables, and reserve shadow for genuinely
floating surfaces: popovers, modals, toasts, dragged elements. Dark mode needs its own elevation
model, because shadows are nearly invisible on dark and elevation is expressed as a *lighter*
surface.

**Motion.** 100–150ms for micro-interactions, 150–250ms standard, 300–400ms only for large
surfaces, and anything beyond 400ms feels broken. Animate only `transform` and `opacity`. View
Transitions are Baseline as progressive enhancement. Honour `prefers-reduced-motion`, and make
no motion the default with enhancement opt-in.

**The avoid list.** Indigo and violet gradients, `#6366f1`; Inter *or* Times/Georgia as an
unconsidered default; three identical feature cards; everything centered; emoji as UI icons;
glassmorphism everywhere; a hero with a fake dashboard and a glow; uniform shadow and uniform
radius on everything; shadow on non-floating elements; tracked ALL-CAPS eyebrows; `A · B · C`
meta strings; fade-and-slide-up on every section.

### 3. The agent UX contract for a dataset-bounded assistant

Ranked. The first seven are release blockers for trust, not polish.

1. **Four-state stream machine with a real Stop.** `submitted | streaming | ready | error`.
   Spinner on `submitted`, Stop on `submitted|streaming`, submit disabled unless `ready`. Stop is
   an `AbortController` on the stream reader. A long database search that cannot be cancelled is
   a dead end.
2. **Throttle re-renders.** Re-parse markdown at roughly 20–30fps rather than per stream frame.
   Naive token delivery ignores human reading speed and wastes compute.
3. **Citations inline, deep-linked, with real payloads.** The strongest finding in the source
   material is that users rarely click citations, so placement rather than trust drives
   verification. Place each source beside the sentence it supports, deep-link to the exact
   supporting text, never label one "Source", and never synthesise a URL the backend did not
   return.
4. **Sanitise markdown on every render pass.** Allowlist tags and attributes, forbid
   model-supplied image sources, validate citation URLs server-side against own snapshot IDs, and
   never pass raw model text to `innerHTML`. OWASP treats model output as injectable.
5. **Tool calls as collapsed cards, never prose.** Show filters, row count, and duration. Never
   render raw chain-of-thought, and never first-person narration such as "Mình đã tìm kiếm và
   nhận thấy": the source material warns these rationalisations are frequently unfaithful and
   *increase* over-trust.
6. **"No data" as a first-class styled state.** Show what was searched, including filters, date
   range, and snapshot size, why it may be empty, and two or three reformulations. The same card
   component serves zero results and tool error, differing only in icon and copy.
7. **Vietnamese-correct composer.** Auto-growing textarea, Enter to send and Shift+Enter for a
   newline, but never send while an IME composition session is active, which is a real bug class
   for Vietnamese input.

Then: per-turn copy, regenerate, and edit-resend actions; scroll anchoring only when the user is
already at the bottom, with a jump-to-latest pill otherwise; buffering of incomplete markdown so
an unclosed bold marker does not render as raw syntax mid-stream; progressive disclosure for
tabular answers, one card per posting; and the scope of the dataset stated in the first message
with limitations placed near the composer rather than in a footer.

The five failures to design against are anthropomorphic reasoning prose, a disclaimer buried in
a footer, a fake typewriter with no Stop and no states, hallucinated or bare-list citations that
give false reliability, and treating "no data" as prose while ignoring corpus staleness.

### 4. Stack options, and the recommendation

| Option | Upside | Cost | Maintenance |
|---|---|---|---|
| A. OKLCH token system, no build | No new runtime, no Docker change, strict CSP is easier without a build | Focus management is hand-rolled; no component registry | Low |
| B. Vite + React 19 + Tailwind v4 + shadcn/ui | Best-in-class a11y primitives; shadcn ships an official skill and MCP server | Node build stage per deploy, React commitment for a Python shop | Medium |
| C. htmx + Jinja fragments | FastAPI-native, no client state | Streaming markdown is awkward; recent major version transition | Low to medium |
| D. AI chat libraries | Fastest route to polished streaming UX | Node 22+; none stream into a Python-owned endpoint without a proxy | High |

**Recommendation: start with A, keep B as the upgrade path.** The stack researcher recommended
B. For this project A is the better first move, because the reported problem is visual craft
rather than architecture, so A keeps the change inside the `Planned` and `Direct` tiers while B
would be research-led. Revisit B when a component registry or multi-view surfaces are needed.

Two constraints reinforce A. Serving self-hosted assets means a strict CSP is *easier* without a
build step: `script-src 'self'`, no inline script, no `unsafe-inline`, and DOMPurify owning
sanitisation. And a hash-based policy is the right shape for a static page, where nonces would
force per-response plumbing and split dev from prod policy.

If B is adopted later, the install is a `npm create vite` template, `tailwindcss` plus
`@tailwindcss/vite`, then `shadcn init` followed by the specific components needed. Tailwind v4
is CSS-first and needs no `tailwind.config.js`, which is less configuration than v3, not more.
Note that shadcn made Base UI its default in July 2026 while keeping Radix supported behind a
flag, and that Vercel's AI Elements registry is mid-rewrite from React to SolidJS, so verify
before depending on it.

### 5. The non-negotiable quality bar

**Target WCAG 2.2 Level AA.** The two new AA criteria that bite a chat interface are 2.4.11
Focus Not Obscured, where an auto-growing thinking bubble must not cover the focused input, and
2.5.8 Target Size minimum of 24x24 CSS pixels for send, stop, and copy controls.

**The streaming live-region recipe.** Token-by-token mutation of a `role="log"` live region
queues and drops announcements and is unusable with a screen reader. No W3C normative technique
exists, so this is community consensus and must be hand-verified:

1. Put `role="log" aria-live="polite" aria-relevant="additions text"` in the initial
   server-rendered HTML, not injected later.
2. Set `aria-busy="true"` before streaming starts.
3. Stream tokens into an `aria-hidden="true"` visual node, which screen readers ignore.
4. On completion, write the final text exactly once to a static visually-hidden node, then set
   `aria-busy="false"`, producing exactly one announcement.

Keep focus in the textarea on send rather than stealing it, expose a skip link to the new answer
on the first assistant turn, use `role="status"` for progress and `role="alert"` only for real
errors, and never auto-scroll a reduced-motion user.

**Performance.** LCP <= 2500ms, INP <= 200ms, CLS <= 0.1, TTFB <= 800ms at p75, and no Long
Animation Frame above 50ms. Time-to-first-token and completion latency are *custom* metrics,
because streaming shifts perceived performance off the Core Web Vitals set; the static shell is
what must satisfy LCP and CLS, which means reserving height for the growing log and never
injecting above the fold on token arrival.

**Security.** Sanitise after every pass and do not widen DOMPurify's defaults, because the
maintainers document bypasses arriving through added tags and attributes. Force
`rel="noopener noreferrer"` on links via a sanitiser hook. Use a hash-based strict CSP:
`default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src
'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`.

**Test scope for a small team.** Keep one Playwright smoke test of the full streaming flow, one
axe test asserting zero critical violations, unit tests for the sanitiser configuration and the
link hook, and two or three visual snapshots of idle, streaming, and error. Skip unit tests of
the markdown sanitiser internals, exhaustive browser matrices, markup validation of generated
output, and axe on every page of a single-page app. Manually, once per release: a keyboard-only
pass, and NVDA with Firefox plus VoiceOver with Safari **specifically on the streaming flow** to
confirm exactly one announcement per completed answer.

### 6. Workflow, tools, and reference sites

**The workflow that holds up in 2026**, ordered by leverage per unit of cost: gather five to
eight real screenshots from comparable products; write the design as tokens in a committed file
before any markup; build against real data from the first commit, designing the empty, loading,
and error states first because they are most of a small app's screens; separate art direction
from coding into two passes, planning colours, type roles, and an ASCII wireframe and critiquing
that plan before building; build components in the repository rather than in a design tool; give
the agent eyes through a browser automation server; have a human review screenshots and write
critiques as text; then lock it down in continuous integration.

The sharpest methodological point: the mainstream browser-automation server is
*accessibility-snapshot-first, not vision-first*, and its own documentation positions it as
avoiding screenshots and visually-tuned models. The reliable loop is snapshot, assert, fix.
Screenshots are for human aesthetic judgement, not for the agent to optimise against, because an
agent that can diff pixels will ship a layout that looks right at one viewport, breaks on a long
name, and is unreadable to a screen reader.

**Tools.** Adopt now: the Playwright MCP server as the agent's eyes, Playwright visual
snapshots, axe-core, and Lighthouse CI. Adopt if the stack becomes option B: Tailwind v4's
CSS-first theme layer, the shadcn skill and MCP server, and its registry. Skip for now: a design
token interchange pipeline, a design-tool MCP server, and a component workshop with hosted
visual review, because one page with about ten components does not justify any of them. Use the
one-shot prompt-to-app generators for exploration only; they are excellent for three candidate
directions in ten minutes and poor as the codebase you own. Never put a model-judged design
review agent in the merge path, because it cannot judge taste and fails on false positives.

**Websites for judging quality**: Land-book, Godly, Awwwards, Minimal Gallery, curated.design,
Layers.to, Mobbin, Refero, SaaSFrame, Pageflows, and Brutalist.design. Use them to calibrate -
find three references that look right, then extract their type pairing, spacing scale, and
accent - not to copy. **Websites for specs rather than vibes**: the Tailwind theme reference,
shadcn theming, the Radix scale documentation, W3C WCAG 2.2, the ARIA Authoring Practices Guide,
the web.dev vitals documentation, the Nielsen Norman Group articles on explainable AI and AI
chatbot design, Fontsource, and the Agent Skills specification.

### 7. Agents need skills for this, and the harness can enforce them

**Yes, and the mechanism is documented rather than folklore.** The stated root cause of generic
model-written UI is distributional convergence: models sample the high-probability centre of
training data, so unguided output converges on one typeface, one accent, and one card shape. The
published fix is steering, and a before/after study shows a short art-direction prompt measurably
changes landing pages, blog layouts, and dashboards. Skills are the delivery mechanism, because
they solve context loading - metadata always present, instructions loaded on relevance, reference
files on demand - while the explicit don't-list and pinned tokens solve taste. The canonical
public artifact is a `frontend-design` skill whose structure is persona framing, grounding
designs in the subject matter, typography guidance with an anti-tell list, a calibration list of
current default looks, a two-pass workflow, restraint rules, screenshot review, and a quality
floor. Authoring rules are prescriptive: keep the skill body under 500 lines, keep the
description under 1024 characters because it is the only text matched during selection, add a
table of contents to reference files over 100 lines, and build three evaluations before writing
the document.

**In this harness specifically**, the enforceable surfaces are:

1. Always-on rules in `AGENTS.md`, which is loaded as a context file, for the don't-list and the
   accessibility floor.
2. A project skill under `.agents/skills/`, matching the convention already used by
   `change-proposal`, `verify-change`, and `deepeval`, with the detailed values in bundled
   reference files so only the description is always in context.
3. Forcing the load with an explicit slash command, because the harness documentation is explicit
   that models do not always load a matching skill on their own and that the command should be
   used to force it.
4. A screenshot review loop, which this harness supports natively because the read tool accepts
   images: capture the page with a browser automation tool, then read the image so the model
   actually sees the rendered result. This repository already has Playwright output under
   `.playwright-cli/`, so the loop is half-built.
5. A project-local extension registering a custom tool with prompt guidelines, whose bullets are
   appended to the system prompt while the tool is active. Each bullet must name the tool,
   because the bullets are appended flat with no tool prefix.
6. A `before_agent_start` hook that injects the review obligation on UI-shaped prompts, with
   access to the structured prompt options so the injection can depend on real project state.
7. A `tool_call` hook acting as a design linter, able to block or warn on a hex literal outside
   the token file, on `!important`, or on a font outside the approved stack. The hook can block a
   call and tool input is mutable, so arguments can be patched before execution.
8. Extending the existing `verify-change` skill with the accessibility, Lighthouse, and visual
   snapshot gates, rather than inventing a second verification policy.
9. Registering extra skill paths from an extension so third-party skills stay out of the tree.
10. Authoring discipline: a small body, a specific description, and evaluations written first.

## Proposed issue sequence

| Order | Issue | Tier | Depends on |
|---|---|---|---|
| 1st | Guardrails: the frontend skill, the `AGENTS.md` section, and screenshot review inside `verify-change` | Direct | Nothing |
| 1st | Automated gates: axe, Lighthouse CI, visual snapshots | Direct | Nothing |
| 2nd | Stack decision, and freeze the type pairing and accent value | Research-led | Nothing, but most later work depends on it |
| 3rd | Token system, and raise the lowest-contrast text token to pass AA | Planned | Stack decision |
| 3rd | Self-hosted variable font with a Vietnamese subset | Planned | Stack decision |
| 4th | Stream state machine, Stop, throttled re-render, markdown buffering | Planned | Token system |
| 4th | Trust surface: tool cards, inline citations, no-data state, staleness badge | Planned | Token system |
| 4th | Accessibility release blockers: the live-region recipe, focus management, target size, reduced motion | Planned | Ships alongside the two above |

## Gaps and confidence

**High confidence, primary sourced.** WCAG 2.2 versus 3.0 status and the new AA criteria; the Core
Web Vitals thresholds including INP at 200ms since 12 March 2024; the live-region streaming
recipe as consensus, pending hand verification; Tailwind v4 theme semantics and its OKLCH
palette; the shadcn paired-foreground contract and radius derivation; the Radix 12-step role
table; View Transitions Baseline status; the canonical skill structure and its size budget; and
the accessibility-first design of the mainstream browser-automation server.

**Verify before pinning.** Search providers were rate-limited during part of the run, so these
rest on a single retrieval: the current Tailwind minor, the shadcn Base-UI default status, the
recent htmx major, the Storybook 10 line, the AI SDK 7 release, and the Alpine 3.15 line. All
pricing for design tools, visual-review services, and generators is unverified and must not be
budgeted from this record.

**Explicitly unverified.** Vietnamese glyph coverage for Geist, Instrument Sans, Instrument
Serif, Fraunces, Bricolage Grotesque, and Atkinson Hyperlegible. The avoid list is synthesised
from framework defaults and observed model output rather than from one named essay. No
controlled study was found isolating the effect of a repository rules file on UI output quality,
and none isolating sentence-batched versus token streaming for comprehension - the
quality-of-experience literature optimises time-to-first-token and inter-token smoothness rather
than chunk granularity.

## Source ledger

**Kept, load-bearing.** W3C WCAG 2.2 and the WCAG 3.0 working draft; the ARIA Authoring
Practices Guide feed pattern and the ARIA23 technique for role log; the web.dev vitals, TTFB, and
strict-CSP documentation; the Tailwind theme-variable reference; shadcn theming; the Radix scale
composition page; the Nielsen Norman Group articles on explainable AI in chat interfaces and on
AI chatbot design guidelines; the Vercel AI SDK chatbot documentation; assistant-ui's tool-fall
back contract; the OpenAI Apps SDK UI guidelines; Anthropic's write-up on improving frontend
design through skills, its `frontend-design` skill, and its skill-authoring best practices; the
agents.md convention; the Playwright MCP documentation, visual-comparison documentation, and
accessibility-testing documentation; the DOMPurify threat model; the OWASP improper-output-handling
guidance; and Fontsource's Vietnamese subset listing.

**Dropped, with reason.** Colour-converter explainer pages, because Tailwind's own OKLCH palette
is stronger primary evidence for the same claim. Vendor posts restating Lighthouse thresholds.
Affiliate pricing listicles for design tools. A cited "Nielsen 15% gain" statistic whose number
does not survive inspection. Community forks of the canonical skill, which are unverified
derivatives of the primary artifact.

<!-- lint-allow-link-path:begin -->

## Appendix: proposed file layout

The following paths do not exist yet and are listed as proposals, not references.

```text
src/api/static/app.js                      streaming + live-region contract
src/api/static/tokens.css                  the token source of truth
.agents/skills/frontend-design/SKILL.md    the on-demand skill
.agents/skills/frontend-design/references/tokens.md
.agents/skills/frontend-design/references/antipatterns.md
.agents/skills/frontend-design/references/a11y.md
.agents/skills/frontend-design/assets/tokens.css
tests/ui/chat.spec.ts                      the only UI test suite to maintain
lighthouserc.cjs                           performance budgets
```

<!-- lint-allow-link-path:end -->
