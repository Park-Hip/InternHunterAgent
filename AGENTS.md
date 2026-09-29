# Agent instructions

This is the canonical cross-agent policy. `CLAUDE.md` imports this file; do not duplicate it.
Active work lives in GitHub Issues: one issue per task, and every pull request closes its issue
with `Closes #<n>`.

Active module-layer refactor documentation lives in `docs/refactor/`.
`docs/discovery/` is preserved historical evidence and does not set refactor implementation order.

## 1. Architecture boundaries

- Keep the API layer, application service, agent runtime, and tracing layer isolated.
- FastAPI routes must not contain LangChain logic or know how the agent is built.
- Keep Langfuse and tracing concerns local to their layer.
- Keep models in `models.py` and parameters in `config/settings.yaml`.

## 2. Change tiers

Use the smallest tier that fits. Planned and research-led changes need approval before code.

| Tier | Use when | Before implementing |
|---|---|---|
| Direct | A focused, low-risk edit with obvious verification | Nothing beyond the issue or request |
| Planned | Behavior, contract, operational, or multi-file change | Short proposal in the linked issue |
| Research-led | An uncertain, irreversible, or architectural choice | Evidence-backed proposal with explicit options |

For planned and research-led changes, invoke the `.agents/skills/change-proposal/SKILL.md` skill.
Branch from the tip of `origin/main` in a dedicated git worktree for anything but a trivial edit.
Keep one coherent change per pull request and rebase onto `origin/main` before review.

Parallel work is managed through standard issue tracking and PR workflows;

## 3. Verification

- Run focused checks first: the tests covering the changed paths, for example
  `uv run pytest tests/<area>`.
- For documentation changes: `uv run python scripts/docs_lint.py`.
- For any change to `src/api/static/tokens.css`: `uv run python scripts/check_contrast.py`.
- For any change to the UI under `src/api/static/`: `uv run python scripts/ui_screenshots.py`
  and read the captured PNGs back. A UI change without a screenshot review is unfinished.
- Before requesting review, run the full gate: `uv run pytest` plus available lint gates.
- After a nontrivial change, invoke the `.agents/skills/verify-change/SKILL.md` skill to select
  checks from the diff.
- Every pull request includes a manual check with an expected result when an end-user or
  maintainer validation applies.

## 4. Frontend

- The UI is static: `src/api/static/`, served by FastAPI `StaticFiles`. No SPA, no client
  framework, no build step. Do not introduce one without a Change proposal.
- Before writing any HTML or CSS, load the `frontend-design` skill
  (`/skill:frontend-design`) and read its `references/tokens.md`.
- `src/api/static/tokens.css` is the single source of truth. Never hardcode a colour,
  radius, font size, spacing value, or duration in `styles.css` or in markup; add a token
  instead, and add its contrast pair to `scripts/check_contrast.py` in the same change.
- Colour is OKLCH with semantic role names and a paired foreground per surface. Dark mode
  is a token swap under `prefers-color-scheme`, never a second stylesheet.
- Type is Be Vietnam Pro, self-hosted, because Vietnamese is a first-class language here.
  Body text is 16px or larger, `line-height` is never 1.0 near Vietnamese text, and no
  typeface is merged without verifying the glyphs `ệ ữ ỗ ặ ằ ế` render with no fallback.
- Visual defaults we do not want, enforced by the skill: Times/Georgia or Inter as an
  unconsidered default, indigo or violet gradients, one hue used for everything, three
  identical cards, everything centred, emoji as icons, glassmorphism, and shadow on
  non-floating elements.
- Accessibility floor: full keyboard operation, a visible focus ring, 4.5:1 text contrast,
  `prefers-reduced-motion` honoured, interactive targets at least 24x24px, and streaming
  text announced exactly once. Never send on Enter during an IME composition session.
- Do not redesign layout, shrink the masthead, or restructure the conversation as part of
  token or typography work. One coherent change per pull request.

## 5. Safety invariants

- Never commit secrets; production secrets are Render runtime environment variables.
- Documentation is UTF-8 without BOM; never round-trip Markdown through PowerShell
  `Get-Content`/`Set-Content`.
- Schema changes go through Alembic migrations; ingestion accumulates records instead of
  truncating clean jobs.
