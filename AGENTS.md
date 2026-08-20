## 1. Operational rules

- Implement one change at a time.
- Do not implement future work, refactor unrelated systems, introduce unnecessary dependencies, or
  over-engineer the MVP.
- Keep models in `models.py` and parameters in `config/settings.yaml`.
- Before designing, planning, or implementing, read `docs/Decision_Log.md`, then the relevant
  research record beginning with `research/README.md`.
- Before changing Markdown, read `docs/Docs_Conventions.md`.
- Run focused verification and the available build or test gates before finalizing.
- Record risks and out-of-scope follow-ups in the pull request body instead of fixing them silently.

## 2. Architecture boundaries

- Keep the API layer, application service, agent runtime, and tracing layer isolated.
- FastAPI routes must not contain LangChain logic or know how the agent is built.
- Keep Langfuse and tracing concerns local to their layer.

## 3. Change workflow

Use the smallest tier that fits the change.

| Tier | Use when | Required artifact |
|---|---|---|
| Direct | A focused, low-risk edit has obvious verification | None beyond the pull request body |
| Planned | The change affects behavior, contracts, operations, or multiple files | An approved plan covering goal, files, exclusions, verification, and risks |
| Research-led | The choice is uncertain, irreversible, or needs measured evidence | Research record, decision, and approved plan |

Branch from the tip of `origin/main` and work in a dedicated git worktree.
Keep a pull request limited to one coherent change and rebase it onto `origin/main` before review.
Use the pull request template for the summary, risks, known issues, and manual verification.
For a planned change, use the tracked `skills/plan/` skill to prepare the approval artifact.

## 4. Manual verification

Every pull request includes a short manual checklist with the expected result.
Automated checks are necessary but do not replace an end-user or maintainer validation when one is
applicable.

## 5. Integration

Use the tracked `skills/integrate/` skill when merging ready pull requests or publishing derived
repository-state documentation.
