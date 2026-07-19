---
name: generate-ticket-prompt
description: Turn one ticket from `docs/Tickets.md` into a grounded implementation prompt for a separate coder session. Use when asked to generate, draft, or refine a ticket prompt, especially for requests like "make the prompt for T0013" or "write the implementation prompt for this ticket." Produce the prompt only; do not implement the ticket itself.
---

# Generate Ticket Prompt

Write a self-sufficient implementation prompt for another cold-start coder session. The prompt must be accurate to the current repo, constrained to one ticket, and cheap for the implementer to follow without re-discovering the codebase.

## Workflow

### 1. Understand the ticket with targeted reads

Read only what is needed to draft the prompt.

- Find the ticket in `docs/Tickets.md` and read the smallest useful line range around it.
- Read `AGENTS.md` and `CLAUDE.md` for project rules that the implementer must follow.
- Read `research/README.md` first, then only the relevant research or milestone docs for the ticket.
- Read `docs/Repo_Current_State.md` and `docs/Known_Issues.md` if they affect scope, dependencies, current status, or follow-ups.
- Read the actual implementation files the ticket will touch. Prefer targeted reads of the relevant functions, models, config blocks, prompts, or scripts.
- Search tests for the current behavior being changed. Tickets that alter schemas, prompts, config, or persisted fields often already have assertions pinning the old state.

Use targeted search and narrow reads instead of loading large files end to end. Verify names, paths, function signatures, and config locations against the repo instead of guessing.

### 2. Resolve real ambiguity before drafting

If a material ambiguity remains, ask the user directly before writing the prompt.

Examples:

- The ticket wording conflicts with a newer research or schema decision.
- A field name or source field shape is unclear.
- The ticket appears to imply future-ticket scope.
- The owning module or update pattern is not discoverable from the repo.

Do not invent missing details. If the repo and ticket disagree, surface the conflict clearly and recommend the safest interpretation.

### 3. Draft a prompt that is strict and implementation-ready

Write the prompt in markdown. Optimize for a separate coder session that starts with no context from the current conversation.

Include these sections:

- Project one-liner.
- Read only these files:
  Use 2 to 4 exact file references with line ranges when possible. Mark anything else as reference-only if stuck.
- Ticket:
  Include the ticket id and title exactly.
- Branch:
  Recommend `feature/tXXXX-slug`, based on the prior ticket branch if the repo docs say so.
- Goal.
- Dependencies.
- Allowed areas:
  List the exact files or folders the coder is expected to edit.
- Do not touch:
  Name unrelated files, layers, or future-ticket areas that are out of scope.
- Interfaces you consume:
  Include relevant signatures, DTO fields, model attributes, or config keys so the coder does not have to hunt for them.
- Pattern to mirror:
  Inline a short sibling snippet or describe the local pattern to copy.
- Requirements:
  Make them concrete and file-specific.
- Non-goals.
- Acceptance criteria.
- Manual verification:
  Provide runnable checks, not vague statements like "tests pass."
- Project rules:
  Restate the local constraints that matter most:
  one ticket only; no unrelated refactors; no unnecessary dependencies; models live in `models.py`; parameters belong in `config/settings.yaml`; read `research/` before design; keep layer boundaries intact; log risks and deferred work separately instead of fixing them inline.
- After implementation, provide:
  summary of changes; files changed; commands run; build and test results; manual verification steps; risks; follow-up tickets; docs needing updates; completion report expectations; `Repo_Current_State.md` update expectations when the ticket requires it.

### 4. Keep the prompt grounded in current repo reality

Prefer precise repo facts over generic advice.

- Mirror existing file names and patterns exactly.
- Call out the specific test files likely to fail or need updates.
- Preserve known semantics from the repo and research notes instead of silently "simplifying" them.
- If a value is source-derived or nullable today, keep that truth visible in the prompt.
- If a date field should be treated as a date, describe date-safe behavior rather than text matching.

### 5. Deliver only the prompt plus minimal notes

Output the implementation prompt as plain markdown for the user to hand to another coder session.

After the prompt, optionally add a short note covering:

- judgment calls you made while drafting,
- open decisions you intentionally left to the user,
- any repo ambiguity that should be resolved before implementation.

Do not implement the ticket. Do not add extra roadmap ideas, future-ticket work, or speculative architecture.
