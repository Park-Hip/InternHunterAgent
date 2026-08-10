# Docs Hygiene & Documentation System — M22 Plan

> **Status:** Pre-design plan (research / pre-design). Authored **2026-08-09** against `main`
> @ `a5ff82e` + `37b5169`. Every number in §2 was **measured**, not estimated; the commands
> are given so they can be re-run as the progress metric. Nothing here is built yet — this
> plan graduates into `docs/Tickets.md` as **M22** once approved.
>
> **Scope:** the whole documentation surface (46 tracked `.md` files), not `docs/` alone.
> **Feeds:** `docs/Tickets.md` (T0022.x), `docs/README.md`, and a new `docs/Docs_Conventions.md`.

---

## 0. TL;DR — the nine moves

| # | Move | Why it matters |
|---|---|---|
| 1 | **Set a line-length + shape standard** and reflow the live docs | 21% of all doc lines exceed 100 chars; the worst single line is 5,424 chars |
| 2 | **Rewrite the root `README.md`** | The repo's front door still describes only a T0002-era Postgres bootstrap |
| 3 | **Add `docs/Tech_Stack.md`** | No doc answers "what is this built with" — the stack is scattered across 5 files |
| 4 | **Add `docs/Operations.md`** | Deploy topology is restated in 4 places and drifts independently |
| 5 | **Split archive out of living docs** | `Tickets.md` / `Manual_Verification_Guide.md` are ~90% history by volume |
| 6 | **Prune `research/` from 14 docs to 5** | 9 are executed plans (~4,900 lines) whose milestones already shipped |
| 7 | **Add `docs/Decision_Log.md`** | **The "one place"** — every durable decision in ≤6 lines, harvested before archiving |
| 8 | **Write `scripts/docs_lint.py` + wire it into CI** | Turns hygiene from a recurring chore into an enforced invariant |
| 9 | **Publish a Fact Ledger (one fact, one owner)** | The root cause of drift: no doc formally owns any given fact |

Moves 1–7 are the cleanup and consolidation. **Moves 8–9 are what stop the mess from coming
back** — without them this plan is a one-off tidy that decays within a month, exactly as the
2026-07 hygiene pass (`docs/archive/Documentation_Hygiene_Review_T0016.md`) did.

> **Two agents, one repo.** This project is worked by **both Claude Code and Codex**.
> `AGENTS.md` (Codex) and `CLAUDE.md` (Claude Code) must both stay complete — they are
> byte-identical *by policy*, not by accident, and the plan enforces that in lint rather than
> collapsing either one. See **§2.4.1**.

### Decisions locked 2026-08-09

| Decision | Choice | Detail |
|---|---|---|
| Milestone placement | **M22 = Docs Hygiene**; v1.0 release cut → **M23** | §9.0 |
| Reflow scope | **T1/T2/T3 + `research/**` + 3 named files**; `docs/archive/**` excluded | §5.2.1 |
| Root README audience | **Recruiter / portfolio first**; setup below the fold | §6.2 |

---

## 1. Why now

Three forces converge:

- **The v1.0 release cut is next.** `research/v1-release-readiness-plan.md` §2 lists "docs
  conformance" as one line of M22's DoD. That framing badly under-scopes the work: a
  portfolio project that tags v1.0 with a front-door README describing a database bootstrap
  is shipping its worst artifact first. This plan argues docs hygiene should *become* M22 and
  the release cut should shift to M23 (see §9.0).
- **Doc maintenance is now a third of all commits.** 46 of 150 commits touch only `.md`
  files. `Repo_Current_State.md` alone has been rewritten across 66 commits.
- **The repo just went quiet.** One branch, no open PRs, nothing in progress. This is the
  cheapest moment to restructure docs — no in-flight branch will conflict.

---

## 2. Baseline audit — measured 2026-08-09

### 2.1 Inventory

| Metric | Value |
|---|---|
| Tracked `.md` files | **46** |
| Total size | **1,432,013 bytes (1.37 MB)** |
| Total lines | **14,503** |
| Lines longer than 100 chars | **3,101 (21.4%)** |
| Lines longer than 200 chars | **1,553 (10.7%)** |

Reproduce:

```bash
git ls-files '*.md' | xargs wc -c | tail -1
git ls-files '*.md' | xargs awk 'length($0)>100' | wc -l
```

### 2.2 The readability defect, quantified

This is the user-visible complaint — "long chunk of texts" — and it has an exact shape:
**no hard-wrap discipline.** A paragraph is one physical line, so diffs are unreadable, and
so is the prose.

| File | Longest line | Lines >200 chars | Bytes/line |
|---|---:|---:|---:|
| `docs/archive/Repo_State_History.md` | **5,424** | 55 | 164 |
| `evals/v1_scenario_matrix.md` | **4,231** | 31 | **497** |
| `docs/Repo_Current_State.md` | **2,790** | 55 | 140 |
| `docs/MVP_Technical_Design.md` | 1,990 | 126 | 155 |
| `docs/Tickets.md` | 1,577 | **327** | 149 |
| `docs/Known_Issues.md` | 1,510 | 176 | 221 |
| `docs/Completion_Reports.md` | 1,446 | 194 | **290** |
| `docs/Manual_Verification_Guide.md` | 785 | 132 | 74 |

**The key insight: this repo already knows how to wrap.** `docs/README.md` (max 189),
`docs/Prompt_Playbook.md` (88), `docs/Schema_Contract.md` (93), and
`guides/Streaming_And_SSE_Explained.md` (156) are all well-formed. The standard exists
implicitly in the best files — it was simply never written down or enforced. **We are
propagating an internal convention, not importing an external one.**

### 2.3 Drift, measured

**15 of 162** file paths referenced in docs no longer resolve (**9.3%**):

| Broken reference | Verdict |
|---|---|
| `docs/Code_Review_Notes.md` | **Stale** — moved to `docs/archive/`; 4 docs still point at the old path |
| `infra/langfuse/docker-compose.yaml` | **Stale** — `infra/langfuse/` contains only a 5-line README |
| `scripts/init_clean_jobs.sql` | **Stale** — actual file is `scripts/init_db.sql` |
| `src/services/query/schema_context.py`, `obligations.py` | **Stale** — never existed / renamed |
| `src/core/event_loop.py`, `scripts/run_scenario_matrix.py`, `evals/scenarios_v1.yaml`, `evals/test_scenarios_v1_load.py` | **Legitimately archived-on-tag** — must be *annotated*, not "fixed" |
| `evals/goldens.py`, `evals/v2_scenario_matrix.md`, `tests/services/query/test_schema_context.py` | Needs case-by-case triage |
| `config/ingestion`, `src/core.db`, `docs/rename-t0013-schema-freeze` | Prose fragments caught by the matcher — mostly false positives, confirm and ignore |

The archived-on-tag cases are important: a naive link-fixer would delete correct references.
The lint rule in §8 therefore needs an explicit **`<!-- archived-on-tag -->`** escape hatch.

**Index drift — 8 files exist but appear in no index:**

| Unlisted file | Should appear in |
|---|---|
| `docs/Agent_Behavior_Spec.md` | `docs/README.md` |
| `docs/T0020.4_Cron_Activation_Runbook.md` | `docs/README.md` |
| `research/eval-cost-and-rate-limits.md` | `research/README.md` |
| `research/honesty-enforcement-design.md` | `research/README.md` |
| `research/ingestion-milestone-plan.md` | `research/README.md` |
| `research/experiments/*.md` (3 files) | `research/README.md` |

**Content drift in `research/README.md`** — it describes `deployment-research-plan.md` as a
"**Skeleton** … findings to be filled in" (the file is now 892 lines / 71 KB, fully
populated) and calls the DeepEval evaluation milestone "**now next**" (M11 shipped; the repo
is at M21).

### 2.4 Duplication and orphans

| Finding | Evidence |
|---|---|
| **`AGENTS.md` and `CLAUDE.md` are byte-identical** | Both exactly 2,778 bytes; `diff` returns clean. **This is intentional, not a defect** — see §2.4.1 |
| **The ticket-prompt skill exists twice and has diverged** | `skills/generate-ticket-prompt/SKILL.md` (93 lines) vs `.claude/skills/…` (94 lines) — `diff` shows a full-file rewrite |
| **`milestone/` is a self-declared temporary folder that was never deleted** | Its own banner: "**DISPOSABLE / temporary working doc** … then this file is deleted" |
| **Filename collision** | `milestone/data-ingestion-stage.md` vs `research/data-ingestion-stage.md` — different content, same name |
| **Orphan README** | `infra/langfuse/README.md` — 5 lines, points to a nonexistent compose file |

### 2.4.1 Two agents, two instruction files — a constraint, not a duplicate

**This project is worked by both Claude Code and Codex.** Each reads a different instruction
file by convention:

| File | Read by | Status |
|---|---|---|
| `CLAUDE.md` | Claude Code | Must stay complete |
| `AGENTS.md` | **Codex** | Must stay complete |

`skills/generate-ticket-prompt/SKILL.md` line 17 confirms the intent — it instructs the
implementer to *"read `AGENTS.md` **and** `CLAUDE.md` for project rules."*

**Correcting an earlier read of this audit:** the byte-identical pair initially looks like
duplication to collapse, and the obvious move — reduce `AGENTS.md` to a pointer at
`CLAUDE.md` — **would degrade Codex**, which expects its rules in the file it reads, not one
hop away. The duplication is load-bearing.

**The fix is not deduplication, it is enforced parity:** keep both files complete, and add a
lint check that fails when they diverge (§8, `agent-parity`). That converts a silent drift
risk into a build error while both agents keep working. The same treatment applies to the two
`SKILL.md` copies once the maintainer names the canonical one.

### 2.5 Encoding damage — active, and it will recur

`docs/Completion_Reports.md` contains **mojibake**: the T0019.10 section renders `—` as
`â€"`, `⚠️` as `âš ï¸`, and `→` as `â†'`. This is a UTF-8 file decoded as cp1252 and
re-saved — the signature of a PowerShell `Get-Content` / `Set-Content` round-trip.

No BOMs are currently present. **This is a live hazard, not just damage to repair:** any
future PowerShell-based doc edit reintroduces it. The lint rule in §8 must fail the build on
mojibake byte sequences, and `docs/Docs_Conventions.md` must state the rule plainly:
**never round-trip a doc through PowerShell text cmdlets.**

### 2.6 Churn — the maintenance-cost argument

| Doc | Commits touching it |
|---|---:|
| `docs/Repo_Current_State.md` | **66** |
| `docs/Known_Issues.md` | 53 |
| `docs/Manual_Verification_Guide.md` | 50 |
| `docs/Tickets.md` | 34 |
| `docs/Completion_Reports.md` | 24 |

`Repo_Current_State.md` is rewritten roughly every other commit because it is *narrative* —
prose paragraphs restating milestone summaries that `Completion_Reports.md` already owns.
Every fact stated in two places doubles the update cost and halves the odds both stay true.

### 2.7 `research/` audit — 14 docs, 5,900 lines, mostly executed

`research/` is the second-largest doc surface and the messiest. Each file was written to
*precede* a milestone; nine of those milestones have since shipped, so the plan is now
history while the decisions inside it are still load-bearing.

| Doc | Lines | State | Verdict |
|---|---:|---|---|
| `v1-release-readiness-plan.md` | 343 | **Live** — scopes M20–M23 | **KEEP** |
| `docs-hygiene-and-system-plan.md` | 626 | **Live** — this plan | **KEEP** |
| `honesty-enforcement-design.md` | 479 | **Live** — "No implementation"; the honesty work is unbuilt | **KEEP** |
| `eval-cost-and-rate-limits.md` | 124 | Reference — Groq/Gemini quota facts still true | **KEEP** (fold headline numbers into `Tech_Stack.md`) |
| `job-site-comparison.md` | 528 | Scorecard; VietnamWorks decided, rivals are stubs | **KEEP, TRIM** — collapse unfilled stubs to one line |
| `data-ingestion-stage.md` | 442 | Banner: *"shipped tickets twice"* (T0009, T0019) | **ARCHIVE** |
| `deployment-research-plan.md` | 892 | Deploy shipped (T0018.4); **8 unfilled placeholders** | **ARCHIVE** |
| `deepeval-sql-agent-eval-planning.md` | 648 | M11 shipped | **ARCHIVE** (§11 grounding → Decision Log) |
| `ingestion-milestone-plan.md` | 573 | Banner: *"Graduated 2026-07-16"* → T0019 | **ARCHIVE** |
| `pre-deploy-refinement-plan.md` | 595 | Brainstorm; consumed by M16–M19 | **ARCHIVE** |
| `demo-ui-and-golive-plan.md` | 397 | T0018 shipped | **ARCHIVE** |
| `streaming-implementation-plan.md` | 313 | T0017 shipped | **ARCHIVE** |
| `schema-enrichment-plan.md` | 310 | M13 shipped; superseded by `Schema_Contract.md` | **ARCHIVE** |
| `agent-behavior-question-bank.md` | 755 | **Stub, never populated** — ~48 question groups, no answers; M15 track parked | **ARCHIVE** — revive only if the behavior track restarts |

**Net: 4 keep, 1 keep-and-trim, 9 archive — about 4,900 lines leaving the live surface.**

#### The constraint that rules out plain deletion

> **Every single research doc is cited by 1–6 live docs.** Measured:
> `data-ingestion-stage.md` ×6, `deployment-research-plan.md` ×6, `job-site-comparison.md` ×4,
> `streaming-implementation-plan.md` ×4, `ingestion-milestone-plan.md` ×4,
> `pre-deploy-refinement-plan.md` ×4, `deepeval-sql-agent-eval-planning.md` ×4 …

Deleting any of them breaks live references — and `CLAUDE.md` §1 *requires* reading the
relevant `research/` doc before designing any stage, so a dangling pointer is a real
workflow break, not a cosmetic one. **"Delete the unneeded ones" must therefore take a safe
form:**

1. **Extract** the durable decisions into `docs/Decision_Log.md` (§6.6) — this is the
   "gather it into one place" move.
2. **Move** the full record to `research/archive/`, unchanged.
3. **Rewrite** every inbound link, verified by the `link-path` check.

Nothing is lost, the live surface shrinks by ~4,900 lines, and the *reason* behind each
decision becomes findable in one file instead of buried in a 900-line plan.

---

## 3. Goals and non-goals

### Goals

| G | Goal | Done when |
|---|---|---|
| G1 | **Human-readable core docs** | No living doc has a line >100 chars; core docs lead with a summary table or bulleted answer, not a prose block |
| G2 | **One fact, one owner** | The Fact Ledger (§5.3) is published, and no fact class has two owning docs |
| G3 | **Gather scattered facts into one place** | Tech stack, operations/deploy, conventions, and **decision rationale** each have exactly one home |
| G3b | **Prune the live doc surface** | `research/` holds 5 live docs, not 14; ~4,900 lines move to `research/archive/` with zero broken links |
| G3c | **Both agents keep working** | `AGENTS.md` (Codex) and `CLAUDE.md` (Claude Code) stay complete and identical, enforced by lint |
| G4 | **Zero drift on mechanical claims** | `docs_lint.py` passes: no broken paths, no unlisted files, no mojibake, no stale stamps |
| G5 | **Living docs stay small** | `Repo_Current_State.md` ≤ 120 lines; archives absorb the history |
| G6 | **Hygiene is enforced, not remembered** | CI fails a PR that breaks a docs invariant |
| G7 | **A newcomer can orient in 10 minutes** | Root README → Tech_Stack → Repo_Current_State answers what/how/where-now |

### Non-goals

- **Not** rewriting or editing the *content* of research findings. Executed docs are moved to
  `research/archive/` **verbatim** — dates, evidence, and wording preserved. The harvest into
  `Decision_Log.md` *quotes and links*; it never restates a finding in new words.
- **Not** deleting any research doc outright. Every one is cited by live docs (§2.7), so the
  safe form of "delete" is archive-plus-link-rewrite.
- **Not** deleting history. Everything retired is moved to `archive/` or preserved on a tag,
  never dropped.
- **Not** introducing a docs generator, static site, MkDocs, or any new dependency. Plain
  markdown in git remains the medium (CLAUDE.md §1: avoid unnecessary dependencies).
- **Not** re-litigating the doc taxonomy in `docs/README.md`. It is sound; files simply stopped
  obeying it.

---

## 4. The five principles

1. **One fact, one owner.** Every fact class has exactly one owning document. Others link;
   they never restate. Drift is impossible for a fact that exists once.
2. **Living docs are short; archives are long.** A doc that must be *current* is capped and
   scannable. A doc that only records *what happened* may grow forever, and moves to
   `archive/`.
3. **Lead with the answer.** Tables, status tags, and bullets first; narrative only where a
   reader needs the *why*. A reader should triage from the first screenful.
4. **Mechanical claims must be machine-checkable.** File paths, dependency versions, and
   index membership are verifiable — so they get verified in CI, not by eye.
5. **Stamp what you verify.** Any doc asserting live state carries `Last verified: DATE`. An
   unstamped or stale claim is treated as unverified, not as true.

---

## 5. Target architecture

### 5.1 The four-tier model

Today's `docs/README.md` has three tiers (canonical / living / reference). The failure mode
is that **archive material sits inside living docs**. Add an explicit fourth tier and enforce
the boundary.

| Tier | Character | Cap | Members |
|---|---|---|---|
| **T1 — Front door** | What is this, how do I run it, what is it built with | 150 lines each | `README.md`, `docs/Tech_Stack.md`, `docs/README.md` |
| **T2 — Canonical** | Permanent laws & design; changes rarely | 400 lines | `MVP_Spec.md`, `Full_Design_Document.md`, `MVP_Technical_Design.md`, `Schema_Contract.md`, `Agent_Behavior_Spec.md` |
| **T3 — Living** | Must be true *right now*; capped and stamped | 150 lines | `Repo_Current_State.md`, `Known_Issues.md`, `Tickets.md` (open only), `Operations.md` |
| **T4 — Archive** | Append-only history; never needs to be current | uncapped | `Completion_Reports.md`, `Resolved_Issues.md`, `archive/**`, `Tickets_Archive.md`, `Manual_Verification_History.md` |

### 5.2 Disposition of all 46 files

**Front door (T1)**

| File | Action |
|---|---|
| `README.md` | **REWRITE** — currently T0002-era DB bootstrap only. See §6.2 |
| `docs/README.md` | **UPDATE** — add the 4-tier model, the Fact Ledger, and the 2 unlisted files |
| `docs/Tech_Stack.md` | **NEW** — see §6.1 |

**Canonical (T2) — reflow only, no content change**

| File | Action |
|---|---|
| `docs/MVP_Spec.md` | REFLOW (8 lines >200) |
| `docs/Full_Design_Document.md` | REFLOW (21 lines >200) |
| `docs/MVP_Technical_Design.md` | REFLOW + **split check** (126 lines >200; 435 lines) |
| `docs/Schema_Contract.md` | **KEEP AS-IS** — already conformant (max 93). Use as the model |
| `docs/Agent_Behavior_Spec.md` | REFLOW + register in `docs/README.md` |
| `docs/Prompt_Playbook.md` | **KEEP AS-IS** — conformant (max 88) |

**Living (T3) — the heavy lifting**

| File | Action |
|---|---|
| `docs/Repo_Current_State.md` | **REBUILD as a fact sheet** — 297 → ≤120 lines. See §6.5 |
| `docs/Known_Issues.md` | **SPLIT + REFLOW** — evict the 5 `RESOLVED` entries it holds in violation of its own stated rule; rebuild the category counts from actual entries |
| `docs/Tickets.md` | **SPLIT** — 1,299 lines / 107 headings / 19 done milestones. Closed milestones → `docs/archive/Tickets_Archive.md`; live file keeps open work + a one-line-per-milestone index |
| `docs/Operations.md` | **NEW** — absorbs `T0020.4_Cron_Activation_Runbook.md` + the topology facts currently restated in 4 places. See §6.3 |
| `docs/Manual_Verification_Guide.md` | **SPLIT** — 1,503 lines / 82 headings. Per-ticket one-time checks → `archive/Manual_Verification_History.md`; keep only re-runnable smoke checks |

**Archive (T4) — reflow the worst, otherwise leave**

| File | Action |
|---|---|
| `docs/Completion_Reports.md` | **FIX ENCODING** (mojibake) + REFLOW (194 lines >200). Content untouched. *In reflow scope: it gains an entry every ticket, so diff quality matters* |
| `docs/Resolved_Issues.md` | REFLOW (72 lines >200) — same reasoning, still actively appended to |
| `docs/archive/**` (6 files) | **EXCLUDED from reflow** per §5.2.1, including the 5,424-char line. Add a one-paragraph `archive/README.md` explaining what the folder is |

**Research (14 + 3 experiments) — prune to 5 live docs, per §2.7**

| File | Action |
|---|---|
| `research/README.md` | **REWRITE** — index 5 live docs + an archive pointer; correct the two stale descriptions (§2.3) |
| 4 live docs + `job-site-comparison.md` | **KEEP** — reflow; trim the comparison's unfilled rival stubs to one line each |
| 9 executed docs (~4,900 lines) | **HARVEST → `Decision_Log.md`, then move to `research/archive/`**, every inbound link rewritten |
| `research/experiments/*` (3) | **KEEP** — dated evidence behind archived findings; register in the index |
| `research/archive/README.md` | **NEW** — one paragraph: what is here, why, and that it is history not guidance |

**Outside `docs/` and `research/`**

| File | Action |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | **KEEP BOTH COMPLETE — do not dedupe.** `AGENTS.md` is Codex's instruction file, `CLAUDE.md` is Claude Code's (§2.4.1). Enforce byte-parity in lint instead. Both gain the same `Docs_Conventions.md` pointer |
| `skills/` vs `.claude/skills/` | **`.claude/skills/` is canonical** (decided, §9.2). Tag the root `skills/` copy as `archive/skills-root-copy`, then delete it. Verify the skill still loads afterwards |
| `milestone/data-ingestion-stage.md` | **DELETE the folder** per the file's own banner. Confirm its content reached the design docs; tag before deleting |
| `infra/langfuse/README.md` | **FIX or DELETE** — points to a nonexistent compose file |
| `guides/Streaming_And_SSE_Explained.md` | **KEEP AS-IS** — conformant (max 156) and correctly placed outside `docs/` |
| `evals/v1_scenario_matrix.md` | **REFLOW** — worst density in the repo (497 bytes/line, 4,231-char line) |
| `data/vendor/README.md` | Leave (14 lines) |

### 5.2.1 Reflow scope — ✅ **decided 2026-08-09**

**Reflow covers T1, T2, T3, `research/**`, `evals/v1_scenario_matrix.md`,
`Completion_Reports.md`, and `Resolved_Issues.md`. It excludes `docs/archive/**` (6 files).**

Rationale: archived files are read rarely and edited never, so diff quality — the main payoff
of hard-wrapping — buys nothing there. This drops roughly 40% of the reflow volume while
keeping ~95% of the benefit. `Completion_Reports.md` and `Resolved_Issues.md` are *tiered* as
archive but are appended to every ticket, so they stay in scope.
`evals/v1_scenario_matrix.md` stays in scope too: it has the worst density in the repo
(497 bytes/line) and `research/honesty-enforcement-design.md` cites it as live evidence.

**Consequence for §8:** the `line-length` check needs a permanent `docs/archive/**` exclusion,
not a temporary one. Encode it in the linter's config block, not as a TODO.

### 5.3 The Fact Ledger — the anti-drift core

Publish this table in `docs/README.md`. It is the mechanism behind G2, and the thing that
makes the system *powerful* rather than merely tidy.

| Fact class | Sole owner | Everyone else |
|---|---|---|
| What the product must do | `MVP_Spec.md` | link |
| Permanent laws / layer boundaries | `Full_Design_Document.md` | link |
| How a capability is built | `MVP_Technical_Design.md` | link |
| Languages, frameworks, versions, services | **`Tech_Stack.md`** (new) | link |
| `clean_jobs` column contract | `Schema_Contract.md` | link |
| Deploy topology, env vars, runbooks, cron | **`Operations.md`** (new) | link |
| What is true right now (branch, head, live state) | `Repo_Current_State.md` | link |
| What a ticket *should* do | `Tickets.md` (open) / `Tickets_Archive.md` (closed) | link |
| What a ticket *did* | `Completion_Reports.md` | link |
| Open risks | `Known_Issues.md` | link |
| Closed risks | `Resolved_Issues.md` | link |
| **Why it is this way** (decision rationale) | **`Decision_Log.md`** (new) | link |
| Doc rules & conventions | **`Docs_Conventions.md`** (new) | link |
| Agent working rules | `CLAUDE.md` + `AGENTS.md` — **identical by policy**, both complete | link |

**The rule:** if you are about to write a fact into a doc that does not own it, write a link
instead.

---

## 6. New documents — specifications

### 6.1 `docs/Tech_Stack.md` (new, T1, ≤150 lines)

The user explicitly asked for this, and the audit confirms the gap: stack facts are currently
scattered across `pyproject.toml`, `Repo_Current_State.md`, `MVP_Technical_Design.md`,
`render.yaml`, and three research docs.

Sections:

1. **At a glance** — one table: Layer / Choice / Version / Why chosen / Where configured.
2. **Runtime** — Python 3.12, FastAPI ≥0.136.3, uvicorn, `WEB_CONCURRENCY=1`.
3. **Agent** — LangChain ≥1.3.1, langgraph-checkpoint-postgres, langchain-groq,
   langchain-google-genai; the split ReAct / `sql_generation` model profiles.
4. **Data** — SQLAlchemy 2.0, psycopg 3.2, Alembic ≥1.14, Postgres 17 (Neon).
5. **Observability** — Langfuse ≥4.6.1, structlog.
6. **Ingestion** — cloudscraper, beautifulsoup4, lxml, httpx.
7. **Quality** — pytest 9, pytest-asyncio, mypy 2.1, ruff 0.15, deepeval 4.
8. **Hosted services** — Render / Neon / Langfuse Cloud, with the $0-of-$10 cost position.
9. **Deliberately not used** — CORS (same-origin), Celery, Redis, a JS framework. *This
   section prevents re-litigating settled choices.*

**Powerful bit:** `docs_lint.py --check-stack` diffs the dependency names in this doc against
`pyproject.toml` and fails if they disagree. The stack doc then *cannot* go stale silently.

### 6.2 `README.md` (rewrite, T1, ≤120 lines)

Currently 50 lines covering only `docker compose up` and `init_db.sql`.

**Audience — ✅ decided 2026-08-09: recruiter / portfolio first.** The README is optimized for
a 30-second skim by someone evaluating the author, not for someone about to run it locally.
Setup detail therefore sits *below the fold*, and anything an operator needs mid-task belongs
in `Operations.md` instead.

Order matters — write it in exactly this sequence:

1. **What it is, in one paragraph** — a Vietnamese AI/Data job-search agent that answers
   natural-language questions over real postings (note: *not* intern-only; internships are
   ~2% of the corpus, so do not oversell the name).
2. **Live demo link** — `https://internhunteragent.onrender.com`, prominent and above the fold.
3. **A screenshot, or a 6-line sample exchange** — the single highest-value element for this
   audience. A reader should see the product working without leaving the page.
4. **What's interesting about it, in 4–6 bullets** — the ReAct agent over a read-only SQL
   tool, the honesty/no-hallucination posture, streaming SSE, Langfuse tracing, the DeepEval
   harness. This is the section that does the actual portfolio work.
5. **Architecture in 5 lines** — request → API → service → agent runtime → SQL tool → Postgres,
   tracing alongside; link to `Full_Design_Document.md`.
6. **Quickstart** — clone, `uv sync`, `.env`, `docker compose up -d`, `init_db.sql`, run, open
   `http://localhost:8000`. Must be executable start to finish by a stranger (verified in §10).
7. **Where the docs are** — 5 links, one line each.
8. **Status** — v1.0-rc, linking `Repo_Current_State.md`.

Move the existing DB-reset detail into `Operations.md`; it is operator material, not
front-door material.

> **Screenshot — ✅ resolved 2026-08-09: none available yet.** T0022.4 ships **item 3 as the
> 6-line sample exchange only** and is not blocked. Add a `[LOW · OPEN]` entry to
> `Known_Issues.md` for the screenshot (suggested path `docs/assets/demo.png`), to be captured
> when the live demo is next up. Write the README so the image slots in without a rewrite —
> put the sample exchange in its own section, not woven into a paragraph.

### 6.3 `docs/Operations.md` (new, T3, ≤200 lines)

Absorbs `T0020.4_Cron_Activation_Runbook.md` (424 lines) and consolidates the deploy topology
now restated in `Repo_Current_State.md`, `Completion_Reports.md` (T0018.4),
`research/deployment-research-plan.md`, and the runbook.

Sections: topology table (Render / Neon / Langfuse, region, tier, health check) · environment
variables and where each is set · deploy flow and the `render.yaml` pin · database operations
(init, reset, Alembic upgrade, current head) · the ingestion cron and its gating · keep-alive
· incident notes. Carries `Last verified:`.

**Do not delete the runbook mid-flight.** The cron activation is still pending maintainer
execution; the runbook is its live artifact. Merge it in and leave a pointer at the old path
until activation completes.

### 6.4 `docs/Docs_Conventions.md` (new, T1/reference, ≤120 lines)

The written form of §7, plus: the Fact Ledger rule, the tier model and caps, the
`Last verified:` stamp, the `<!-- archived-on-tag -->` escape hatch, and — prominently — the
**PowerShell encoding hazard** (§2.5): never round-trip a doc through `Get-Content` /
`Set-Content`; use an editor or the file-edit tooling.

### 6.5 `docs/Repo_Current_State.md` (rebuild, T3, ≤120 lines)

Today: 297 lines, a 2,790-char line, 66 commits of churn, and long narrative sections that
duplicate `Completion_Reports.md`.

Rebuild as a **fact sheet** — tables and short bullets only:

| Block | Form |
|---|---|
| Header | Branch · head SHA · `Last verified:` date |
| Live deployment | 4-row table (API / DB / tracing / URL) — or better, link to `Operations.md` |
| Milestones | **One line each**, status tag only. Detail lives in `Completion_Reports.md` |
| Open maintainer actions | Short checklist (branch protection, cron activation) |
| Archive tags | Keep the existing table — it is genuinely useful and already tabular |
| Build/test status | One line + date |
| Known issues | **Link only.** Never a copy |
| Next recommended ticket | 2 lines |

The current per-capability inventory ("T0016.1 – CORS middleware: …") is the main bloat: it
restates completion reports. Cut it; link instead.

### 6.6 `docs/Decision_Log.md` (new, T2, ≤300 lines) — the "one place"

**This is the answer to "gather all the information into one place."** Nine research docs
(~4,900 lines) are executed plans whose remaining value is the handful of decisions inside
them. Today, answering *"why does `tech_stack` use an external vocabulary instead of an
allowlist?"* means knowing that `schema-enrichment-plan.md` superseded
`data-ingestion-stage.md` §5 — a fact recorded only inside the superseding doc.

**Format — one row per decision, ADR-style but compact:**

```markdown
### D-014 · tech_stack built from an external vocabulary, not a hardcoded allowlist
- **Decided:** 2026-07-09 · **Status:** Active · **Shipped in:** M13 (T0013.1)
- **Why:** a hardcoded allowlist could not keep pace with source tags; audit coverage
  rose 58% → 89% against an external vocabulary.
- **Supersedes:** `data-ingestion-stage.md` §5 (allowlist default).
- **Full record:** [`research/archive/schema-enrichment-plan.md`](…)
```

**Rules that keep it from becoming another wall of text:**

| Rule | Value |
|---|---|
| Length per decision | **≤ 6 lines.** If it needs more, the full record is one link away |
| Ordering | Newest first, stable `D-NNN` ids that are never renumbered |
| Status | `Active` · `Superseded by D-NNN` · `Reversed` — never delete a decision |
| Scope | Only decisions with **durable consequences**. Not every finding |
| Ownership | Sole owner of *"why is it this way"* in the Fact Ledger |

**Expected content:** roughly 25–35 decisions harvested from the nine archived docs — source
market choice, VietnamWorks-over-alternatives, the schema freeze, `tech_stack` vocabulary,
same-origin static UI, `fetch()`+`ReadableStream` over `EventSource`, Render/Neon/Langfuse
selection, the judge-provider switch to Gemini, deterministic hedging, Alembic adoption, cron
gating, `main` reconciliation.

**Why this beats leaving them in `research/`:** a reader gets every decision in one scan
instead of opening nine documents, and `CLAUDE.md` §1's "read the research before designing"
rule becomes cheap to obey rather than a 5,900-line tax.

---

## 7. The readability standard

Written into `docs/Docs_Conventions.md` and enforced by §8.

| Rule | Value | Rationale |
|---|---|---|
| **Hard wrap** | 100 chars | Matches the repo's already-conformant files; makes diffs line-level |
| Exemptions | Table rows, code fences, link-only lines, long URLs | Wrapping these hurts |
| **Paragraph length** | ≤ 5 lines, then a break | The "wall of text" fix |
| **Lead with structure** | Table or bullets before prose in every T1/T3 doc | Triage from the first screenful |
| **Heading depth** | ≤ H3 in living docs | H4+ signals the doc should be split |
| **Status tags** | `[SEVERITY · STATE]` — keep the existing `Known_Issues.md` scheme | Already good; apply consistently |
| **Dates** | Absolute `YYYY-MM-DD`, never "recently" / "now next" | `research/README.md` drifted exactly this way |
| **Freshness stamp** | `> **Last verified:** YYYY-MM-DD` on every T3 doc | Distinguishes verified from assumed |
| **Cross-refs** | Relative markdown links | Machine-checkable |
| **Encoding** | UTF-8, no BOM, LF | Prevents §2.5 recurrence |

**Reflow is mechanical and must not change meaning.** Reflow commits stay separate from
content commits so review is tractable — one commit per file group, message
`docs(T0022.x): reflow <file> to the 100-char standard (no content change)`.

---

## 8. Automation — `scripts/docs_lint.py`

A single dependency-free stdlib script (CLAUDE.md §1: no unnecessary dependencies), runnable
locally and in CI.

| Check | Rule | Failure mode caught |
|---|---|---|
| `line-length` | No line >100 chars outside exemptions; **`docs/archive/**` permanently excluded** per §5.2.1 | §2.2 — the readability defect |
| `link-path` | Every backticked repo path and relative link resolves, unless tagged `<!-- archived-on-tag -->` | §2.3 — 15 broken refs |
| `index` | Every `.md` in `docs/` and `research/` appears in that folder's README | §2.3 — 8 unlisted files |
| `encoding` | Valid UTF-8, no BOM, no `â€` / `Â ` / `ï»¿` / `â†` sequences | §2.5 — active mojibake |

> **Self-reference exemption (found by dogfooding this plan).** This document and
> `Docs_Conventions.md` both *quote* the mojibake byte sequences in order to define the rule,
> so a naive `encoding` check flags them — this file trips it 3 times. The check must ignore
> matches inside backtick code spans, or honor a `<!-- lint-allow-encoding -->` marker.
> Verify by running the finished linter against this file: it must exit 0.
| `stamp` | Every T3 doc has `Last verified:`; warn if older than its own last commit date | Silent staleness |
| `size-cap` | T1 ≤150, T3 ≤150–200 lines per §5.1 | Living docs bloating back into archives |
| `check-stack` | Dependency names in `Tech_Stack.md` match `pyproject.toml` | Stack doc drifting from reality |
| `agent-parity` | **`AGENTS.md` and `CLAUDE.md` are byte-identical**; ditto the two `SKILL.md` copies | §2.4.1 — Codex and Claude Code silently drifting apart |
| `duplicate-heading` | Warn when the same H2 appears in two living docs | Early warning of ownership violation |

**Usage:** `uv run python scripts/docs_lint.py` (all checks) ·
`--check line-length --fix` (safe autofix for reflow) · `--stat` (prints the §2 baseline
table, so progress is measurable at any point).

**CI wiring:** add a `docs` job to `.github/workflows/ci.yml` alongside the existing
ruff/mypy/pytest gate. Start it as **warn-only for one milestone**, then flip to blocking once
the backlog is clean — otherwise every unrelated PR turns red on day one.

**Not proposed:** a pre-commit framework, a docs site generator, or link-checking external
URLs (slow, flaky, and network-dependent in CI).

---

## 9. Execution — M22, tickets T0022.1–.9

### 9.0 Milestone placement — ✅ **decided 2026-08-09**

`research/v1-release-readiness-plan.md` defines **M22 = v1.0 Release Cut** with "docs
conformance" as one DoD bullet. That bullet cannot absorb this work.

**Decision: M22 becomes Docs Hygiene & Documentation System, and the v1.0 release cut
renumbers to M23.** Rationale: the root README is the first thing any visitor to a portfolio
repo reads, and tagging v1.0 while it describes a T0002 database bootstrap ships the weakest
artifact under the strongest label. The docs work is fully parallel to code — nothing in
M23's DoD depends on it beyond conformance itself.

**Consequence:** `research/v1-release-readiness-plan.md` must be updated (M20–M22 → M20–M21,
M23), and every "M22" reference in it re-pointed. Tracked as a line item in §13.

### 9.1 Ticket sequence

One branch per ticket per CLAUDE.md §3. **T0022.1 goes first** so every later ticket has a
measurable pass/fail target rather than a subjective one.

| Ticket | Scope | Depends on | Risk |
|---|---|---|---|
| **T0022.1** | `docs_lint.py` + `Docs_Conventions.md` + CI job in **warn-only** mode. Ships the §2 baseline as `--stat` output | — | Low |
| **T0022.2** | **Encoding + parity:** fix `Completion_Reports.md` mojibake; confirm `AGENTS.md`/`CLAUDE.md` byte-identical and **both complete** (no collapsing — §2.4.1); tag+delete root `skills/` and `milestone/`; fix or drop `infra/langfuse/README.md` | .1 | Low — all inputs now decided |
| **T0022.3** | **Mechanical reflow, no content change.** ~40 files to the 100-char standard — T1/T2/T3, `research/**`, `Completion_Reports.md`, `Resolved_Issues.md`, `evals/v1_scenario_matrix.md`. **`docs/archive/**` excluded** (§5.2.1). Separate commits per group | .1 | Low, high volume — review as "no semantic diff" |
| **T0022.4** | **Front door:** rewrite `README.md`; add `Tech_Stack.md`; wire `--check-stack` | .1 | Medium — quickstart must be verified on a clean clone |
| **T0022.5** | **Operations consolidation:** new `Operations.md`; absorb the T0020.4 runbook (leave a pointer); single-source the topology | .4 | **Medium-high** — cron activation is live work; do not break the runbook |
| **T0022.6** | **Archive split:** `Tickets.md` → `Tickets_Archive.md`; `Manual_Verification_Guide.md` → history. Living files keep open items + an index | .3 | Medium — mind inbound links |
| **T0022.7** | **Rebuild `Repo_Current_State.md`** as a fact sheet; evict `RESOLVED` entries from `Known_Issues.md`; rebuild its category counts | .6 | Medium |
| **T0022.8** | **Research prune (§2.7):** harvest ~25–35 decisions into `Decision_Log.md`; move the 9 executed docs to `research/archive/`; trim `job-site-comparison.md`; rewrite every inbound link; add `research/archive/README.md` | .3 | **Highest** — 9 docs × up to 6 inbound links each; `link-path` must be green before and after |
| **T0022.9** | **Index + ledger:** rewrite `docs/README.md` (4 tiers + Fact Ledger) and `research/README.md` (5 live docs + archive pointer); **flip CI to blocking** | all | Low |

### 9.2 Maintainer answers — ✅ **both resolved 2026-08-09**

| # | Question | Answer |
|---|---|---|
| Q1 | Which `SKILL.md` copy is canonical? | **`.claude/skills/` is canonical.** The root `skills/` copy is a leftover: **tag it, then delete it** (`archive/skills-root-copy`), per the repo's established tag-and-drop pattern. Codex does not auto-load `skills/`, so nothing breaks; the workflow rules Codex needs are in `AGENTS.md`, which stays complete |
| Q2 | Is a demo screenshot available? | **No, not yet.** T0022.4 ships the **6-line sample exchange** instead and is **not** blocked. Log the screenshot as a follow-up in `Known_Issues.md` (`[LOW · OPEN]`), to be added when the live demo is next up |

**Consequence for `agent-parity`:** with the root `skills/` copy gone, that check covers only
the `AGENTS.md` ↔ `CLAUDE.md` pair. Keep it a two-file check; do not generalize it.

### 9.3 Definition of done for the milestone

- `uv run python scripts/docs_lint.py` exits 0 on all checks.
- CI `docs` job is blocking on PRs targeting `main`.
- Every `.md` file has a stated tier and an owner in the Fact Ledger.
- A stranger can clone, follow the root README, and reach a working local app.
- In-scope files carry no line >100 chars outside the table/code exemptions:

```bash
git ls-files '*.md' | grep -v '^docs/archive/' | xargs awk 'length($0)>100 && $0 !~ /^\|/' | wc -l
# expected: 0
```

- **M23 (v1.0 Release Cut) is unblocked** — its "docs conformance" DoD bullet is satisfied by
  this milestone rather than deferred into it.
- `research/` holds **5 live docs**; the other 9 are in `research/archive/` and every inbound
  link resolves.
- `Decision_Log.md` exists, and each archived doc has at least one decision harvested from it.
- `diff AGENTS.md CLAUDE.md` is empty and **both files are complete** — a Codex session still
  picks up the project rules.

### 9.4 Live-surface reduction, projected

| Surface | Before | After |
|---|---:|---:|
| `research/` live docs | 14 (5,900 lines) | **5 (~1,900 lines)** |
| `docs/` living-tier lines | ~3,500 | **~900** |
| Total lines a newcomer must skim to orient | ~14,500 | **~2,500** |

The other ~12,000 lines are not deleted — they move to `archive/`, where they stay findable
and stop demanding upkeep.

---

## 10. Manual verification checklist

Per CLAUDE.md §4 — what the developer runs by hand after each ticket.

**After T0022.1**

- [ ] `uv run python scripts/docs_lint.py --stat` prints a baseline matching §2.1.
- [ ] Deliberately break a link in a scratch file → `link-path` flags it; revert.
- [ ] Open a throwaway PR → the `docs` job appears and is **non-blocking**.

**After T0022.2**

- [ ] `grep -rn "â€" --include="*.md" .` returns nothing.
- [ ] `docs/Completion_Reports.md` T0019.10 section renders `—`, `⚠️`, `→` correctly in a
      markdown preview.
- [ ] The ticket-prompt skill still loads: run `/generate-ticket-prompt` and confirm it works.
- [ ] `git tag` shows the pre-deletion tag for `milestone/`.
- [ ] **`diff AGENTS.md CLAUDE.md` is empty, and both files are still complete** (55 lines,
      all 6 sections) — neither has been reduced to a pointer.
- [ ] **Codex check:** start a Codex session in the repo and confirm it picks up the project
      rules from `AGENTS.md` — ask it to state the branching strategy (CLAUDE.md §3). This is
      the only check that proves the Codex half still works.

**After T0022.3**

- [ ] `git diff --word-diff` on a sample of reflowed files shows **no word-level changes**.
- [ ] `docs_lint.py --check line-length` exits 0.

**After T0022.4**

- [ ] On a clean clone in a fresh directory, follow the README quickstart end to end and get a
      streamed answer at `http://localhost:8000`. Note any step that required outside knowledge.
- [ ] `docs_lint.py --check-stack` exits 0; then bump a version in `pyproject.toml` and confirm
      it **fails**; revert.

**After T0022.5**

- [ ] Every step of the old T0020.4 runbook is present in `Operations.md` — diff them
      side by side; the cron activation must remain executable.
- [ ] Env-var table matches the Render dashboard and `.env.example`.

**After T0022.6 / .7**

- [ ] `docs_lint.py --check link-path` exits 0 (no inbound link broken by the split).
- [ ] `Repo_Current_State.md` ≤120 lines and states branch, head, live URL, next ticket
      within the first screenful.
- [ ] `Known_Issues.md` contains no `RESOLVED` entries; its category counts match a manual
      recount.

**After T0022.8 (research prune — the riskiest ticket)**

- [ ] `docs_lint.py --check link-path` exits 0. **Run it before the move as well**, so a
      pre-existing break is not mistaken for one this ticket caused.
- [ ] `grep -rn "research/" --include="*.md" docs/ README.md` — every hit resolves to either a
      live doc or `research/archive/`.
- [ ] Spot-check 5 harvested decisions against their source docs: the `Decision_Log.md` entry
      states the same thing the original did, with the date preserved.
- [ ] `research/` contains exactly **5** live `.md` files plus `README.md`, `archive/`, and
      `experiments/`.
- [ ] Open `Decision_Log.md` cold and answer *"why is `tech_stack` not a hardcoded
      allowlist?"* in under 30 seconds without opening another file.

**After T0022.9**

- [ ] Every `.md` under `docs/` and `research/` is reachable from its README.
- [ ] A PR with a >100-char doc line is **blocked** by CI.
- [ ] A PR that edits `CLAUDE.md` without `AGENTS.md` is **blocked** by the `agent-parity`
      check.

---

## 11. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Reflow silently alters content** | Medium | Reflow-only commits; review with `--word-diff`; never mix with content edits |
| **Splitting archives breaks inbound links** | Medium | `link-path` check runs before and after; T0022.6 is gated on it |
| **`Operations.md` consolidation disrupts the pending cron activation** | **Medium-high** | Merge, don't move: keep `T0020.4_Cron_Activation_Runbook.md` as a pointer until activation completes |
| **CI blocking too early turns unrelated PRs red** | High if mishandled | Warn-only for one milestone (T0022.1), flip at T0022.8 |
| **Deleting the wrong `SKILL.md` copy breaks the skill** | Low | Q1 in §9.2; diff both, confirm with the maintainer, verify by invoking the skill |
| **Collapsing `AGENTS.md` silently degrades Codex** | **High if unguarded** — it was this plan's own first recommendation | §2.4.1 makes both files mandatory; `agent-parity` enforces it; the §10 Codex check proves it |
| **Archiving a research doc breaks a live reference** | **High** — all 14 are cited by 1–6 live docs | `link-path` green before *and* after T0022.8; move in one commit per doc so a bisect is cheap |
| **A decision is lost in the harvest** | Medium | Nothing is deleted — the full record stays in `research/archive/` and every `Decision_Log.md` entry links to it. Spot-check in §10 |
| **`Decision_Log.md` becomes the next wall of text** | Medium | Hard ≤6-line cap per decision, enforced by review; detail belongs in the linked archive record |
| **Docs churn resumes after the cleanup** | Medium | This is exactly what §8 exists to prevent; the 2026-07 pass failed *because* it had no enforcement |
| **PowerShell reintroduces mojibake** | **High without a guard** | `encoding` check is blocking; the hazard is documented in `Docs_Conventions.md` |
| **Plan scope grows into content rewriting** | Medium | Non-goals in §3 are binding; research findings and dates are frozen |

---

## 12. Out of scope / follow-ups

- **Rewriting research doc content.** Reflow only.
- **A docs site (MkDocs/Docusaurus).** Revisit only if the repo becomes multi-contributor.
- **External URL link-checking.** Flaky in CI.
- **`Agent_Behavior_Spec.md`'s unlanded `behavior_glossary`.** A real open item, but it
  changes agent output — it belongs to the behavior track, not to docs hygiene.
- **Auto-generating `Repo_Current_State.md` from git.** Attractive, but premature; revisit
  after T0022.7 shows what is genuinely mechanical.
- **Vietnamese-language README.** Worth considering for the portfolio audience; separate ticket.

---

## 13. Docs that need updating when this plan lands

| Doc | Change |
|---|---|
| `research/README.md` | Register this plan **and** the 6 currently-unlisted files; fix the 2 stale descriptions |
| `docs/Tickets.md` | Graduate §9 into M22 (T0022.1–.9) |
| `research/v1-release-readiness-plan.md` | **Renumber M22 → M23** and re-point every "M22" reference (§9.0, decided). Its title/§2 heading "M20–M22 Shape" also changes |
| `docs/README.md` | 4-tier model + Fact Ledger (T0022.8) |
| `CLAUDE.md` §6 **and `AGENTS.md` §6** | Add a pointer to `Docs_Conventions.md` so future tickets inherit the standard. **Edit both, identically** — §2.4.1 |
| `CLAUDE.md` / `AGENTS.md` §1 | The "read `research/` before designing" rule should point at `Decision_Log.md` first, then the surviving live docs — the whole point of the harvest |
| `docs/Known_Issues.md` | Log the encoding hazard as a standing `[LOW · NOTE]` if not already present |
