# InternHunter — Tickets & Roadmap

> **Last verified:** 2026-08-12 against the active ticket plan and completion records.

> **Eviction:** A ticket plan leaves when its completion report is recorded and its historical scope
> is moved to the ticket archive.

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
| 22 | T0022 | **Docs Hygiene & Documentation System** | ✅ | Phase 1 (.1-.9) complete 2026-08-10: lint gate, front door, Decision Log, research prune · Phase 2 (.10-.14) complete 2026-08-12: prune, archive collapse, register rebuild, restructure, enforcement |
| 23 | T0023 | v1.0 Release Cut | 📋 | DoD sweep, ToS posture, tag — renumbered from T0022 on 2026-08-09 |
| — | Backlog | `is_active` honesty hedge, custom domain | 📋 | unscheduled; seeds future tickets |

> ⚠ **M11:** milestone shipped, but the T0011.5 baseline-calibration run is still **blocked** on
> maintainer credentials — see [`Known_Issues.md`](Known_Issues.md).
>
> ⚠ **M20:** complete as a coder milestone; two **maintainer** actions remain open — branch
> protection to *enforce* the CI gate, and the gated cron activation. See
> [`T0020.4_Cron_Activation_Runbook.md`](T0020.4_Cron_Activation_Runbook.md).

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

## T0022 Phase 2: Prune & Per-File Structure (T0022.10-.14) - Complete

Completed plans are preserved in [Tickets Archive](archive/Tickets_Archive.md).

| Ticket | Outcome | Plan |
|---|---|---|
| T0022.10 | Pruned obsolete documentation and the retired self-hosted stack. | [Archive](archive/Tickets_Archive.md#t002210-prune-the-dead-documentation-surface) |
| T0022.11 | Collapsed executed research records. | [Archive](archive/Tickets_Archive.md#t002211-collapse-the-executed-research-archives) |
| T0022.12 | Rebuilt the decision and issue registers. | [Archive](archive/Tickets_Archive.md#t002212-harvest-the-gaps-and-rebuild-known_issuesmd) |
| T0022.13 | Restructured the surviving documentation. | [Archive](archive/Tickets_Archive.md#t002213-restructure-the-surviving-documents) |
| T0022.14 | Enforced documentation caps, eviction, amendment, and orphan checks. | [Completion report](Completion_Reports.md#t002214-enforce-the-caps) |

### T0022.14: Enforce the caps - Complete 2026-08-12
**Objective:** Make the documentation system hold by machine rather than by good intentions.
Phase 1 wrote caps and shipped no check, so both were breached the day they were written; phase 2
has spent four tickets restoring the shape by hand. This block ships the four checks that keep it,
closing M22.

**It lands last, against a clean tree, so no check starts warn-only** - the failure mode that made
T0022.1's gate advisory for a milestone. Every check here must be **blocking on the day it merges**.

**Measured preconditions (2026-08-12):**

| Fact | Value |
|---|---|
| Capped rows in `docs/README.md` passing | **19 of 19** - the table was reconciled to measurement 2026-08-12 |
| Existing checks | 5, all blocking, all one severity: `line-length`, `link-path`, `encoding`, `agent-parity`, `stack`, plus `stamp` |
| Test suite | 20 tests in `tests/test_docs_lint.py` |
| CI | `.github/workflows/ci.yml` already runs the **full** lint and blocks - no workflow change needed |
| `amendment` as plan §7 specifies it | **20 hits outside archives, ~2 genuine** - unusable unscoped (see below) |
| `orphan` | **2 real orphans** by a link-based definition |

**In Scope:**

* **`size-cap` - and the caps come from `docs/README.md`, not the script.** Wrap the tier table in
  `<!-- caps:begin -->` / `<!-- caps:end -->` and parse the `Doc` and `Cap` columns, exactly the way
  `check_stack` parses the `deps`-marked region of `Tech_Stack.md`. Report **both directions**, as
  `stack` does: a document over its cap, *and* a tracked live document missing from the table.
  Rows reading `Uncapped` are skipped for length but still count as indexed.
  * **Rejected: a `TIER_CAPS` dict in `docs_lint.py`.** That splits one fact across two files, which
    is the exact failure the Fact Ledger exists to prevent. The register is the document; the check
    only enforces it.
  * Caps are **per-document**, not per-tier - the `Tier` column is a character label, the `Cap`
    column carries the number. Do not reintroduce a tier-to-cap lookup.
* **`eviction-rule` - the ticket's largest content job.** Every row with a numeric cap states, in
  its header, what leaves the document and when (plan §2.1 Rule A). Detect it the way `stamp`
  detects `Last verified:` - a fixed `> **Eviction:** ...` line matched by regex. That is roughly
  **15 headers to write**, and each rule must be honest and specific: *"an entry leaves when fixed,
  superseded, or reclassified"* is a rule; *"prune when large"* is not. `Known_Issues.md` already
  carries one from T0022.12 - reuse its wording pattern rather than inventing a second shape.
* **`amendment` - narrow it, or it is pure noise.** Plan §7's four phrases over the whole live
  surface produce **20 findings, of which about 2 are genuine**. `Resolved_Issues.md` alone accounts
  for 8, and every one is correct usage: describing what a fix changed is exactly what a
  closed-issue register is for. Two constraints make the check work:
  * **Scope it to T1-T3 rows of the caps table.** T4 registers are excluded by construction, and so
    are `research/**` plans, which are dated pre-design. Measured effect: **20 findings drop to 5.**
  * **Strip code spans before matching**, as `check_encoding` does. This is what lets
    `Docs_Conventions.md` document the rule without tripping it - the same self-reference trap the
    `encoding` rule hit in T0022.1, solved the same way.
  * Escape hatch `<!-- lint-allow-amendment -->` for the legitimate residue.
  * **The 5 surviving findings, pre-triaged:** `Schema_Contract.md` (*"the gate is `no longer`
    T0014"*) and `Tickets.md` (*"that state `no longer` holds"*) are the genuine article -
    **collapse them against current truth** per Rule B. `MVP_Technical_Design.md` ×2 and
    `Repo_Current_State.md` ×1 are ordinary prose about postings, HTTP status, and deleted
    branches - **mark them**.
  * **Blocking, not warning** - a deliberate departure from plan §7. The harness has one severity
    and five checks that use it; adding a severity system for a single check is the
    over-engineering CLAUDE.md §1 forbids. The marker is the pressure valve.
* **`orphan` - define it on links, not mentions.** A tracked live `.md` is an orphan when no other
  **live** document links to it by Markdown link or repo-rooted code span. Mentions from
  `archive/**` do not rescue a file - that is precisely how something stays hidden. Exempt the three
  entry points that need no inbound link: root `README.md`, `AGENTS.md`, `CLAUDE.md`.
  * **The 2 orphans this finds today**, both of which this ticket resolves:
    `evals/v1_scenario_matrix.md` (reachable only from `Completion_Reports.md` and research
    plans) and `data/vendor/README.md`
    (mentioned once, in a research table). Index each in the owning document or record why it is
    exempt - do not delete either.
* **Write Rules A and B into `Docs_Conventions.md`.** Rule A: a capped document states what leaves
  it. Rule B: correct by collapsing, never by appending - git holds the superseded version. Name the
  four trigger phrases **in code spans** so the file describing the rule does not violate it.
* **Fix the `link-path` false positive.** A backticked git branch name whose first segment matches a
  tracked top-level directory - a branch under `docs/`, for instance - is reported as a missing
  path, which is why branch names are written without backticks today. Constrain `is_repo_path`
  so a value only counts as a repo path when it plausibly is one - a file extension, or an
  existing directory.
  **This ticket's own text is the test case**: naming such a branch in backticks anywhere in
  `Tickets.md` must stop being a finding.
* **Tests.** One per new check, in both directions - a finding, and the marker or table row that
  clears it - plus a parse test for the caps table. Expect the suite to go from **20 to roughly
  30**.

**Out of Scope:**
* **A warning severity.** Decided above; the whole point of landing last is that nothing needs one.
* **Making `stamp` verify freshness.** It checks presence only, which is how `Tickets.md` carried a
  `Last verified: 2026-08-10` stamp through a rewrite that cut it from 1,381 lines to 179. A real
  gap - but comparing stamps against git mtime forces a stamp bump on every whitespace edit. Record
  it as a follow-up ticket with that trade-off stated; do not build it here.
* **`duplicate-heading`.** Deferred from phase 1 and still deferred - the four above are what this
  pass proved it needs.
* **Trimming any document to fit its cap.** The caps were set from measurement on 2026-08-12. If one
  is wrong, change the number in the table and say why in the same commit.
* **Re-tiering documents** beyond what a new check actually forces.
* **Auto-fixing amendments.** `--fix` stays a whitespace-only reflow tool. Collapsing a correction
  is a judgement call.

**Preconditions from T0022.13:** two defects found in review must land before or with this block -
`MVP_Technical_Design.md` needs a forwarding line where §7-§8 were (four references inside the file
itself now point into a void), and `Tickets.md` needs its stamp and its M22 index row brought to
current. If .13 merges without them, this ticket inherits them.

**Manual verification:**
1. `uv run python scripts/docs_lint.py` exits **0** with all ten checks active. Run it once before
   any edit so a pre-existing finding is not attributed here.
2. **Each new check fires, then clears.** Four times: add 200 lines to `Known_Issues.md` →
   `size-cap` blocks; delete an `Eviction:` line → `eviction-rule` blocks; add *"this is `no longer`
   true"* to a living doc → `amendment` blocks; add an unlinked `docs/scratch.md` → `orphan` <!-- lint-allow-link-path -->
   blocks. Revert each and confirm the lint returns to 0. **A check that cannot be made to fail
   is not enforcing anything.**
3. Change a cap number in `docs/README.md` and confirm `size-cap` immediately enforces the new value
   with no script edit - the proof the table is the source of truth.
4. Delete a row from the caps table and confirm `size-cap` reports the now-unindexed document.
5. `uv run pytest tests/test_docs_lint.py` reports **~30 passed**, none skipped. A skip means the
   gitignored `.claude/` skill copy was missed, as in T0022.10.
6. Confirm `Docs_Conventions.md` documents all four trigger phrases and that the lint stays green on
   that file - the self-reference test.
7. Write a branch name like `docs/some-branch` in backticks in a live document; `link-path` stays
   silent. Then confirm a genuinely missing `docs/` path is **still** reported - step 2's
   scratch file still needs its marker, because a suffixed path that does not exist remains a
   real finding.
8. Read three eviction rules cold and answer, for each, *"what would make me remove an entry
   tomorrow?"* If the answer is "nothing specific", the rule is decoration - rewrite it.
9. Open a PR touching only documentation and confirm CI blocks on a seeded violation, without a
   workflow edit.
10. Record the final check count, test count, and the resolution of both orphans in the completion
    report. **M22 closes with this ticket** - state the end-state numbers against plan §8.

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
  state is resolved. Render's deploy branch repoint is tracked in T0020.2 (see the **T0020**
  milestone above).
* **`is_active` agent exposure + honesty hedge** — cut from T0019 (gate unmet); re-enters only after
  T0011.5 baseline → prompt-v2 few-shot pass → the targeted recalibration delta.
* **Deploy-doc drift** (`research/archive/pre-deploy-refinement-plan.md` §6h) and a custom domain
  (cosmetic).
