# Contributing

This repository is maintained agent-first: most changes are made by coding agents under the rules
in [`AGENTS.md`](AGENTS.md), reviewed and merged by a human.
This page is the human-facing contract for any contributor.

## How work is tracked

GitHub Issues are the only backlog.
One issue per task; every pull request closes its issue with `Closes #<n>`.
Use the issue templates:

- **Bug report** - a defect in behavior, documentation, or operations.
- **Change proposal** - substantial, contract-affecting, or uncertain changes need approval before
  code. Planned changes propose in the issue; research-led changes add linked evidence.
- **Operational follow-up** - risks discovered while doing other work. Record them instead of
  fixing silently inside an unrelated change.

## Making a change

1. Branch from the tip of `origin/main` in a dedicated git worktree.
2. Keep one coherent change per pull request; rebase onto `origin/main` before review.
3. Respect the architecture boundaries in
   [`docs/architecture.md`](docs/architecture.md) — the API layer never imports LangChain, the
   request path never imports ingestion or evaluation packages, tracing stays in its layer.
4. Keep models in `models.py` and parameters in `config/settings.yaml`; schema changes go through
   Alembic migrations.

## Test matrix

Run focused tests first (`uv run pytest tests/<area>`), then the full gate before requesting
review.

| Layer | What it proves | Where |
|---|---|---|
| Unit | Deterministic internals: SQL validator safety cases, table formatter, result serialization | `tests/` |
| Tool path | Query tool end to end with the model stubbed: success path and validator refusal path | `tests/` |
| Request integration | Answer-only happy path and clean failure paths; under streaming, the leak test | `tests/api/`, `tests/agents/` |
| Memory behavior | Multi-turn refinement, session isolation, generated session id, restart persistence, history cap | `tests/agents/runtime/test_memory.py` |
| Evaluation harness | Behavioral quality under model non-determinism, against the seeded fixture database | `evals/`, `tests/evals/` |

The bar: every MVP capability maps to at least one observable test.
Deterministic capability tests live here; model-behavior quality is measured by the evaluation
harness, not asserts.

Fixture-backed tests need Postgres on host port 5433 (`docker compose up -d postgres`); they skip
otherwise.

## Documentation

Documentation claims are checked where they can be machine-checked:

```bash
uv run python scripts/docs_lint.py
```

Follow [`docs/Docs_Conventions.md`](docs/Docs_Conventions.md) when writing Markdown.
Every behavioral change asks: which documented claim does this make true or false? State it in the
pull request's *Docs impact* section.

## Pull requests

The PR template requires: summary with `Closes #`, automated verification results, one manual check
with expected result, risks, docs impact, and known issues.
CI must pass before review.
