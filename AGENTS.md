# Agent instructions

This is the canonical cross-agent policy. `CLAUDE.md` imports this file; do not duplicate it.
Active work lives in GitHub Issues: one issue per task, and every pull request closes its issue
with `Closes #<n>`.

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

## 3. Verification

- Run focused checks first: the tests covering the changed paths, for example
  `uv run pytest tests/<area>`.
- For documentation changes: `uv run python scripts/docs_lint.py` and
  `python scripts/docs_build.py --check`.
- Before requesting review, run the full gate: `uv run pytest` plus available lint gates.
- After a nontrivial change, invoke the `.agents/skills/verify-change/SKILL.md` skill to select
  checks from the diff.
- Every pull request includes a manual check with an expected result when an end-user or
  maintainer validation applies.

## 4. Safety invariants

- Never commit secrets; production secrets are Render runtime environment variables.
- Documentation is UTF-8 without BOM; never round-trip Markdown through PowerShell
  `Get-Content`/`Set-Content`.
- Schema changes go through Alembic migrations; ingestion accumulates records instead of
  truncating clean jobs.
