# Ticket entries

One file per ticket, named for the ticket: `T0031.1.md`. A ticket branch writes exactly one
file here, on a path no other branch owns, so two agents working in parallel can never
produce a conflicting edit.

This directory is the **write surface**. The registers in `docs/` are the **read surface**,
and a ticket agent does not touch them - see the `frozen:` list in
[`../roadmap.yaml`](../roadmap.yaml). The integration step folds each entry into those
registers after the merge.

## Why the split exists

Every register that a ticket used to edit by hand was a single mutable file that every
agent had to write. Over the 200 commits before M31, `Repo_Current_State.md` changed 91
times, `Known_Issues.md` 68, and `Tickets.md` 56 - and each open branch carried an edit to
all eighteen documents under `docs/`. Those are the same lines in the same files, so the
conflicts were structural rather than accidental.

Moving the write to a per-ticket path removes the conflict class instead of asking agents
to avoid it.

## Format

A flat `key: value` frontmatter block, then `##` sections. Nested YAML is deliberately
unsupported so the file can be parsed without a dependency.

```markdown
---
ticket: T0031.1
milestone: M31
title: Give parallel tickets a private write surface
status: in-progress
date: 2026-08-16
goal: Stop every ticket from editing the same registers
verified: no
---

## Plan
Objective, in scope, out of scope.

## Summary
What changed.

## Files
Paths created, changed, or removed.

## Commands
What was run.

## Build and test
Results, as a table when there is more than one.

## Manual verification
A short checklist a developer can re-run. Set `verified: yes` once it has been run.

## Risks

## Follow-ups

## Known issues
Entries a maintainer should file into `Known_Issues.md`.

## Docs
Documents that need updating.
```

`status` is one of `complete`, `in-progress`, `next`, `planned`, `paused`. `ticket`,
`title`, `status`, and `date` are required; the rest are optional.

## Lint

Files here are exempt from the caps table and the orphan check, because a per-ticket file
has no shared index row to claim and no inbound link to earn. They still owe the
line-length, encoding, and scenario-id checks. Their path references are treated as dated
evidence, the same rule [`Completion_Reports.md`](../Completion_Reports.md) already carries.
