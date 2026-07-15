# Documentation Map

This is the index for InternHunterAgent's docs. Each document answers a different question
and stays in its lane; this map says which doc owns what, so nothing gets restated (and
drifts) across files.

## Canonical docs (the sources of truth)

| Concern | Document | Altitude |
|---|---|---|
| What the MVP must do, and why (product capabilities, expectations) | `MVP_Spec.md` | Product / capability |
| Permanent system laws & layer boundaries (what's always true) | `Full_Design_Document.md` | Constitution |
| How the MVP realizes those laws (components, interfaces, decisions) | `MVP_Technical_Design.md` | Build blueprint |
| What gets built in what order (ticket specs, sequencing) | `Tickets.md` | Sequencing |

## Living / operational docs (state that changes as work lands)

| Concern | Document |
|---|---|
| Current branch, completed work, folder structure, next ticket (a *now* snapshot) | `Repo_Current_State.md` |
| Per-ticket outcome records — files changed, tests, follow-ups (append-only archive) | `Completion_Reports.md` |
| **Open** issues, risks, and out-of-scope follow-ups (living register) | `Known_Issues.md` |
| **Resolved** issues, kept for the record (closed archive) | `Resolved_Issues.md` |
| Manual steps a developer runs to verify a change works | `Manual_Verification_Guide.md` |
| Superseded content moved out of the live docs — old state snapshots & build logs, pre-M16 completion reports, dated live-run verification logs, and one-off review artifacts | `archive/` |

## Reference docs (stable, look-up-as-needed)

| Concern | Document |
|---|---|
| Prompt design and conventions | `Prompt_Playbook.md` |
| The frozen v1 `clean_jobs` column contract | `Schema_Contract.md` |

> Teaching walkthroughs (e.g. the SSE/streaming beginner's guide) live outside `docs/`
> in the top-level [`guides/`](../guides/) folder — they explain concepts rather than
> record project state.

## Review artifacts (archived — findings already migrated into the registers)

The one-off review passes — `archive/Code_Review_Notes.md`,
`archive/Claude_Code_Review_Skeleton.md`, and
`archive/Documentation_Hygiene_Review_T0016.md` — now live under `archive/`. Their
actionable findings were migrated into `Known_Issues.md` (open) / `Resolved_Issues.md`
(closed); the files are kept only as the original evidence.

## The rule that keeps these separate

The test for where a piece of content belongs:

- If it describes **what is permanently true** about the system → `Full_Design_Document.md`.
- If it describes **what the product should do or feel like** → `MVP_Spec.md`.
- If it describes **how a capability is built** (components, mechanisms, contracts) → `MVP_Technical_Design.md`.
- If it describes **what a ticket should do** → `Tickets.md`; **what a ticket actually did** → `Completion_Reports.md`.
- If it describes **what is true right now** → `Repo_Current_State.md`.
- If it is an **open risk/bug** → `Known_Issues.md`; once fixed, it moves to `Resolved_Issues.md`.

A document should *reference* another rather than copy from it. Duplicated content is how
the docs drift apart.

## Suggested reading order

1. **`MVP_Spec.md`** — understand what the product is for.
2. **`Full_Design_Document.md`** — learn the permanent laws and boundaries.
3. **`MVP_Technical_Design.md`** — see how the MVP is actually built.
4. **`Repo_Current_State.md`** — find out where the work stands today.
5. **`Tickets.md`** — pick up the next piece of work.
