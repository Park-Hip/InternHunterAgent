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
| [Ingestion gate register](ingestion-gate-register.md) | Retired; see ADR-0058 | Maintainers and implementers |
| [ADR-0060](../decisions/adr-0060-retire-the-agent-v0-bundle.md) | Why the v0 bundle was retired and the legacy SQL query path serves permanently, including the accepted false-success risk | Maintainers and implementers |

The six `docs/refactor/agent-v0-*` records this workspace used to own - the v0 baseline, behavior
and metric contract, legacy rule disposition, scenario disposition, SQL decision, and cutover - are
superseded by ADR-0060 and retired from the working tree. They described a bundle that no longer
exists, so keeping them with a status would leave a second, stale specification of what the agent
may claim. Their content remains on git at `ca4eb9a`, and ADR-0060 names what each one decided.

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

That list bounds this workspace, not the project. Ingestion scope is set by [ADR-0058](../decisions/adr-0058-single-source-mvp-ingestion.md): VietnamWorks is the only source, authorized by [ADR-0034](../decisions/adr-0034-vietnamworks-robots-and-terms-gate.md). A second source needs its own approved decision record.

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
A third is no longer answerable from this workspace, and that is the intended consequence of
ADR-0060: there is no longer a separate contract for what the agent may claim. The agent has one
query path, so the rules that govern a number live in the code that produces it - the validator, the
obligations layer, and the evaluation gate - and
[ADR-0060](../decisions/adr-0060-retire-the-agent-v0-bundle.md)
names the false-success risks that path accepts and the gate that must replace the retired one.
