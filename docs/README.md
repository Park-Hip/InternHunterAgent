# Documentation Map

This is the index for InternHunterAgent's docs. Each document answers a different question and stays in its lane; this map says which doc owns what, so nothing gets restated (and drifts) across files.

## Where to find what

| Concern | Document | Altitude |
|---|---|---|
| What the MVP must do, and why (product capabilities, expectations) | `MVP_Spec.md` | Product / capability |
| Permanent system laws & layer boundaries (what's always true) | `Full_Design_Document.md` | Constitution |
| How the MVP realizes those laws (components, interfaces, decisions) | `MVP_Technical_Design.md` | Build blueprint |
| What gets built in what order (tickets, sequencing) | `Tickets.md` | Sequencing |
| Current branch, completed work, folder structure, known issues | `Repo_Current_State.md` | Snapshot (now) |
| Manual steps to verify a change works | `Manual_Verification_Guide.md` | Verification |
| Prompt design and conventions | `Prompt_Playbook.md` | Reference |

## The rule that keeps these separate

The test for where a piece of content belongs:

- If it describes **what is permanently true** about the system → `Full_Design_Document.md`.
- If it describes **what the product should do or feel like** → `MVP_Spec.md`.
- If it describes **how a capability is built** (components, mechanisms, contracts) → `MVP_Technical_Design.md`.
- If it describes **what a specific ticket does** or **what is true right now** → `Tickets.md` or `Repo_Current_State.md`.

A document should *reference* another rather than copy from it. Duplicated content is how the docs drift apart.

## Suggested reading order

1. **`MVP_Spec.md`** — understand what the product is for.
2. **`Full_Design_Document.md`** — learn the permanent laws and boundaries.
3. **`MVP_Technical_Design.md`** — see how the MVP is actually built.
4. **`Repo_Current_State.md`** — find out where the work stands today.
5. **`Tickets.md`** — pick up the next piece of work.
