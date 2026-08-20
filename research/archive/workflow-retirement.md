# Workflow Retirement Decision Record

> **Status:** archived research, decided 2026-08-20.
> This record preserves the evidence behind D-047 after its implementation.

> **Last verified:** 2026-08-20 against PRs #84 and #85, the current CI workflow, and the main
> branch-protection configuration.

## Decision

The repository retires the ticket allocation and entry-fed documentation workflow.
Reviewed pull-request bodies, generated agent instructions, a tiered planning skill, branch
protection, and focused documentation checks are the replacement operating model.

## Evidence

[The agentic workflow](agentic-workflow.md) measured a fast PR flow whose repeated failures came
from mechanical, remembered steps and committed derived state.
It found 42 percent of sampled CI runs failing, with the advisory documentation gate as the most
common failure shape.

[Workflow simplification](workflow-simplification.md) measured documentation tooling at 89 percent
of application size and separated durable checks from coordination ceremony.
The migration preserves scenario-id, link-path, encoding, stack, and generated-instruction checks.
It removes ticket identity, frozen registers, entry rendering, and ticket-specific skills.

## Implemented controls

- `main` requires the `checks` status check before merge.
- The `docs` status check is simplified to current documentation invariants and agent-instruction
  parity.
- The scenario registry and roadmap retain their durable source-of-truth roles.
- Pull requests use a structured template that records intent, validation, risks, and manual checks.
- `CLAUDE.md` and `AGENTS.md` are generated from one source and verified in CI.

## Residual risk

The workflow is intentionally lighter, so reviewers must still evaluate scope and operational risk.
Branch protection and small deterministic checks prevent mechanical drift but cannot replace review.
