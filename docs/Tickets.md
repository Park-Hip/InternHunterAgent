# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-10 against the active ticket plan and completion records.

Ticket specs and delivery sequence for the MVP. Each entry is the **plan** for one ticket
(Objective / In Scope / Out of Scope); what a ticket *actually did* lives in
[`Completion_Reports.md`](Completion_Reports.md), and the current snapshot lives in
[`Repo_Current_State.md`](Repo_Current_State.md).

**Legend:** ✅ Done · 🔨 In progress · ▶ Next · ⏸ Parallel / paused · 📋 Backlog

| M | Ticket | Milestone | Status | Goal |
|---|--------|-----------|:--:|------|
| 0–5 | T0000–05 | Foundation → Hardening | ✅ | FastAPI boot, request flow, ReAct runtime, Langfuse, tracing, hardening |
| 6 | T0006 | First Real SQL Tool | ✅ | Read-only `query_clean_jobs`; answer-only API |
| 7 | T0007 | Conversation Memory | ✅ | Postgres checkpointer, session→thread, trim cap |
| 8 | T0008 | System Prompt & Persona | ✅ | Resumi persona, honesty rules, schema → config |
| 9 | T0009 | Data Ingestion (VietnamWorks) | ✅ | `raw_jobs` + `clean_jobs`, idempotent loader |
| 10 | T0010 | Pre-deploy Hardening | ✅ | Typed errors, single-table allowlist, off-loop LLM |
| 11 | T0011 | Model Evaluation Harness | ✅ ⚠ | DeepEval judge, fixture DB, 3-seam metrics, writeback |
| 12 | T0012 | Hardening & Known-Issue Fixes | ✅ | qwen leak fix, metric unblock, `trace_url`, fallbacks |
| 13 | T0013 | Pre-Deploy Refinement | ✅ | `tech_stack` rebuild, 16-col v1 schema freeze |
| 14 | T0014 | Pre-Deploy Known-Issue Fixes | ✅ | Config-load robustness, register housekeeping |
| 15 | T0015 | Agent Behavior Spec & Scenario Matrix | ⏸ | Parallel track — not on this branch |
| 16 | T0016 | Security Posture | ✅ | CORS, rate limit, input cap, `/docs` decision |
| 17 | T0017 | Streaming Response Delivery | ✅ | `astream` + no-leak filter, SSE endpoint |
| 18 | T0018 | Clickable Demo (UI + go-live) | ✅ | .1–.4 done · **live: https://internhunteragent.onrender.com** |
| 19 | T0019 | Ingestion Deploy Readiness (live-DB) | ✅ | .1–.10 done; landed on `main` via PR #29 |
| 20 | T0020 | Reconciliation & Activation | ✅ ⚠ | `main` reconciled, Render pinned to `main`, CI gate live, cron runbook — **2 maintainer actions open** |
| 21 | T0021 | Serving-Path Hardening & Honesty Baseline | 🔨 | .1 schema assertion + .2 error logging done · .3/.4 named, unscoped |
| 22 | T0022 | **Docs Hygiene & Documentation System** | ✅ | Complete 2026-08-10: lint gate, front door, Decision Log, research prune (.1-.9) |
| 23 | T0023 | v1.0 Release Cut | 📋 | DoD sweep, ToS posture, tag — renumbered from T0022 on 2026-08-09 |
| — | Backlog | `is_active` honesty hedge, custom domain | 📋 | unscheduled; seeds future tickets |

> ⚠ **M11:** milestone shipped, but the T0011.5 baseline-calibration run is still **blocked** on
> maintainer credentials — see [`Known_Issues.md`](Known_Issues.md).
>
> ⚠ **M20:** complete as a coder milestone; two **maintainer** actions remain open — branch
> protection to *enforce* the CI gate, and the gated cron activation. See
> [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md).

---

## Archived completed milestones

**Current action:** T0023 - scope the v1.0 release cut after the documentation-system milestone.

- **M0 - Foundation:** [archived ticket plan](archive/Tickets_Archive.md).
- **M1 - Runnable Request Flow:** [archived ticket plan](archive/Tickets_Archive.md).
- **M2 - ReAct Agent Runtime:** [archived ticket plan](archive/Tickets_Archive.md).
- **M3 - Self-Hosted Langfuse:** [archived ticket plan](archive/Tickets_Archive.md).
- **M4 - Tracing Integration:** [archived ticket plan](archive/Tickets_Archive.md).
- **M5 - Hardening:** [archived ticket plan](archive/Tickets_Archive.md).
- **M6 - First Real SQL Tool:** [archived ticket plan](archive/Tickets_Archive.md).
- **M7 - Conversation Memory:** [archived ticket plan](archive/Tickets_Archive.md).
- **M8 - System Prompt and Persona Refinement:** [archived ticket plan](archive/Tickets_Archive.md).
- **M9 - Data Ingestion:** [archived ticket plan](archive/Tickets_Archive.md).
- **M10 - Pre-deploy Hardening:** [archived ticket plan](archive/Tickets_Archive.md).
- **M11 - Model Evaluation Harness:** [archived ticket plan](archive/Tickets_Archive.md).
- **M12 - Hardening and Known-Issue Fixes:** [archived ticket plan](archive/Tickets_Archive.md).
- **M13 - Schema Enrichment and v1 Freeze:** [archived ticket plan](archive/Tickets_Archive.md).
- **M14 - Pre-Deploy Known-Issue Fixes:** [archived ticket plan](archive/Tickets_Archive.md).
- **M16 - Security Posture:** [archived ticket plan](archive/Tickets_Archive.md).
- **M17 - Streaming Response Delivery:** [archived ticket plan](archive/Tickets_Archive.md).
- **M18 - Clickable Demo:** [archived ticket plan](archive/Tickets_Archive.md).
- **M19 - Ingestion Deploy Readiness:** [archived ticket plan](archive/Tickets_Archive.md).
- **M20 - Reconciliation and Activation:** [archived ticket plan](archive/Tickets_Archive.md).

---

## T0015: Milestone 15 - Agent Behavior Spec & Scenario Matrix — ⏸ Parallel track
**Objective:** Define, freeze, and measure Resumi's intended per-scenario behavior against the
frozen 16-column schema — the "act the way we want" target that prompt-tuning optimizes toward and
the eval metrics grade. This is the **prompt-behavior track**, a **parallel sibling of T0014** (both
forked from the T0013.5 freeze; neither blocks the other). It lives on its own `feature/t0015.x-*`
branches and is **not present on the T0014 branch**. **Sub-tickets are indexed here, not fully
specified** (per request) — the per-ticket In/Out-of-Scope + verification live in the sub-ticket
commits and `docs/Completion_Reports.md` on the M15 branches:
* **T0015.1** — reconcile the behavior spec to the frozen 16-column schema. *(done)*
* **T0015.2** — settle the 10 open behavior decisions; freeze the scenario set + canonical phrasings
  (the `behavior_glossary`) and author `docs/Agent_Behavior_Spec.md`. *(done)*
* **T0015.3** — prompt-versioning mechanism (`prompt_version` in `config/prompts.yaml` → runtime →
  Langfuse trace metadata → eval output). *(done)*
* **T0015.4** — run the v1 scenario matrix against the `internhunter_eval` fixture DB and grade it.
  *(in progress — paused on the Groq daily token quota; 7/29 scenarios collected + graded, all 5
  collected probes FAIL — see [[groq-free-tier-quota-eval-runs]])*
* **T0015.5** — wire the `behavior_glossary` canonical strings into the prompt few-shots (few-shot
  honesty fixes for the C1–C5 probe failures). *(pending T0015.4)*

## T0021: Milestone 21 - Serving-Path Hardening & Honesty Baseline — ▶ In progress
**Scoped 2026-08-09** (authored after the fact, same pattern as T0020 — T0021.1 shipped as PR #30 on
2026-07-22 and T0021.2 was started in a worktree while this milestone lived only in
`research/v1-release-readiness-plan.md` §2 and the [[v1-release-roadmap-m20-m22]] memory note).
Where T0020 makes the *artifact* trustworthy, this milestone makes the *running service*
trustworthy: assert the schema the read path depends on, and stop the serving path from lying — to
operators via swallowed exceptions, and to users via canned messages that overstate what is known.
Runs largely parallel to T0020; both block **T0023** (v1.0 release cut — renumbered from T0022 on
2026-08-09 when docs hygiene took the T0022 slot).

> **Scoping note.** Only **T0021.2** is fully specified below — it is the slice being executed.
> **T0021.1** (read-path schema assertion) shipped ahead of its block as PR #30 and is summarized
> here for continuity, not re-scoped. **T0021.3** and **T0021.4** are named but deliberately
> unscoped; the `get_job_details` column allowlist that the research plan lists under M21 already
> landed early as **T0019.10**, so this milestone's remaining shape needs a scoping pass before
> those blocks are authored.

### T0021.1: Read-path schema assertion — ✅ **done** (PR #30, opened 2026-07-22) — *summary only,
not re-scoped*
Asserts the columns the read path depends on, so a schema drift fails loudly at startup instead of
surfacing as a canned "database error" mid-answer. Its `EXPECTED_COLUMNS` requires the 22-column
post-migration shape, which is why the PR was held until D6 stamped and upgraded Neon (signed off
2026-08-09) — both states were exercised during the D6 run, discharging its manual check C. See
`docs/T0020.4_Cron_Activation_Runbook.md`.

### T0021.2: Agent-path error logging at swallowed catch sites — ✅ Done
**Objective:** Close the three swallowed-exception sites recorded in the **Error-handling honesty
audit (2026-07-22)** in `Known_Issues.md`, so an operator can tell a one-off blip from a systemic
outage from structlog alone. Today every one of these replaces a real exception with a canned
user-facing string and logs *nothing* — the streaming path is the widest instance, since it backs
the primary chat UI and reports a DB outage, an unhandled bug, and a Langfuse crash identically as
"the demo is busy". **The log line is the load-bearing deliverable; user-facing message wording is
explicitly not in scope.**

**In Scope:**
* `src/agents/tools/query_clean_jobs.py` — `logger.error("query_clean_jobs.db_error",
  error=str(exc))` at the `except ExecutorError` catch site, so the real Postgres message carried on
  `ExecutorError` reaches structlog.
* `src/agents/tools/get_job_details.py` — the identical twin,
  `logger.error("get_job_details.db_error", error=str(exc))`.
* `src/agents/service.py` — in `stream_agent_response`'s catch-all, bind the currently-discarded
  `classify_provider_busy_error(exc)` return value and record it:
  `logger.error("stream_agent_response.failed", session_id=..., error=str(exc),
  reclassified_busy=...)`.
* Regression tests asserting each catch site logs the expected event name and carries the underlying
  cause, including the `reclassified_busy` true/false branches.
* Move the three now-resolved audit entries from `Known_Issues.md` to `Resolved_Issues.md` per the
  register convention, leaving pointers behind.

**Out of Scope:**
* **Differentiating the user-facing message by cause** — `BUSY_MESSAGE` is intentionally still
  returned for *every* streaming failure, including non-provider ones. Introducing a
  `GENERIC_ERROR_MESSAGE` is honesty/prompt work deferred to **T0021.4**; this ticket is log-only
  and changes no user-visible string.
* Logging the `validate_sql` reject branch (not a swallowed exception — nothing raised there).
* The `[MED · OPEN]` `generate_agent_response` empty/None-answer fallback signal, and the `[MED ·
  OPEN]` checkpointer pool-timeout misreport — both remain open in `Known_Issues.md`; neither is a
  discarded exception at a catch site.
* Any Langfuse/tracing-layer change, and the real `mypy [arg-type]` fix baselined by T0020.3.

## T0022: Milestone 22 - Docs Hygiene & Documentation System - Complete 2026-08-10
**Scoped 2026-08-09** from
[`research/docs-hygiene-and-system-plan.md`](../research/docs-hygiene-and-system-plan.md),
which carries the measured baseline, the full disposition of all 46 tracked `.md` files, and
the per-ticket risk notes. **Read that plan before executing any block below** — it is not
restated here.

**Why this milestone exists, and why it precedes the release cut.** The docs surface is
1.37 MB across 46 files, and it has drifted measurably: **21% of all doc lines exceed 100
characters** (worst single line: 5,424), **15 of 162** referenced repo paths no longer
resolve, 8 files appear in no index, `docs/Completion_Reports.md` carries committed mojibake
from a PowerShell round-trip, and **46 of 150 commits are docs-only** — `Repo_Current_State.md`
alone has been rewritten 66 times. The root `README.md` still describes only the T0002-era
Postgres bootstrap. Tagging v1.0 against that front door ships the weakest artifact under the
strongest label, so **the v1.0 release cut renumbers from T0022 to T0023** (decision 2026-08-09).

**The milestone is not a tidy-up.** Five of the nine tickets are cleanup; the rest install the
system that keeps it clean — a `docs_lint.py` gate in CI, a Fact Ledger assigning every fact
class exactly one owning document, and a `Decision_Log.md` that gathers ~25–35 durable
decisions out of nine executed research plans before they are archived.

> **Scoping note.** Only **T0022.1** is fully specified below — it is the slice to execute
> first, and it is deliberately first because it converts every later ticket from a subjective
> judgement into a pass/fail check. Blocks **.2–.9** are summarized for sequencing and will be
> authored as each is picked up, per the T0020/T0021 pattern. Two maintainer inputs are already
> settled: `.claude/skills/` is the canonical skill copy, and no demo screenshot exists yet
> (T0022.4 ships the sample exchange instead and is not blocked).

> **Constraint that governs the whole milestone — two agents, one repo.** This project is
> worked by **both Claude Code and Codex**. `CLAUDE.md` (Claude Code) and `AGENTS.md` (Codex)
> are byte-identical **by policy, not by accident**, and both must stay complete. Reducing
> either to a pointer degrades the other agent. Enforce parity in lint; never deduplicate.

### T0022.1: Docs lint harness + conventions + warn-only CI gate — ✅ Complete
**Objective:** Make docs hygiene machine-checkable before any doc is touched, so the eight
tickets that follow have an objective target instead of a subjective one. This ticket changes
**no existing documentation content** — it adds the checker, writes down the standard the repo
already follows in its best files (`Schema_Contract.md`, `Prompt_Playbook.md`), and wires a
**non-blocking** CI job. Blocking is deliberately deferred to T0022.9, because flipping it on
against a 3,101-line backlog would redden every unrelated PR.

**In Scope:**
* `scripts/docs_lint.py` — **stdlib only, no new dependency** (CLAUDE.md §1). Four checks in
  this ticket, chosen because each has immediate real findings:
  * `line-length` — no line >100 chars. Exemptions: table rows, fenced code, link-only lines,
    long URLs. **`docs/archive/**` is permanently excluded** (read rarely, edited never).
  * `link-path` — every backticked repo path and relative markdown link resolves, unless
    marked `<!-- archived-on-tag -->`. That escape hatch is required: several broken paths
    (`src/core/event_loop.py`, `scripts/run_scenario_matrix.py`) are *correctly* referenced <!-- archived-on-tag -->
    files preserved on archive tags, and a naive fixer would delete valid references.
  * `encoding` — valid UTF-8, no BOM, no `â€` / `Â ` / `ï»¿` / `â†` mojibake sequences. Must
    ignore matches inside backtick code spans, or honor `<!-- lint-allow-encoding -->`, so
    that docs *documenting* the hazard do not trip it.
  * `agent-parity` — `AGENTS.md` and `CLAUDE.md` are byte-identical **and both non-trivial**
    (a length floor, so neither can be reduced to a pointer and still pass).
* CLI surface: bare run executes all checks; `--check <name>` runs one; `--stat` prints the
  baseline table (file count, total bytes, lines >100, lines >200) so progress is measurable
  at any point; `--fix` safely reflows `line-length` only.
* `docs/Docs_Conventions.md` — the written standard: the 100-char wrap and its exemptions, the
  ≤5-line paragraph rule, lead-with-a-table, absolute `YYYY-MM-DD` dates, the
  `> **Last verified:**` stamp, the `<!-- archived-on-tag -->` marker, and — prominently — the
  **PowerShell hazard**: never round-trip a doc through `Get-Content`/`Set-Content`; it strips
  em-dashes and adds a BOM. This is the documented cause of the `Completion_Reports.md` damage.
* `.github/workflows/ci.yml` — a `docs` job alongside the existing ruff/mypy/pytest gate,
  running `uv run python scripts/docs_lint.py` with **`continue-on-error: true`**.
* Tests for the checker itself under `tests/`, including the two trap cases: a correctly
  archived-on-tag reference must **pass**, and a doc quoting a mojibake sequence in a code span
  must **pass**.

**Out of Scope:**
* **Fixing any finding the linter reports.** This ticket ships the instrument, not the repair —
  reflow is T0022.3, encoding and parity repair is T0022.2.
* The other four checks (`stamp`, `size-cap`, `check-stack`, `duplicate-heading`). Each depends
  on artifacts that do not exist yet — tier assignments, `Tech_Stack.md` — and lands with them.
* Making the CI job blocking (T0022.9), and any branch-protection change.
* Any external-URL link checking (slow and flaky in CI), pre-commit framework, or docs-site
  generator.

### T0022.2: Encoding repair, agent-surface parity & orphan cleanup — ✅ Complete
***T0022.1 prerequisite resolved (2026-08-10).** The corrected `encoding` check first
failed against the unrepaired report and now passes after this ticket's byte-level repair. The
check ignores intentional mojibake examples inside backticked code spans, as documented.

**In Scope:**
* **Repair `docs/Completion_Reports.md`.** 29 occurrences, concentrated in the T0019.10
  section: `—` rendered as `â€"`, `⚠️` as `âš ï¸`, `→` as `â†'`. Restore the intended
  characters. **Content is not otherwise touched** — this is a byte-level repair of an
  append-only archive, not an edit of the record.
* **Confirm `AGENTS.md` / `CLAUDE.md` parity holds** (`--check agent-parity` currently passes;
  keep it passing). Both files stay complete — see the milestone's governing constraint above.
* **Reconcile the two `SKILL.md` copies without deleting either.** See the correction below.
* **Delete `milestone/`** — a single file whose own banner declares it "**DISPOSABLE /
  temporary working doc … then this file is deleted**". Confirm its content reached
  `Full_Design_Document.md` / `MVP_Technical_Design.md` / `Tickets.md`, tag as
  `archive/milestone-scratchpad`, then remove. It also collides by filename with
  `research/archive/data-ingestion-stage.md`.
* **Fix `infra/langfuse/README.md`** — 5 lines instructing the reader to run
  `docker compose -f infra/langfuse/docker-compose.yaml up -d` against a file that does not
  exist; the folder contains only the README. The deploy uses **Langfuse Cloud Hobby**, not
  self-host (decided 2026-07-12), so the instruction is unreachable. Either restore the compose
  file or replace the README with a pointer to the Cloud decision. **Prefer the pointer** —
  reviving self-host contradicts a settled decision.
* Re-run `docs_lint.py --check encoding --check agent-parity`; both exit 0 **and the encoding
  check is demonstrably non-inert** (see manual verification).

**⚠ Correction to the 2026-08-09 answer on the skill copies — do not delete root `skills/`.**
That answer ("`.claude/skills/` is canonical, tag and delete the root copy") was given when the
only known difference was a 93-vs-94-line `SKILL.md` diff. Inspection on 2026-08-10 found
`skills/generate-ticket-prompt/agents/**openai.yaml**` — an **OpenAI/Codex agent interface
manifest** (`display_name`, `short_description`, `default_prompt` invoking
`$generate-ticket-prompt`). `.claude/skills/` has **no equivalent file**. The two trees are not
duplicates: they are the same workflow packaged for **two different agents**, exactly like
`AGENTS.md` / `CLAUDE.md`. Deleting the root tree would remove the Codex skill definition.
**Revised action:** keep both; treat `.claude/skills/…/SKILL.md` as canonical **for the shared
instruction text only**, sync the root copy's `SKILL.md` to match, and leave `openai.yaml`
untouched as Codex-only surface. Extending `agent-parity` to cover this `SKILL.md` pair is
optional and may be deferred to T0022.9.

**Out of Scope:**
* **Any reflow or rewrapping** (T0022.3), including in the files repaired here. A mojibake fix
  that also rewraps its paragraph is unreviewable — the semantic diff disappears into churn.
* **The 83 `link-path` findings.** They need a design decision first — the check currently
  scans `docs/archive/**`, which `line-length` excludes by design, and many findings are
  correct references to files preserved on archive tags needing `<!-- archived-on-tag -->`
  rather than repair. Belongs to T0022.3/.6.
* Adding the four deferred checks (`stamp`, `size-cap`, `check-stack`, `duplicate-heading`),
  and flipping CI to blocking (T0022.9).
* Any edit to the *substance* of `Completion_Reports.md` entries, and any `Known_Issues.md`
  triage beyond logging follow-ups this ticket creates.

**Manual verification** (the first check is the one that matters — an inert check passing is
indistinguishable from a clean repo, which is precisely how this defect survived T0022.1):
1. **Prove the check is live before repairing.** On the corrected patterns, run
   `docs_lint.py --check encoding` against the *unrepaired* file: it must **fail**, naming
   `docs/Completion_Reports.md` and ~29 lines. A pass here means the check is still inert —
   stop and fix the patterns, do not proceed to the repair.
2. Repair, then re-run: exits 0.
3. Open the `T0019.10` section of `Completion_Reports.md` in a markdown preview — `—`, `⚠️`
   and `→` render correctly, and no other text on those lines changed.
4. `git diff --word-diff docs/Completion_Reports.md` shows **only** character substitutions —
   no rewrapped lines, no moved prose.
5. `diff AGENTS.md CLAUDE.md` is empty and both files are ≥1000 bytes.
6. **Codex still resolves the skill:** `skills/generate-ticket-prompt/agents/openai.yaml` is
   present and unmodified, and a Codex session can still invoke `$generate-ticket-prompt`.
7. `/generate-ticket-prompt` still loads in Claude Code from `.claude/skills/`.
8. `git tag` lists `archive/milestone-scratchpad`, and `milestone/` is gone.
9. `docs_lint.py --stat` still reports 48 files minus the one deleted, and `lines >100` is
   **unchanged** from the pre-ticket baseline — proof no reflow leaked in.

### T0022.3: Structure-safe reflow of the stable docs — ✅ Complete
**Objective:** Bring the documents whose *structure no later ticket changes* to the 100-char
standard, so their diffs become line-level and reviewable. **No content change of any kind** —
this ticket rewraps bytes and nothing else. Two prerequisites make that claim verifiable
rather than hopeful: the reflower must stop destroying markdown structure, and the scope must
exclude every file another M22 ticket is about to rewrite or archive.

**Baseline (measured 2026-08-10, post-T0022.2):** `--check line-length` reports **2,357
findings across 28 files**; `--stat` reports 47 files, 3,187 lines >100, 1,561 lines >200.
`docs/archive/**` is already excluded by `is_archive()`.

**⚠ Prerequisite 1 — `--fix` corrupts markdown structure today; fix it before mass use.**
Verified 2026-08-10 by running the shipped `reflow_line_length` logic against real content.
It computes `indent` from leading whitespace only, so **every non-whitespace block marker is
lost on continuation lines**:

| Construct | Continuation line produced | Damage |
|---|---|---|
| `> **Status:** …` | `and not a ticket.` | blockquote marker `>` dropped |
| `- **Severity:** …` | `or cosmetic and omitted…` | list indent dropped to column 0 |
| `  - **Found:** …` | `  longer than expected…` | indented 2, but item content starts at 4 |
| `1. **MVP_Spec.md** …` | `technical design documents.` | ordered-list indent dropped |

All four *usually* still render, but only because CommonMark **lazy continuation** rescues
them — and lazy continuation **fails** when a wrapped line happens to begin with a token
markdown reads as a new block (`-`, `*`, `1.`, `#`, `>`). At 928 rewrapped lines the odds of
hitting that are not small, and the failure is **silent**: a paragraph quietly becomes a list
item. Teach `reflow_line_length` to detect the block prefix (`>`, `-`, `*`, `N.`) and indent
continuations to the content column, then re-verify against the four cases above.

**⚠ Prerequisite 2 — scope out the files another ticket is about to replace.** Reflowing a
file that T0022.6/.7/.8 will split, rebuild, or archive is throwaway work, and it inflates a
"no content change" diff until nobody can review it. **1,429 of the 2,357 findings (61%) are
in such files.** Each owning ticket leaves its own output conformant instead; CI stays
warn-only until T0022.9, so nothing forces zero findings before then.

**In Scope — reflow these 13 files (~928 findings):**
* `docs/Completion_Reports.md` (273) · `docs/Known_Issues.md` (270) ·
  `docs/MVP_Technical_Design.md` (151) · `docs/Resolved_Issues.md` (111) ·
  `docs/Full_Design_Document.md` (30) · `docs/MVP_Spec.md` (25) ·
  `docs/Agent_Behavior_Spec.md` (12) · `evals/v1_scenario_matrix.md` (8).
* `research/honesty-enforcement-design.md` (27) and `research/eval-cost-and-rate-limits.md` (2)
  — the two surviving research docs with findings.
* **`AGENTS.md` (9) and `CLAUDE.md` (9) — reflow both, identically, in one commit.** They are
  byte-identical by policy; rewrapping one alone breaks `--check agent-parity`. Verify with
  `diff` afterwards, not by eye.
* **`skills/…/SKILL.md` (1) and its `.claude/skills/…` twin — same trap, plus a worse one:**
  the offending line is inside **YAML frontmatter**. Wrapping a `description:` value across
  lines is invalid YAML and will break skill loading for both agents. Either leave that line
  as an explicit exemption or convert it to a YAML block scalar — **do not let `--fix` touch
  frontmatter**. Add a frontmatter guard to the reflower.
* Extend `is_archive()` to cover **`research/archive/`** as well as `docs/archive/`, so the
  9 docs T0022.8 relocates are excluded on arrival rather than needing a later pass.
* **One explicit content exception, committed separately:** `docs/Completion_Reports.md:361`
  still contains `SELECT â€¦ FROM` — residual T0022.2 mojibake that survived because it sits
  inside a code span, where `code_spans_removed()` makes the `encoding` check blind. It is 3
  codepoints; repair it here rather than knowingly reflowing around it, in its own commit with
  its own message so the reflow diff stays purely mechanical.

**Out of Scope — deferred to the ticket that owns each file (1,429 findings):**
* `docs/Tickets.md` (614) and `docs/archive/Manual_Verification_Archive.md` (293) → **T0022.6**
  splits them.
* `docs/T0020.4_Cron_Activation_Runbook.md` (130) → **T0022.5** absorbs it into `Operations.md`.
* `docs/Repo_Current_State.md` (72) → **T0022.7** rebuilds it from scratch.
* `README.md` (4) → **T0022.4** rewrites it; `docs/README.md` (2) → **T0022.9** rewrites it.
* The 9 archive-bound research docs (314 total, `research/archive/deployment-research-plan.md` 121
  and
  `research/archive/deepeval-sql-agent-eval-planning.md` 109 the largest) → **T0022.8**.
* The 83 `link-path` findings, the four deferred checks, and flipping CI to blocking (T0022.9).
* **Any wording, structure, ordering, or heading change.** If a reflowed paragraph reads badly,
  that is a finding to log — not to fix here.

**Manual verification** (check 2 is the one that matters — a reflow that changes meaning is
far worse than one that never ran):
1. Re-run the four constructs from Prerequisite 1 against the patched reflower: blockquote,
   flat bullet, nested bullet, ordered item — each continuation keeps its marker/indent.
2. **`git diff --word-diff` across every reflowed file shows only whitespace and newline
   moves — zero added or deleted words.** Any word-level change means the reflower ate content.
3. Render `MVP_Spec.md`, `Known_Issues.md` and `Agent_Behavior_Spec.md` in a markdown preview
   and confirm no paragraph became a list item and no blockquote broke mid-way.
4. `diff AGENTS.md CLAUDE.md` is empty; `--check agent-parity` exits 0.
5. `/generate-ticket-prompt` still loads in Claude Code, and
   `skills/generate-ticket-prompt/agents/openai.yaml` is untouched — frontmatter intact.
6. `--check line-length` findings drop from 2,357 to **≤1,429**, and every remaining finding is
   in a file this ticket deliberately deferred.
7. `--check encoding` exits 0 and `Completion_Reports.md:361` now reads `SELECT … FROM`.
8. `uv run pytest -q` still green — `tests/test_docs_lint.py` must cover the new prefix-aware
   reflow and the frontmatter guard.

### T0022.4: Front door — recruiter-first README + `Tech_Stack.md` — ✅ Complete
**Objective:** Fix the repo's front door and give the tech stack a single owner. The root
`README.md` still described only the T0002-era Postgres bootstrap — 50 lines that never said
what the project *is*, never linked the live demo, and would have been the first thing a
visitor read against a `v1.0.0` tag. Separately, stack facts were spread across
`pyproject.toml`, `config/settings.yaml`, `render.yaml`, `Repo_Current_State.md`, and three
research docs, with no document owning them.

**Audience decision (2026-08-09): recruiter/portfolio first.** The README is optimized for a
30-second skim by someone evaluating the author, not for someone about to run it locally, so
setup sits below the fold and operator detail belongs in `Operations.md` (T0022.5).

**In Scope — delivered:**
* **`README.md` rewritten** (120 lines, at its cap) in this order: what it is · live demo link
  above the fold · sample exchange · what is engineering-interesting (grounded answers, honesty
  as a design constraint, leak-free streaming, real ingestion, DeepEval measurement, tracing) ·
  architecture diagram · quickstart · docs map · status.
* **`docs/Tech_Stack.md` added** (112 lines) — at-a-glance table plus runtime, agent, data,
  observability, ingestion and quality sections, hosted services with the $0/mo position, and a
  **"Deliberately not used"** section recording why CORS, self-hosted Langfuse, a JS framework,
  a task queue, and `EventSource` were each rejected, so those choices stop being re-litigated.
* **`stack` check added to `scripts/docs_lint.py`** — parses `pyproject.toml` with stdlib
  `tomllib` (no new dependency) and compares **bidirectionally** against the package names in
  the tables between `<!-- deps:begin -->` / `<!-- deps:end -->`, catching both an added
  dependency that was never documented and a documented one that no longer exists.
* Five tests in `tests/test_docs_lint.py`, including one asserting the shipped `Tech_Stack.md`
  actually agrees with the real `pyproject.toml`.
* `docs/README.md` gains a `Tech_Stack.md` row so the new doc is not an orphan.

**Out of Scope:**
* `docs/Operations.md` and relocating the database-reset section — **T0022.5**. The reset
  instructions stay in the README until that doc exists, so nothing is lost in transit.
* The `stamp`, `size-cap` and `duplicate-heading` checks, and flipping CI to blocking (T0022.9).
* Any reflow beyond the two files authored here, and the 79 outstanding `link-path` findings.

**Two judgment calls worth recording:**
* **No fabricated demo figures.** Docker was unavailable, so no real query results could be
  produced. Rather than invent plausible counts, the sample exchange uses the two *behavioural*
  exchanges — the missing-posting-date refusal and the prompt-injection decline — which
  demonstrate the differentiator and need no data. It is labelled as paraphrased response
  shapes, not a transcript. Inventing statistics in a project built around not inventing data
  would undercut the claim the README is making.
* **No screenshot** (decided 2026-08-09, none available). The sample exchange lives in its own
  section so an image can slot in later without a rewrite. Logged as a follow-up.

**Manual verification:**
1. **Prove the `stack` check is not inert** — add a fake dependency to `pyproject.toml`, run
   `docs_lint.py --check stack`, confirm it **fails naming that package**, then revert.
   *(Run 2026-08-10 with `tenacity>=9.0`: reported `dependency 'tenacity' is not documented`.)*
2. `--check stack` exits 0 against the committed tree.
3. Every quickstart command resolves: `scripts/init_db.sql`, `scripts/reset_db.sql`,
   `.env.example`, `docker-compose.yml` exist; `src.api.app` and `src.services.ingestion.loader`
   import; `src/api/app.py` exposes `app`; compose publishes host port 5433. *(All confirmed.)*
4. `uv run pytest tests/test_docs_lint.py -q` green (15 passed); `ruff` and `mypy` clean.
5. **Outstanding — needs a machine with Docker:** follow the quickstart on a *clean clone* end
   to end and reach a streamed answer at `http://localhost:8000`. Note any step that required
   knowledge not on the page. This is the only check that validates the README's core promise.
6. Render `README.md` and `Tech_Stack.md` in a markdown preview — the architecture diagram and
   both tables lay out correctly, and no line wraps badly at 100 chars.

 **Follow-ups logged:** demo screenshot (the future `assets/demo.png` file) when the live demo is
 next up;
the README quickstart clean-clone run above.

### T0022.5: Operations consolidation — `docs/Operations.md` — ✅ Complete
**Objective:** Give the project's operational facts a single owner. Today "how this thing is
deployed and run" is spread across `Repo_Current_State.md`, `Completion_Reports.md` (T0018.4),
`research/archive/deployment-research-plan.md`, `render.yaml`, `.env.example`, the ingestion
workflow's
comment block, and the T0020.4 runbook — each drifting independently. Measured 2026-08-10:
**"Neon" appears in 17 live docs, `/api/v1/health` in 11, `WEB_CONCURRENCY` and "Langfuse Cloud
Hobby" in 7 each.** An operator has no single page to open, and a reader cannot tell which copy
is current.

**⚠ The T0020.4 runbook is a LIVE artifact, not history — do not fold it away.** Its §7 sign-off
table has **6 of 10 gates still unsigned**: D2 (ToS verdict), the `DATABASE_URL` +
`HEALTHCHECKS_URL` secrets, the manual `workflow_dispatch` run, re-enabling `schedule:`, the
first confirmed scheduled run, and the D10 decision. The maintainer is mid-execution against
that table. Consolidation must not disturb a partially-signed checklist, break its ordering, or
strand the sign-off state. **Merge the steady-state facts; leave the gated activation
sequence exactly where it is.**

**⚠ Boundary to settle — `Tech_Stack.md` vs `Operations.md`.** T0022.4 gave `Tech_Stack.md` a
"Hosted services" section, so both documents can plausibly claim Render/Neon/Langfuse. Left
unresolved this recreates the exact duplication the milestone exists to remove. **Decide and
record the split in the Fact Ledger:** `Tech_Stack.md` owns **what was chosen** (which service,
which tier, which version, and why not the alternative); `Operations.md` owns **how it is
operated** (env vars, deploy flow, database procedures, cron, incident response). Trim
`Tech_Stack.md`'s hosted-services table to the choice plus a link, rather than duplicating
operational detail into it.

**In Scope:**
* **Create `docs/Operations.md`** (T3 living doc, ≤200 lines, carrying a `Last verified:` stamp):
  * **Topology** — API on Render (Docker, Singapore, Free, `WEB_CONCURRENCY=1`, health check
    `/api/v1/health`, `autoDeploy` from `main` pinned by the tracked `render.yaml`), Postgres on
    Neon (PG17, Alembic head `b7e2f4a91c3d`), tracing on Langfuse Cloud Hobby (JP).
  * **Environment variables** — one table sourced from `render.yaml` + `.env.example`, marking
    for each: where it is set, whether it is secret (`sync: false`), and which surface needs it.
    Capture the two easily-missed facts: `GOOGLE_API_KEY` and `HEALTHCHECKS_URL` are
    **deliberately not declared for the web service**, and the ingestion cron's `DATABASE_URL`
    must be Neon's **direct/non-pooled** host, not the pooled one.
  * **Deploy flow** — push to `main` → Render auto-deploy; what `render.yaml` does and does not
    control (it declares secret *presence*, never values).
  * **Database operations** — init, the destructive reset path **relocated out of `README.md`**
    (T0022.4 parked it there deliberately), `alembic upgrade head`, and the current head.
  * **Ingestion cron** — current state (`schedule:` commented out, `workflow_dispatch` only),
    why it is parked, and a **pointer to the runbook** for activation. Do not restate the gates.
  * **Keep-alive / idle-pool** notes and the $0-of-$10 cost position.
* **Leave `T0020.4_Cron_Activation_Runbook.md` in place and functional**, reflowed to the 100-char
  standard (**130 line-length findings** — this ticket owns them). Add a short header note saying
  steady-state operations now live in `Operations.md` while this file remains the execution
  record until §7 is fully signed.
* **Repoint the duplicated topology statements** in live docs to `Operations.md` rather than
  restating them. Where a doc needs the fact inline, keep one sentence and link.
* Register `Operations.md` in `docs/README.md` and add its Fact Ledger row.

**Out of Scope:**
* **Signing any gate, setting any secret, or activating the cron.** This is a documentation
  ticket; the activation remains a maintainer action executed against the runbook.
* **Deleting or archiving the runbook** — that becomes possible only after §7 is fully signed,
  and is not this milestone's call.
* `docs/Repo_Current_State.md` (72 findings) → **T0022.7** rebuilds it; only its *topology
  paragraph* may be reduced to a link here.
* `research/archive/deployment-research-plan.md` (116 findings) → **T0022.8** archives it. Harvest
  its
  decisions there, not here.
* `Completion_Reports.md`'s T0018.4 entry — an append-only historical record; it keeps its
  point-in-time topology description untouched.
* Any change to `render.yaml`, the Dockerfile, the workflow, or actual infrastructure.

**Manual verification:**
1. **The runbook still works as an execution document.** Diff §7 before and after: all 10 rows
   present, same order, the 4 signed rows still signed, the 6 open rows still open. A maintainer
   resuming activation mid-way must lose nothing.
2. Every step of the old runbook that describes *steady-state* operation appears in
   `Operations.md`; every step that describes *the gated activation sequence* stayed put.
3. The env-var table matches `render.yaml` and `.env.example` line by line — including the two
   deliberately-undeclared variables and the direct-vs-pooled `DATABASE_URL` distinction.
4. Follow the relocated database-reset procedure end to end against a local Docker Postgres and
   confirm it still works after the move. *(Needs Docker.)*
5. `docs_lint.py --check line-length` findings drop by ~130; `--check link-path` gains nothing —
   run it **before and after**, since this ticket moves content between files.
6. `grep -rn "Singapore\|WEB_CONCURRENCY" docs/ --include="*.md" | grep -v archive` returns
   `Operations.md` plus links, not five independent restatements.
7. Open `Operations.md` cold and answer: *which host does the cron's `DATABASE_URL` use, and
   why?* — in under 30 seconds, without opening another file.

### T0022.6: History split - `Tickets.md` & `Manual_Verification_Guide.md` - ✅ Complete
**Objective:** The two largest live documents are mostly history. Measured 2026-08-10:
`Tickets.md` is **1,698 lines across 23 milestone sections**, `Manual_Verification_Guide.md` is
**1,503 lines across 63 ticket checklists**. Between them they carry **906 of the repo's 2,141
line-length findings (42%)**. Someone opening either file to answer *"what is left to do?"* or
*"how do I verify this change?"* must first scroll past nineteen finished milestones. Move the
finished work to `docs/archive/`; leave the live files holding open work plus an index.

**⚠ Prerequisite 1 — the keep-alive fact is stale in the very files this ticket freezes.** The
maintainer confirmed on **2026-08-10** that the cron-job.org keep-alive ping is **running**, and
`Known_Issues.md` has carried first-hand evidence of it since 2026-07-21 (an observed execution
history, a run at 07:00:13, `Failed (timeout)` at 13.37 s against a 30 s limit). Five live
statements still say it was never applied:

| Site | Stale claim |
|---|---|
| `Operations.md` § Keep-alive | "No keep-alive action is configured" — and conflates it with the ToS-blocked GitHub `keepalive-workflow` action, a different mechanism |
| `Known_Issues.md` `[MED · OPEN]` cold start | "decided 2026-07-16, not yet applied" |
| `Known_Issues.md` `[HIGH · OPEN]` 750-hour cliff | "Latent today (no ping enabled)" — the entry's own text says it flips to live-and-mitigated once enabled |
| `Repo_Current_State.md` | "written but not enabled (maintainer action)" |
| `archive/Manual_Verification_Archive.md` → `### T0019.7` Part B | outcome recorded |

Part B's open question is **already answered elsewhere**: `Known_Issues.md` records that idle
pool connections do **not** hold Neon awake — the trigger in Part C never fires. Archiving an
empty measurement template on top of a stale "not yet applied" would bury both. **Correct the
fact in `Operations.md` (its Fact Ledger owner) and write Part B's answer back before splitting.**

**The schedule to record** (maintainer-supplied 2026-08-10): cron-job.org, **`*/12 7-22 * * *`**
— 5 pings/hour × 16 h = **80/day**, matching the Part A prediction. Warm 07:00 until ~23:03
(last ping 22:48 + Render's 15-min idle timer) ≈ **16.05 h/day ≈ 498 h/month** against the
750-hour cap, so the `[HIGH · OPEN]` cliff entry becomes **live-and-mitigated**, not latent. Two
consequences the register currently gets wrong: the 07:00 ping is the **daily wake-up call**
after an ~8 h overnight sleep, so its logged timeout is structural rather than "not yet
characterized"; and a missed ping is a **24-minute gap against a 15-minute spin-down**, so a
single failure *does* spin the instance down — the claim that the next cycle recovers it does not
hold at a 12-minute interval. Confirm the job's **timezone is ICT** and its target is
`/api/v1/health` before writing either fact down.

**⚠ Prerequisite 2 — section headings disagree with the roadmap index.** The index says M19 ✅,
M20 ✅⚠, M21 🔨; the section headings say `▶ Next` (line 1082), `▶ In progress` (1227), and
`▶ In progress` (1270). A split keyed off "which milestones are done" cuts in the wrong place if
these disagree. Reconcile them first — the index is correct.

**⚠ The real link hazard is invisible to `link-path`.** There are **91 inbound references to
`Tickets.md` and 97 to `Manual_Verification_Guide.md`**, but **zero `#anchor` deep links** — so
no URL breaks. The exposure is **44 textual pointers** shaped like ``Manual_Verification_Guide.md`
→ `### T0019.7``, which name a *heading* the split relocates. `link-path` validates repo paths
only and cannot see these. Grep for them explicitly; a green lint run is not evidence here.

**In Scope:**
* **Create `docs/archive/Tickets_Archive.md`**, following the pattern
  `archive/Completion_Reports_Archive.md` already set (older milestones out, current era live).
  Move the finished milestone sections **verbatim** — this is a move, not an edit.
* **Live `Tickets.md` keeps** the header, the **full 23-row roadmap index unchanged** (it is the
  index, not history), the open milestones, the backlog, and one pointer line per archived
  milestone. Reflow the remainder to the 100-char standard.
* **Create `docs/archive/Manual_Verification_Archive.md`** for the per-ticket checklists of
  completed milestones. **Do not append them to `archive/Manual_Verification_History.md`** — that
  file states its own contract as *dated live-run logs, not steps to re-run*, and mixing reusable
  checklists into it breaks the distinction that justified the file. Two archive files, two
  content classes.
* **Live `Manual_Verification_Guide.md` keeps** the checklists for milestones still open or
  carrying unrun checks, plus a one-line-per-ticket index into the archive.
* **Rewrite the 44 textual heading pointers** to name whichever file now holds the heading.
* Update the `archive/` row in `docs/README.md` to list both new files.

**Out of Scope:**
* **Editing any ticket text or checklist step.** Archived content moves byte-for-byte. Reflow
  applies to the live remainder only — `docs/archive/**` is excluded from the standard by design
  (`is_archive()` in `scripts/docs_lint.py`), so archived lines are not reflowed on the way out.
* **Deciding whether the keep-alive ping should keep running.** Prerequisite 1 corrects the
  *record*; the cost/CU-hour decision (D7) stays with the maintainer.
* `docs/Repo_Current_State.md` (68 findings) and evicting the `RESOLVED` entries from
  `Known_Issues.md` → **T0022.7**, except for the one stale keep-alive sentence above.
* `research/**` (295 findings across 9 docs) → **T0022.8**.
* Rewriting `docs/README.md` wholesale and flipping CI to blocking → **T0022.9**.

**Manual verification:**
1. `docs_lint.py --check link-path` exits 0 **before and after** — run both, so a pre-existing
   break is not attributed to this ticket.
2. `grep -rn 'Manual_Verification_Guide\.md.*### T00' docs/ research/ --include="*.md"` — every
   surviving hit names a heading that is still in the live file.
3. Open `Tickets.md` cold: the next actionable ticket is visible within the first two screenfuls.
4. Open `Manual_Verification_Guide.md` cold and find the checklist for the most recent ticket
   without scrolling past finished milestones.
5. `git log --follow -p --stat` on the archive files shows a pure move — no content diff inside
   any relocated section.
6. `docs_lint.py --check line-length` findings drop by ~900; confirm the archived files are
   excluded rather than silently passing.
7. Re-read `Operations.md` § Keep-alive: it states that the ping is running, on which endpoint
   and window, and that the Neon idle-pool question is answered — with no reference to the
   GitHub `keepalive-workflow` action, which is a separate and still-open matter.

**Status: completed (2026-08-10).**

### T0022.7: Rebuild `Repo_Current_State.md` & true up the registers - Complete
**Objective:** After T0022.6, `Repo_Current_State.md` is **the last live `docs/` file carrying a
meaningful lint debt — 68 of the repo's remaining findings, against 2 for `docs/README.md` and
0 for everything else.** At **306 lines** it is also still a narrative rather than a fact sheet:
a reader asking *"what is true right now?"* reads three screenfuls before reaching the answer.
Rebuild it as a ≤120-line snapshot, and fix the two registers it points at, which no longer
obey their own stated rules.

**⚠ The `RESOLVED` count in the plan is stale — it is 8, not 5, and they are not one problem.**
Measured 2026-08-10. `Known_Issues.md` carries 8 entries whose headline says `RESOLVED`, in two
distinct classes that need opposite treatment:

| Class | Entries | Lines | What is actually wrong |
|---|---|---|---|
| **A — never archived** | L658 (HIGH, cron auto-activation), L799, L1160 | 53 | Genuinely resolved, still sitting in the open register. Move to `Resolved_Issues.md`. |
| **B — pointer stubs** | L417, L704, L883, L1198, L1203 | 43 | Body already lives in `Resolved_Issues.md`; these are the stubs left behind. |

Class B is the subtler defect. The file's own rule permits a stub only *"if an open item still
cross-references the resolved one"* — **L417 has zero inbound references**, so its stub has no
justification. And **L704 is 21 lines**, which is not "a short pointer" but a second copy free to
drift from the archived original. **Audit each stub for an actual inbound reference: keep it as
one or two lines if referenced, delete it if not.**

**⚠ Three entries say `RESOLVED` and must NOT be moved.** L75 `[HIGH · PARTIALLY RESOLVED]`
(schema drift), L332 `[MED · PARTIALLY RESOLVED]` (`max_jobs` ceiling), and L576
`[HIGH · MOSTLY RESOLVED]` (Render deploy repoint) are still partly open. A `grep RESOLVED`-driven
sweep evicts all three and silently closes live risks. Match on the full state token, never the
substring.

**⚠ The category index is wrong, and one whole section is missing from it.** The header lists
**7 categories totalling 78**; the file actually has **8 sections totalling 81 entries**.
**"Query service (T0019.10)" (3 entries) appears nowhere in the index**, so nothing links to it
and a reader scanning the index never learns it exists. Rebuild the counts from the file after
the moves land, not before.

**In Scope:**
* **Rebuild `docs/Repo_Current_State.md`** to **≤120 lines**, conformant to the 100-char standard
  (it currently has no `#` title — give it one), answering CLAUDE.md §6's questions in this order:
  current branch and head · completed milestones (one line each, pointing at
  `archive/Tickets_Archive.md`) · folder structure · dependencies (link `Tech_Stack.md`, do not
  restate) · scripts · build/test status · a link to `Known_Issues.md` · next recommended ticket.
* **Preserve the three things that are genuinely live**, not narrative: the **archive-tag table**
  (four tags — the branches they replaced no longer exist, so these are the only recovery
  handles), the unverified **`stash@{0}`**, and the **M15 behavior track's** partial reclamation
  (`behavior_glossary` still absent from `config/prompts.yaml`). Everything historical goes to
  `archive/Repo_State_History.md`, which already exists for exactly this.
* **Topology and operational facts become links to `Operations.md`**, not restatements — the Fact
  Ledger already assigns them there.
* **Move the 3 class-A entries** to `Resolved_Issues.md` under matching categories, preserving
  their resolution notes verbatim.
* **Resolve each class-B stub** by inbound-reference audit: shrink to a one-line pointer, or
  delete.
* **Rebuild the category index** from the file: 8 sections, correct counts, `Query service
  (T0019.10)` added.

**Out of Scope:**
* **Re-litigating whether an issue is actually resolved.** This ticket relocates entries by the
  state their own headline declares; it does not re-triage. A headline that looks wrong becomes a
  note, not an edit.
* **Rewriting `Resolved_Issues.md`'s own structure** (568 lines). Entries land under existing
  categories; if none fits, add one rather than reorganizing.
* **Auto-generating the state file from git** — named as a follow-up in the plan's §12, and
  deliberately deferred until this rebuild shows what is genuinely mechanical.
* `research/**` (295 findings across 9 docs) → **T0022.8**.
* `docs/README.md` (2 findings) and flipping CI to blocking → **T0022.9**.

**Manual verification:**
1. `Repo_Current_State.md` is **≤120 lines** and states branch, head, live URL, and next ticket
   **within the first screenful**.
2. `docs_lint.py --check line-length` drops by ~68 and reports **0 findings for `docs/`** except
   the 2 in `docs/README.md` that T0022.9 owns.
3. `grep -c "RESOLVED" docs/Known_Issues.md` returns **3** — the `PARTIALLY`/`MOSTLY` entries —
   and each is still readable as an open risk with its remaining work stated.
4. Every category count in the header matches a fresh recount, and the index lists **8** sections.
5. Each of the 3 relocated entries is findable in `Resolved_Issues.md` with its resolution note
   intact; diff the moved text to confirm it is a move, not a rewrite.
6. `docs_lint.py --check link-path` exits 0 — the rebuild drops paragraphs containing repo paths,
   so run it before and after.
7. Open `Repo_Current_State.md` cold and answer *"which branch deploys, and what is the next
   ticket?"* in under 15 seconds, without opening another file.

### T0022.8: Research prune - harvest, archive, rewrite links - Done 2026-08-10
**Objective:** `research/` is now **the entire remaining docs debt: 307 of the repo's ~310
line-length findings sit in 9 files**, every other live document having been brought conformant
by .3–.7. Nine of those plans describe milestones that have already shipped, so the *plan* is
history while the *decisions* inside it are still load-bearing — `CLAUDE.md` §1 requires reading
the relevant research doc before designing any stage. Harvest the decisions into a single
`docs/Decision_Log.md`, move the executed plans to `research/archive/` verbatim, and rewrite
every inbound reference. **Nothing is deleted.**

**⚠ The citation exposure is 209 references, not "1–6 docs each" — and lint can only see 36% of
them.** Measured 2026-08-10 across the 9 archive candidates:

| Reference form | Count | Seen by `link-path`? |
|---|---:|---|
| Path-qualified — `research/archive/deployment-research-plan.md` | 76 | **Yes** — breaks loudly on the move |
| Bare filename in prose — ``see `research/archive/deployment-research-plan.md` §1a`` | 133 | **No** — stays green while pointing nowhere |

`research/archive/deployment-research-plan.md` alone is referenced **71 times across 13 live
files**;
`research/archive/pre-deploy-refinement-plan.md` 38 times across 15. **A green `link-path` run is
not evidence
this ticket succeeded.** Sweep the bare mentions with a per-filename grep, one document at a time.

**⚠ 94 further references live inside `docs/archive/`, which the linter does not check at all**
(`is_archive()` skips those files entirely). **Decide this explicitly and record it:** archived
documents are point-in-time records, and T0022.6 already set the precedent that archived content
moves verbatim. The recommendation is to **leave them untouched and state the policy in
`research/archive/README.md`** — an archived report citing the path that was correct when it was
written is accurate history, not a broken link. What must not happen is discovering this halfway
through and rewriting archive prose by reflex.

**⚠ The harvest cannot be mechanical.** There are only **24 `**Decision` markers in all of
`research/`, and 13 of them are in one file** (`research/archive/deployment-research-plan.md`, 12 of
those dated).
Most decisions — `tech_stack` from an external vocabulary rather than a hardcoded allowlist,
same-origin static UI, `fetch()` + `ReadableStream` over `EventSource` — are recorded in prose
with no marker. Grepping the markers would miss most of the record and over-weight a single
document. **Budget a read pass per archived doc.**

**⚠ `research/README.md` indexes 11 of 14 documents and two of its descriptions are false.**
Unlisted: `eval-cost-and-rate-limits.md`, `honesty-enforcement-design.md` (both **KEEP** docs, so
nothing points a reader at them) and `research/archive/ingestion-milestone-plan.md` (an archive
candidate that no
index mentions). `research/archive/deployment-research-plan.md` is described as a *"**Skeleton**
outline … findings
to be filled in"* when it is 892 lines of completed research carrying the Render and Neon
decisions; the DeepEval entry calls T0011 *"now next"* though M11 shipped. The full rewrite is
**T0022.9**, but the three unlisted files must be resolved here — the prune decides their fate.

**In Scope:**
* **Create `docs/Decision_Log.md`** — one entry per durable decision, **≤6 lines each**, each
  stating the decision, its date, and a link to the archived source that holds the reasoning.
  Detail belongs in the archive, not here; a wall of text defeats the purpose.
* **Move 9 executed plans to `research/archive/` verbatim** —
  `research/archive/deployment-research-plan.md` (892),
  `research/archive/agent-behavior-question-bank.md` (755, never populated),
  `research/archive/deepeval-sql-agent-eval-planning.md`
  (648), `research/archive/ingestion-milestone-plan.md` (573),
  `research/archive/pre-deploy-refinement-plan.md` (595),
  `research/archive/data-ingestion-stage.md` (442), `research/archive/demo-ui-and-golive-plan.md`
  (397),
  `research/archive/streaming-implementation-plan.md` (313),
  `research/archive/schema-enrichment-plan.md` (310). **One commit per
  document**, so a bisect is cheap when a reference turns out to have been missed.
* **Keep 5 live:** `v1-release-readiness-plan.md`, `docs-hygiene-and-system-plan.md`,
  `honesty-enforcement-design.md` (its work is unbuilt), `eval-cost-and-rate-limits.md`, and
  `job-site-comparison.md` **trimmed** — collapse the never-filled rival scorecards to one line
  each, keeping the VietnamWorks column that was actually decided.
* **Fold the headline Groq/Gemini quota numbers into `Tech_Stack.md`**, leaving
  `eval-cost-and-rate-limits.md` as the derivation.
* **Rewrite all 76 path-qualified references** and **sweep the 133 bare mentions**.
* **Add `research/archive/README.md`** — why each document was archived, what superseded it, and
  the archive-link policy decided above.

**Out of Scope:**
* **Editing research content.** Archived documents move byte-for-byte; findings and dates are
  frozen. Trimming `job-site-comparison.md` is the single exception, and it removes empty stubs
  only.
* **Reflowing the 307 findings.** They leave the live surface by moving — `docs/archive/**` and
  `research/archive/**` are both lint-exempt by design. Do not reflow on the way out.
* **Deleting any research document**, including the never-populated question bank. Archive is the
  house pattern; deletion is not.
* Rewriting `research/README.md` and `docs/README.md` wholesale, and flipping CI to blocking →
  **T0022.9**.

**Manual verification:**
1. `docs_lint.py --check link-path` exits 0 **before and after**. Run it before the first move so
   a pre-existing break is not attributed to this ticket.
2. `grep -rn "<archived-doc>.md" --include="*.md" docs/ research/ README.md` for **each of the 9
   filenames** — every surviving hit either resolves to `research/archive/` or is inside
   `docs/archive/` under the stated policy. This is the check `link-path` cannot do for you.
3. `research/` contains exactly **5** live `.md` files plus `README.md`, `archive/`, and
   `experiments/`.
4. Spot-check **5 harvested decisions** against their archived sources: the `Decision_Log.md`
   entry says the same thing the original did, with the date preserved.
5. Open `Decision_Log.md` cold and answer *"why is `tech_stack` not a hardcoded allowlist?"* in
   under 30 seconds without opening another file.
6. `docs_lint.py --check line-length` drops by ~307; confirm the moved files are **excluded**
   rather than silently passing, by checking one archived file still has long lines.
7. `git log --follow -p` on one archived document shows a pure rename with no content diff.
8. Follow `CLAUDE.md` §1 as a new contributor would: pick a stage, and confirm the research it
   tells you to read is reachable in one hop from `research/README.md` or `Decision_Log.md`.

### T0022.9: Index, ledger & enforcement - Complete 2026-08-10
**Objective:** Make the standard self-enforcing and the indexes truthful. Every previous ticket
in this milestone improved a document; this one decides whether those improvements survive. The
2026-07 hygiene pass failed for exactly one reason — it had no enforcement — so the deliverable
is not a tidier file but a build that goes red when the rules are broken, and an index that
tells the truth about what is live.

**⚠ Flipping to blocking today turns every PR red — 95 findings remain.** Measured 2026-08-10:
**65 `line-length` + 30 `link-path`**. Clearing them is the bulk of this ticket; the flip is the
last commit, not the first.

**⚠ The 65 `line-length` findings were largely created by T0022.8.** Inserting the `archive/`
segment made every rewritten reference 8 characters longer, tipping previously-conformant lines
over the limit: `Completion_Reports.md` 0 → 19, `Tickets.md` 0 → 18, `Known_Issues.md`
0 → 8, `MVP_Technical_Design.md` 0 → 6, `Agent_Behavior_Spec.md` 0 → 1. Mechanical reflow under
T0022.3's rules — structure-safe, no content change, reviewed as "no semantic diff".

**⚠ The 30 `link-path` findings are six different problems. A blanket exemption would gut the
check** — and the check is the reason the milestone can claim zero drift on mechanical facts.

| Class | Count | Correct fix |
|---|---:|---|
| The hygiene plan's own §2 baseline table, which *lists broken paths as measured data* | 14 | Exempt the measured region deliberately, or accept and annotate — do not "fix" the data |
| Files preserved only on an archive tag (`event_loop.py`, `run_scenario_matrix.py`, `scenarios_v1.yaml`) | 6 | `<!-- archived-on-tag -->`, the escape hatch built for this |
| Deliberately unbuilt future files (`obligations.py`, `v2_scenario_matrix.md`, `demo.png`) | 4 | Rephrase as prose, or mark; they are plans, not references |
| Genuinely stale references (`goldens.py` under `evals/` ×3, the Langfuse infra compose file ×2) | 5 | Repoint or drop — these are real rot |
| Prose the checker mistakes for a path (a `src/core` dotted reference) | 1 | Rephrase the sentence |
| A mojibake artifact reported as `missing <?>` at plan line 528 | 1 | Encoding repair — `encoding` cannot see it inside a code span |

**⚠ This ticket cannot deliver "blocked" on its own — say so rather than overclaiming.** Flipping
`continue-on-error: true` at `.github/workflows/ci.yml:18` makes the docs job **fail**. Turning a
failing job into a *merge block* requires **branch protection, a maintainer action still open
from M20**. Until it is set, a red docs job is advisory. The completion report must state this
plainly; "the gate is live" would be the exact kind of overclaim this milestone exists to remove.

**⚠ `size-cap` as specified would fail on the day it ships.** Plan §8 caps T3 living docs at
150–200 lines. `Tickets.md` is **833** and `Known_Issues.md` **1,189** — both T3, both by design
after the splits. Shipping `size-cap` and flipping to blocking in the same ticket contradicts
itself. **Recommendation: ship `stamp` only, and drop `size-cap` and `duplicate-heading`.**
`stamp` has a real target — `Known_Issues.md` is the one T3 doc with no `Last verified:` line,
against six documents that have one. `duplicate-heading` finds nothing across living docs today.
Per CLAUDE.md §1, three checks that fire on nothing is over-engineering; one that catches a real
gap is the MVP.

**⚠ `research/README.md` was path-patched by T0022.8, not rewritten.** All nine archived plans
still sit in the live Contents table as though current; the stale descriptions survived verbatim
(`deployment-research-plan.md` is still called a *"**Skeleton** outline … findings to be filled
in"* though it carries the Render and Neon decisions, and the DeepEval row still says T0011 is
*"now next"*); `eval-cost-and-rate-limits.md` and `honesty-enforcement-design.md` are **still
unlisted** after being flagged in .8; and the sweep left every row's *display text* carrying a
full folder-qualified prefix while its link target stayed relative — the same path written two
different ways inside one table cell.

**⚠ The durability mechanism does not exist yet.** Neither `CLAUDE.md` nor `AGENTS.md` mentions
`Docs_Conventions.md` or `Decision_Log.md`. Without those pointers a future ticket inherits none
of this and the milestone decays exactly as the 2026-07 pass did. **Edit both files identically**
— `agent-parity` enforces byte-identity and will fail the build if only one is touched.

**In Scope:**
* **Clear the 65 `line-length` findings** by structure-safe reflow.
* **Resolve all 30 `link-path` findings by class**, per the table above. Each class gets a
  deliberate decision recorded in the completion report, not a silent exemption.
* **Rewrite `research/README.md`**: five live documents with accurate descriptions, a pointer to
  `archive/` and `Decision_Log.md`, and the two unlisted keep-docs registered.
* **Finish `docs/README.md`**: register `Decision_Log.md` and `Docs_Conventions.md`, add their
  Fact Ledger rows, and fix its 2 long lines. The four-tier structure and Ledger already landed.
* **Add the `Docs_Conventions.md` and `Decision_Log.md` pointers to `CLAUDE.md` §1/§6 and
  `AGENTS.md` §1/§6** — identically, in one commit.
* **Ship the `stamp` check** and give `Known_Issues.md` a `Last verified:` line.
* **Flip `continue-on-error: true` → `false`** in `.github/workflows/ci.yml`, as the final commit.

**Out of Scope:**
* **Setting branch protection.** Maintainer action, tracked under M20.
* **`size-cap` and `duplicate-heading`.** Recommended dropped above; if the maintainer wants them,
  they need caps re-derived from what the splits actually produced, as their own ticket.
* **Re-opening the tier model or Fact Ledger.** Both are settled; this ticket registers documents
  into them, it does not redesign them.
* **Content rewriting anywhere.** Reflow and index work only.
* **The v1.0 release cut** → **T0023**.

**Manual verification:**
1. `uv run python scripts/docs_lint.py` exits **0** on all checks — the milestone's definition of
   done.
2. Open a PR containing a >100-char documentation line; the docs job goes **red**. Confirm it is
   red and *not* merge-blocking, and that the report says which one it is.
3. Open a PR that edits `CLAUDE.md` without `AGENTS.md`; `agent-parity` goes red.
4. Delete a `Last verified:` line locally; `stamp` reports it. Restore.
5. Every `.md` under `docs/` and `research/` is reachable from `docs/README.md` or
   `research/README.md` — enumerate and diff against `ls`.
6. Open `research/README.md` cold: exactly **5** live documents, each description matching what
   the file actually contains today.
7. Read `CLAUDE.md` §1 as a new contributor: it points at `Decision_Log.md` first, then the
   surviving live research. Confirm `AGENTS.md` says the same thing byte-for-byte.
8. Re-run the T0022.3 review standard on the reflow commits: `git diff --word-diff` shows
   whitespace only.

## Backlog — unscheduled milestones (removed 2026-07-12; to be named & scoped) — 📋 Backlog
Removed the placeholder milestones **Deploy Hardening**, **Demo UI**, and **Ingestion Deploy
Readiness** (briefly numbered T0016–T0018) on 2026-07-12 at the user's request — they need more
specific milestone names and scoping before they re-enter the numbered roadmap. Their substance is
preserved in research and will seed the future tickets:
* **Deploy hardening** — `research/archive/pre-deploy-refinement-plan.md` §6, **minus the security
  posture
  (§6b) now carved into T0016 (Milestone 16)**. §6f (Langfuse secrets) is moot — the deploy uses
  **Langfuse Cloud Hobby**, not self-host (user decision 2026-07-12). Remaining unscheduled:
  topology (§6a), DB readiness probe (§6c), what-data-ships (§6g), deploy-doc drift (§6h), CI gate
  (§6i).
* **Demo UI** — **promoted to the numbered roadmap on 2026-07-13, then split:** the streaming
  backend became **T0017 (Milestone 17, fully scoped)** and the UI + go-live became **T0018
  (Milestone 18, fully scoped 2026-07-14; re-split 2026-07-15 into T0018.1–.4)**. See both above.
  `research/archive/pre-deploy-refinement-plan.md` §6j;
  `research/archive/demo-ui-and-golive-plan.md`.
* **Ingestion Deploy Readiness** — **promoted to the numbered roadmap on 2026-07-16 as T0019
  (Milestone 19, scoped .1–.8; extended to .10 on 2026-07-20)**. See above. It absorbed the three
  ops items previously parked here: the keep-alive ping
  (`research/archive/deployment-research-plan.md` §1a), the
  dead-man's switch (§9A), and the schema-drift assertion/migration (`Known_Issues.md` `[HIGH ·
  OPEN]`). Validation of its decisions: `research/archive/ingestion-milestone-plan.md`.

**Still unscheduled after T0019:**
* **CI merge gate** — `research/archive/pre-deploy-refinement-plan.md` §6i; no automated gate today,
  and
  Render auto-deploys straight off the active branch. Explicitly *not* part of T0019.6 (that
  workflow is ingestion-only).
* **`main` reconciliation** — ✅ done (T0020.1, PR #29 / `bcc81db`). `main` now carries the full
  M10–M19 chain and is the true head; the earlier "stuck at T0009 / M10–M19 on ticket branches"
  state no longer holds. Render's deploy branch repoint is tracked in T0020.2 (see the **T0020**
  milestone above).
* **`is_active` agent exposure + honesty hedge** — cut from T0019 (gate unmet); re-enters only after
  T0011.5 baseline → prompt-v2 few-shot pass → the targeted recalibration delta.
* **Deploy-doc drift** (`research/archive/pre-deploy-refinement-plan.md` §6h) and a custom domain
  (cosmetic).
