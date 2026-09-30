# Refactor charter

> **Last verified:** 2026-09-25
>
> **Eviction:** This charter is replaced when the current module-layer refactor is complete or a later
> approved charter explicitly supersedes it.

## Purpose

This workspace is the concise source of truth for the in-place module-layer refactor of the current
`src/` application.
It helps a maintainer identify the current layers, explain their intended dependency direction, and
select the next approved boundary without consulting the legacy discovery collection.

## Authority and audience

| Record | Owns | Reader |
| --- | --- | --- |
| This charter | Refactor scope, authority, and operating rules | Maintainers and implementers |
| [Target layer and dependency map](target-layer-dependency-map.md) | Intended layers, dependency direction, and known gaps | Maintainers and implementers |
| [Component index](component-index.md) | Current component groups, refactor state, and immediate next action | Maintainers and implementers |
| [Active backlog](active-backlog.md) | Ordered next decisions and vertical slices | Maintainers and implementers |
| [Ingestion gate register](ingestion-gate-register.md) | Live per-source gate state, required maintainer actions, and the deferral register | Maintainers and implementers |
| [Agent v0 evaluation baseline](agent-v0-baseline.md) | Measured agent and evaluation baseline, v1 retention, and open decisions for the agent-v0 track | Maintainers and implementers |
| [Agent v0 behavior and metric contract](agent-v0-contract.md) | The active v0 specification of what the agent may claim, and how each number is computed | Maintainers and implementers |
| [Agent v0 legacy rule disposition](agent-v0-legacy-rules.md) | The auditable map from the legacy `G01` to `G47` expectations to the v0 contract | Maintainers and implementers |
| [Agent v0 scenario disposition](agent-v0-scenario-disposition.md) | The audit trail from the 50 v1 evaluation scenarios to the 16 v0 acceptance cases, and the behaviors nothing covers yet | Maintainers and implementers |
| [Agent v0 SQL decision](agent-v0-sql-decision.md) | The Stage 4 go/no-go on exploratory SQL, its measurement, and the admission policy a future path would need | Maintainers and implementers |

`docs/discovery/` is retained as historical, source-backed discovery evidence.
It does not set implementation order or create an architecture decision unless an approved record in
this workspace explicitly adopts it.

## Outcomes

1. The existing `src/` tree remains the application being improved.
2. The intended dependency direction is API transport to application service to agent/runtime and
   domain ports.
3. Infrastructure and tracing are replaceable adapters behind explicit boundaries.
4. Each technical change is an in-place, approved vertical slice with characterization evidence when
   compatibility matters.
5. Public HTTP, SSE, browser, data, provider, and operational behavior remains uncommitted until the
   relevant slice states its compatibility boundary.

## Constraints

This reset authorizes documentation only.
It does not authorize a replacement application, a parallel product, a `src/` rewrite, data
collection, schema work, provider changes, deployment changes, or deletion of legacy material.

That list bounds this workspace, not the project.
Data collection and schema work are authorized only by an approved record in `docs/decisions/`
together with a met row in the
[ingestion gate register](ingestion-gate-register.md), and never by this workspace.
The register authorizes no collection today beyond the VietnamWorks automated-access row, which is
itself bounded by [ADR-0034](../decisions/adr-0034-vietnamworks-robots-and-terms-gate.md).

A technical slice requires its own approved issue before implementation.
That issue must name the affected boundary, source-backed current behavior, compatibility decision,
characterization evidence, verification, and rollback path.

## Operating rules

- Keep these records short and current.
- Record durable architecture decisions in `docs/decisions/` when they meet that bar.
- Move completed, declined, or superseded backlog entries out of the active list rather than growing
  a second inventory.
- Create a focused issue when a new concern is discovered instead of expanding an approved slice.

## Maintainer check

A maintainer should be able to explain the dependency direction and choose the next boundary in two
minutes using this workspace alone.
The expected explanation is: API transport invokes an application service, which depends on
agent/runtime and domain ports, while infrastructure and tracing remain replaceable adapters.
A second question is now answerable from the same place: whether a given source may be
collected from, and against which named gates.
A third is answerable too: what the agent is allowed to claim about a posting, and which number
answers which question, from the
[v0 contract](agent-v0-contract.md) alone.
