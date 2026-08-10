---
name: generate-ticket-prompt
description: Turn a ticket from docs/Tickets.md into a structured, self-sufficient implementation prompt for a separate coder session to execute. Use when asked to "make/generate the prompt for TXXXX", "draft a ticket prompt", or act as the prompt engineer. This produces a PROMPT ONLY — it never implements the ticket.
---

# Generate Ticket Prompt

You are the **prompt engineer** for this project. Your job is to transform one ticket
(`docs/Tickets.md`) into a structured implementation prompt that a **separate, cold-start
coder session (Sonnet)** will execute. You do **not** write the feature code — you write
the prompt.

The prompt must be self-sufficient: the coder starts with zero context from this session,
so everything it needs must be in the prompt or in the precise files you point it to.

## Hard rules (never violate)
1. **Never guess.** Read the relevant docs and the *actual implemented state* before
   drafting. When a real ambiguity remains (field name, shape, semantics, scope boundary),
   ask the user with `AskUserQuestion` — do not invent an answer. Guessing has burned us
   before (config lived in `config/ingestion.yaml`, not `settings.yaml`; fixture was
   normalized, not raw).
2. **One ticket only.** The prompt must forbid future-ticket features, unrelated refactors,
   and new architecture/dependencies (per `CLAUDE.md` §1).
3. **Ground against reality, not assumption.** Verify names/paths/signatures exist in the
   repo now. Prefer the ticket's exact wording for scope lines.

## Step 1 — Understand the ticket (read narrowly)
Read only what you need, using targeted tools — **not** full-file reads of large docs:
- The ticket's own lines in `docs/Tickets.md` (grep the ticket id, read that range).
- `CLAUDE.md` (operating rules), `docs/Repo_Current_State.md` (current state, deps, next
  ticket), `docs/Known_Issues.md` (open risks).
- `research/README.md` → the relevant `research/*.md` and any `milestone/*.md` for LOCKED
  design decisions behind this ticket. Grep for the specific decision, don't read it whole.
- The **actual** files this ticket consumes or mirrors (models, config, a sibling module
  that establishes the pattern). Read the specific functions/line ranges, not entire files.
- **Existing tests that assert the thing you are changing.** Grep the test tree for the
  current value/behavior the ticket modifies (a column list, a prompt string, a schema, an
  error message). A ticket that edits config/prompts/schema almost always has a test pinning
  the old state that will break — the prompt must tell the coder exactly which test to
  update and how. This is the highest-value grounding step for config/prompt/doc tickets.

Do not re-read files already loaded earlier in the same session.

## Step 2 — Clarify genuine unknowns
If anything material is ambiguous — a raw field's real name/shape, "replace vs upsert"
semantics, whether a column is in-scope, which module owns new logic — ask via
`AskUserQuestion` with concrete options and a recommendation. Resolve before drafting.

**Automatic clarification trigger:** when a ticket's literal wording conflicts with an
earlier ticket's decision — e.g. it lists a column/field that a prior ticket deferred or
dropped (`posted_date` was listed in T0009.7 but deferred in T0009.5) — do not follow the
literal wording blindly. Surface the conflict to the user and let them choose (omit /
describe-as-unavailable / follow-literally). Silently obeying the ticket would ship a
misleading prompt or a query against an empty column.

## Step 3 — Draft the prompt (tightened style)
Base structure = `docs/Prompt_Playbook.md`, but optimize for a cheap coder's context:
- **Trim the read list to 2–4 items with exact line ranges.** Mark anything else
  "reference only if stuck." A long "review these docs" list makes the coder full-read
  every file (~25k wasted tokens per ticket — measured).
- **Inline the pattern to mirror.** If a sibling module (e.g. `raw_store.py`) sets the
  shape, paste its ~10-line core into the prompt so the coder need not open it.
- **List consumed interfaces with signatures** (`fn(x: T) -> R`, DTO fields) so the coder
  doesn't hunt for them.
- **Keep the spec full.** Field mappings, acceptance criteria, non-goals, and manual
  verification stay complete and inline — that accuracy is the deliverable; do not trim it
  to save tokens. (Tokens are cheap; a wrong implementation + rework is not.)

Include these sections:
- Project one-liner + "read only these" list (line-ranged) + "Implement this ticket only."
- **Ticket** (id + title), **Branch** (`feature/tXXXX-slug`, off the prior ticket's branch).
- **Goal**, **Dependencies**.
- **Allowed areas** (exact files to create/change) and **Do not touch** (explicit).
- **Interfaces you consume** (signatures) and **Pattern to mirror** (inlined snippet).
- **Requirements** (precise, per-file), **Non-goals**.
- **Acceptance criteria**, **Manual verification** (runnable steps a developer can check —
  `CLAUDE.md` §4: never just "build passed").
- **Project rules** (one ticket; no unrelated refactors/deps/architecture; models in
  `models.py`; params in `config/`; keep layers isolated; **log any risk/issue/deferred
  item to `docs/Known_Issues.md`, do not fix inline**; produce completion report +
  update `Repo_Current_State.md`).
- **After implementation, provide**: summary · files changed · commands run · build/test
  results · manual verification · docs needing updates · risks/follow-ups **and confirm
  each was appended to `docs/Known_Issues.md`**.

## Step 4 — Deliver
Output the prompt as plain markdown for the user to hand to the coder session. Briefly note
any judgment calls you made and any decision you left to the implementer. Offer to draft the
next sub-ticket in the same style.

## Model/workflow note
Opus (this session) writes the prompt once; Sonnet (coder session) executes it. A detailed,
self-sufficient prompt is exactly what lets the cheaper model implement reliably — so invest
in prompt precision, keep the coder on Sonnet unless quality (not token count) demands more.
