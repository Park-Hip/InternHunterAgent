# Docs Prune & Per-File Structure — M22 Phase 2 Plan

> **Status:** Pre-design plan (research). Authored **2026-08-10**; measured against M22 phase 1
> (T0022.1-.9), which merged to `main` on **2026-08-11** as PR #41 (`566aba4`). Every number
> below was **measured**, not estimated.
>
> **Scope:** a file-level pass over all 53 Markdown files — prune what nobody reads, then fix
> the structure of what survives. Phase 1 built the enforcement system and moved history into
> archives; it deliberately deleted almost nothing and rewrote only the front door.
>
> **Feeds:** `docs/Tickets.md` (T0022.10-.14). **Companion:**
> [`docs-hygiene-and-system-plan.md`](docs-hygiene-and-system-plan.md) (phase 1).

---

## 0. TL;DR — the six moves

| # | Move | Effect |
|---|---|---|
| 1 | **Delete 7 dead files** and the unused self-hosted Langfuse stack | -956 doc lines; closes 1 open security issue |
| 2 | **Collapse 5 executed research archives** into decision records | 2,241 → ~700-900 lines, every inbound link and section citation intact |
| 3 | **Re-triage and rebuild `Known_Issues.md`** | 1,199 → ~250 lines; the register stops being partly fiction |
| 4 | **Restructure 6 living/canonical docs** for scannability | `Tickets.md` 945 → ~200; blueprint split along the layer boundary |
| 5 | **Close the M22 harvest gap** and fix 3 factual contradictions | 2 unharvested archives; `infra/` claims that disagree three ways | <!-- archived-on-tag -->
| 6 | **Give every capped doc an eviction rule, and lint the caps** | The reason phase 1's caps were already breached |

**Live surface:** 19,755 lines today → **~14,400**, of which the part a person actually reads
drops from ~6,700 to **~2,400**.

### Decisions locked 2026-08-10

| Decision | Choice |
|---|---|
| Dead-file deletions | **All of §3.1**, tagged `archive/docs-pre-prune` first. The root `skills/` copy was in the original list and has since been ruled out — see §3.1.1 |
| `Tickets_Archive.md` / `Manual_Verification_Archive.md` | **Keep as-is** — archived one ticket ago; churn to touch again |
| `research/archive/` | **Collapse the 5 fully-superseded; leave the 4 with live or unharvested content** |
| `Known_Issues.md` | **Collapse *and* re-triage** every open entry against current code |
| `infra/` (self-hosted Langfuse) | **Delete** — superseded by D-029 (Langfuse Cloud) | <!-- archived-on-tag -->
| Milestone placement | **T0022.10-.14** — extend M22 rather than renumber; T0023 stays the release cut |

---

## 1. Why a second pass

Phase 1 was a *systems* milestone: it built `docs_lint.py`, published the Fact Ledger, wrote the
front door, and split history into archives. It succeeded at that and explicitly ruled deletion
out of scope ("Not deleting any research doc outright").

That leaves three things it could not have fixed:

- **Nothing was pruned.** The repo has 53 Markdown files and no file was removed on merit. Dead
  templates, spent spike prompts, and a superseded hygiene review all survived because the
  milestone's safe move was "archive, don't delete."
- **Two caps were breached on the day they were written.** `Known_Issues.md` is 1,199 lines
  against its own 150-line cap; `MVP_Technical_Design.md` is 1,019 against 400. Phase 1 defined
  the caps but shipped no `size-cap` check, so they are aspirations.
- **Its own DoD has a hole.** "Each archived doc has at least one decision harvested from it" is
  false for two of nine (§5.1).

---

## 2. The system frame — every doc needs a reader and a trigger

The Fact Ledger answers *"who owns this fact?"* It cannot answer *"should this file exist?"* —
a doc can own a fact nobody will ever look up. This pass adds the missing axis: **every
surviving document must name a reader and the moment that reader opens it.**

| Reader | Trigger | Path they walk |
|---|---|---|
| A stranger evaluating the project | Landed from a link | `README.md` |
| A newcomer about to build | "How does this work?" | `docs/README.md` → `Tech_Stack` → `MVP_Spec` → `Full_Design` → `MVP_Technical_Design` |
| The maintainer resuming | "Where was I?" | `Repo_Current_State` → `Tickets` → `Known_Issues` |
| An operator mid-incident | Something broke | `Operations` → cron runbook → `Known_Issues` |
| An agent starting a ticket | `CLAUDE.md` §1 sends it | `Decision_Log` → live `research/` → `Docs_Conventions` |
| A future decision-maker | "Did we consider X?" | `Decision_Log` → `research/archive/` |
| Nobody, until an audit | Provenance question | `Completion_Reports`, `Resolved_Issues`, `docs/archive/` |

**The test:** a file that fits no row is deleted. A file that fits a row but cannot be read in
the time that reader has is restructured. Everything in §3-§6 falls out of applying this.

### 2.1 Two rules that stop the regression

Phase 1 assumed caps would hold because they were written down. They did not, and the reason
generalizes:

**Rule A — a capped doc must state what leaves it, and when.** `Known_Issues.md` grew to 8× its
cap because entries could only ever be *appended* or *amended* — no rule said when one leaves.
Compare `Completion_Reports.md`, which grows without complaint because it is uncapped by design.
Every capped doc gets a one-line eviction rule in its header, and `size-cap` enforces the number.

**Rule B — correct by collapsing, never by appending.** The repo's characteristic defect is
correction-on-correction. Live examples:

| Doc | The layer |
|---|---|
| `research/v1-release-readiness-plan.md` | "**Read every 'M22' below as 'M23'**" — a banner reinterpreting 300 lines |
| `docs/Schema_Contract.md` | "The gate is **no longer T0014**" |
| `docs/Known_Issues.md` | One entry runs 41 lines across *Found → Fixed in sandbox → Owned → Fixed → Remaining gap* |
| `docs/Agent_Behavior_Spec.md` | 40 lines of provenance and "NOT LANDED" warnings before any content |

Each layer is individually honest and collectively unreadable: the reader must replay the
document's edit history to learn its current claim. The rule — **rewrite against current truth;
git holds the superseded version** — goes into `Docs_Conventions.md`, and `docs_lint.py` warns on
the giveaway phrases (`no longer`, `read every`, `correcting an earlier`, `superseded above`).

---

## 3. Phase A — prune

Tag `archive/docs-pre-prune` immediately before the first deletion. Everything here is
recoverable from that tag and from git history.

### 3.1 Files deleted

| File | Lines | Verdict |
|---|---:|---|
| `docs/archive/Claude_Code_Review_Skeleton.md` | 198 | Blank template whose own banner says "do not record findings here until the review pass begins." The pass happened and wrote `Code_Review_Notes.md` free-form. Zero inbound links | <!-- archived-on-tag -->
| `docs/archive/Documentation_Hygiene_Review_T0016.md` | 187 | The 2026-07 hygiene pass M22 supersedes, and cites only as the cleanup that decayed | <!-- archived-on-tag -->
| `docs/archive/Repo_State_History.md` | 272 | Old branch snapshots; own banner: "the authoritative history is git." Holds the repo's worst line (5,424 chars) | <!-- archived-on-tag -->
| `research/experiments/deployment-research-fill-prompt.md` | 49 | A prompt to *fill* a document that is filled (892 lines) and archived | <!-- archived-on-tag -->
| `research/experiments/topdev-scraping-spike-prompt.md` | 181 | A prompt to *run* a spike that ran; results are `job-site-comparison.md` Candidate 3 | <!-- archived-on-tag -->
| `docs/Prompt_Playbook.md` | 63 | Duplicated by `skills/generate-ticket-prompt/SKILL.md`, which names it as its base structure. Two homes, one template | <!-- archived-on-tag -->
| `infra/langfuse/README.md` | 6 | Six lines asserting the directory is empty — see §3.2 | <!-- archived-on-tag -->
| **Total** | **956** | 53 → **46** Markdown files |

**Inbound links to repair:** `docs/README.md` (Prompt Playbook row),
`skills/generate-ticket-prompt/SKILL.md` line 57 (absorb the template inline),
`docs/Repo_Current_State.md` (Repo State History), `research/job-site-comparison.md` (TopDev
spike prompt). `link-path` must be green before and after.

### 3.1.1 `skills/` is **not** deleted — T0022.2's premise was wrong

An earlier draft of this plan listed `skills/generate-ticket-prompt/**` for deletion, following
T0022.2's note that *"`.claude/skills/` is canonical; tag and delete the root copy."*

**That premise does not hold: `.claude/` is gitignored** (`.gitignore:4`). The Claude Code copy
exists only on a machine that has run Claude Code, so **the tracked `skills/` copy is the only
one in version control** — deleting it would drop the skill from the repository entirely and
leave Codex, CI, and every fresh clone without it.

Found by CI on PR #41: `test_shared_skill_instructions_match` read the untracked path
unconditionally and raised `FileNotFoundError` on the clean checkout. The test now skips when the
local copy is absent. **Actions for T0022.10:** keep `skills/` tracked, and record the reversal in
`Decision_Log.md` so the "delete the root copy" note is not acted on later.

### 3.2 `infra/` — one dead directory, three disagreeing claims <!-- archived-on-tag -->

`infra/docker-compose.yaml` is a complete six-service self-hosted Langfuse stack <!-- archived-on-tag -->
(`langfuse-web`, `langfuse-worker`, `clickhouse`, `minio`, `redis`, `postgres`). D-029 chose
Langfuse Cloud. The remains generate three claims that cannot all be true:

| Doc | Claim |
|---|---|
| `docs/Tech_Stack.md` | "Self-hosted Langfuse — `infra/langfuse/` has no Compose service" | <!-- archived-on-tag -->
| `docs/Full_Design_Document.md` §5 | "The self-hosted Langfuse stack lives under `infra/langfuse/`" — wrong path *and* wrong decision | <!-- archived-on-tag -->
| `docs/Known_Issues.md` | An **open** `[OPEN]` entry about that stack's `CHANGEME` secrets |

Delete `infra/`. That makes `Tech_Stack.md` simply true, lets `Full_Design_Document.md` §5 say <!-- archived-on-tag -->
tracing is Cloud-hosted, and closes the security entry as *"resolved by removal"* in
`Resolved_Issues.md`.

### 3.3 Files kept, and why

| File | Reader it serves |
|---|---|
| `research/experiments/vietnamworks_tos_excerpt_2026-07-16.md` | The legal-gate evidence behind D-034. Dated, unreproducible — the page carries no version |
| `docs/archive/Code_Review_Notes.md` | Cited 7× from `Resolved_Issues.md` as the "bug N" detail behind closed entries |
| `docs/archive/Completion_Reports_Archive.md`, `Manual_Verification_History.md` | 83 and 86 lines. Below the cost of touching |
| `docs/archive/Tickets_Archive.md`, `Manual_Verification_Archive.md` | Archived by T0022.6 one ticket ago. Re-litigating is churn (**decided 2026-08-10**) |
| `guides/Streaming_And_SSE_Explained.md` | A deliberate learning walkthrough, correctly outside `docs/`. Needs indexing, not pruning |

**`Code_Review_Notes.md` gets one edit, not deletion:** keep the bug index the 7 links resolve
against; drop the 2026-07-02 improvement backlog after checking which items shipped.

---

## 4. Phase B — collapse the executed research archives

**Deletion is unavailable here.** Each of the nine archived documents is linked from 3-13 live
documents; removing them breaks roughly 50 inbound links and the `link-path` gate that phase 1
just made blocking.

The archive is also the *only* place one thing lives:

| Layer | Owner |
|---|---|
| The decision | `Decision_Log.md` (D-001…D-034) |
| How the built thing works | `MVP_Technical_Design.md` §7-§11, `Operations.md`, `Schema_Contract.md` |
| **The deliberation — options weighed, roads not taken, live-checked facts** | **`research/archive/` only** |

So the archive answers *"did we consider X, and why not?"*, and nothing else does. What it does
**not** need to carry is the scaffolding: generic tutorial material, "what to research" outlines,
ticket breakdowns for shipped tickets, and "open decisions for the user" that were answered.

### 4.1 The five that collapse

| Doc | Lines | Outcome now owned by | Scaffolding to drop |
|---|---:|---|---|
| `deepeval-sql-agent-eval-planning.md` | 648 | `MVP_Technical_Design.md` §8, D-016/17/18 | §1-§9 are a generic DeepEval tutorial. §11 (version-pinned findings) is the part that is ours |
| `ingestion-milestone-plan.md` | 573 | `MVP_Technical_Design.md` §7, `Operations.md`, D-019/20/21/24 | §3's T0019.1-.8 breakdown — all shipped |
| `demo-ui-and-golive-plan.md` | 397 | `MVP_Technical_Design.md` §11, D-002/3/4 | §6 sub-ticket split; §7 "open decisions" all answered |
| `streaming-implementation-plan.md` | 313 | `MVP_Technical_Design.md` §9, D-005…D-009 | §8 T0017 sub-ticket implications |
| `schema-enrichment-plan.md` | 310 | `Schema_Contract.md`, D-010…D-015 | §5 sequencing and ticket implications |
| **Total** | **2,241** | | **→ ~700-900** |

**The uniform decision-record shape** each collapses to:

```markdown
# <title> — Decision Record (archived)
> Archived YYYY-MM-DD. <Milestone> shipped. Outcome owned by <doc>.
> Preserved for the reasoning and the rejected alternatives; not implementation guidance.
## Decisions taken            <- one line each, with its D-NNN id
## Rejected alternatives      <- one line each, with the reason. THE point of the file
## Live-checked facts         <- dated environment measurements, verbatim
## Sources
```

**Two constraints on the collapse:**

1. **Section identity is a link target.** Citations name the section inside the *link text* —
   "DeepEval planning §4" — rather than as a URL anchor, so removing a section makes the
   citation nonsense while `link-path` stays green. **Every cited section number must survive as
   a heading**, even when its body collapses to one line.

   The 2026-08-11 audit found the citing surface is far wider than `Decision_Log.md`:
   `MVP_Technical_Design.md`, `Known_Issues.md`, `Completion_Reports.md`, `Resolved_Issues.md`,
   and `archive/Tickets_Archive.md` all cite these records by section, and several cited
   sections are exactly the scaffolding this section proposed to drop. That is why the target
   is ~700-900 lines rather than the ~450 first estimated. The enumerated starting set lives in
   `docs/Tickets.md` → T0022.11.
2. **Do not reword findings.** Phase 1's non-goal holds: prose, dates, and evidence are moved or
   dropped verbatim, never rewritten.

### 4.2 The four left at full length

| Doc | Lines | Why it stays |
|---|---:|---|
| `deployment-research-plan.md` | 892 | Backs 12 `Decision_Log` entries and 13 inbound links — the highest-value single record. *Fix only its stale banner, which still calls it "an outline of what to research, not the findings."* |
| `data-ingestion-stage.md` | 442 | **Unharvested** (§5.1). §11 is a runbook still marked "PENDING D8, NOT YET RUN" |
| `pre-deploy-refinement-plan.md` | 595 | **Unharvested** (§5.1). Cited by `Schema_Contract.md` as the schema-freeze precondition |
| `agent-behavior-question-bank.md` | 755 | `Agent_Behavior_Spec.md` §3 points here for the canonical phrasings. Revisit if the behavior track restarts |

---

## 5. Phase C — rebuild the registers

### 5.1 Close the harvest gap first

M22's DoD: *"each archived doc has at least one decision harvested from it."* Measured against
`Decision_Log.md`:

| Archived doc | Decisions harvested |
|---|---:|
| `deployment-research-plan.md` | 12 |
| `schema-enrichment-plan.md` | 6 |
| `streaming-implementation-plan.md` | 5 |
| `ingestion-milestone-plan.md` | 4 |
| `deepeval-sql-agent-eval-planning.md` | 3 |
| `demo-ui-and-golive-plan.md` | 3 |
| `agent-behavior-question-bank.md` | 1 |
| **`data-ingestion-stage.md`** | **0** |
| **`pre-deploy-refinement-plan.md`** | **0** |

The two with zero are the *most* cross-linked in the archive (10 and 9 inbound docs). Candidate
harvests: the source-market choice (Vietnamese boards), the ToS/legality posture, the
`tech_stack` architectural fork, and the schema-freeze-before-refinement sequencing.

### 5.2 `Known_Issues.md` — collapse and re-triage

**1,199 lines, 73 entries, against a 150-line cap.** Three separate defects:

| Defect | Evidence |
|---|---|
| Entries are edit histories | One `[HIGH · PARTIALLY RESOLVED]` entry spans 41 lines and four generations of amendment |
| ~21 entries are not issues | 12 `[LOW · NOTE]` + 9 `[NOTE]` are by-design facts — they belong to `Operations`, `Tech_Stack`, or `Docs_Conventions` |
| The header already drifted | Category counts total 73; the tags in the body count 75 |

**Decided 2026-08-10: collapse *and* re-triage** — each of the 46 `OPEN` entries is checked
against current code before it is rewritten, and the ones that were quietly fixed are closed into
`Resolved_Issues.md`. Structure-only would leave a register that is partly fiction.

**New entry shape — four fields, one line each, hard-capped at 6 lines:**

```markdown
- **`[MED · OPEN]` <the claim, readable alone>**
  - **Found:** YYYY-MM-DD, <ticket or context>
  - **Impact:** <what breaks, one sentence>
  - **Next:** <candidate fix or owning ticket>
  - **History:** <link into Resolved_Issues.md or a completion report>
```

**Lead with a triage table** so the register is triageable from the first screen:

| Severity | Open | Blocked | Decision |
|---|---:|---:|---:|
| HIGH | | | |
| MED | | | |
| LOW | | | |

**Eviction rule (Rule A):** an entry leaves when it is fixed, when it is superseded, or when it is
re-classified as a by-design note — in which case it moves to the doc that owns the fact.

---

## 6. Phase D — restructure what survives

### 6.1 `docs/Tickets.md` — 945 → ~200

| Problem | Fix |
|---|---|
| 760 lines are the **completed** T0022 block (.1-.9, all ✅) | Move to `archive/Tickets_Archive.md`, as T0022.6 did for every other closed milestone |
| A 20-bullet "Archived completed milestones" list where every bullet links to the same file | Delete. The milestone index table 30 lines above already carries status, goal, and the same link |
| Open work is buried below ~800 lines of closed work | Open milestones first; the index table stays as the top-of-file map |

### 6.2 `docs/MVP_Technical_Design.md` — split along the layer boundary

1,019 lines against a 400-line cap. The clean cut already exists in `Full_Design_Document.md` §3,
which declares ingestion an isolated layer the request pipeline must never import:

| New file | Sections | Lines |
|---|---|---:|
| `MVP_Technical_Design.md` (serving path) | §1-6 lifecycle, agent, contract, data, errors, testing · §9 streaming · §10 hardening · §11 demo | ~620 |
| `Offline_Pipelines_Design.md` (new) | §7 ingestion · §8 evaluation harness | ~330 |

The docs then mirror the architecture instead of cutting across it.

**The 400-line T2 cap is wrong and should be raised to 650,** not worked around. It was set
without measurement; a build blueprint for an eleven-subsystem service does not fit in 400 lines,
and a cap that is breached the day it is written teaches everyone to ignore caps.

### 6.3 The smaller structural fixes

| Doc | Now | Change |
|---|---:|---|
| `docs/Manual_Verification_Guide.md` | 146 | Half the file is a flat 70-item list of ticket IDs. Replace with one sentence and a link to the archive |
| `docs/Agent_Behavior_Spec.md` | 172 | 40 lines of provenance and "NOT LANDED" warning before any content. Lead with a 3-line status box; move provenance to the foot |
| `docs/README.md` | 67 | Four tables state overlapping ownership. Merge into one: **Doc · Owns · Tier · Cap · Reader** |
| `docs/Decision_Log.md` | 222 | Excellent format, but 34 decisions read as 220 lines of scroll. Add a one-line-per-decision index table at the top |
| `docs/Completion_Reports.md` | 1,642 | "Entry format" sits at line 157, between T0022.1 and Milestone 16. Move to the top; leave content untouched |
| `research/job-site-comparison.md` | 528 | VietnamWorks is decided (D-034). Keep the scorecard and the selected source; collapse the ITviec and TopDev deep-dives to verdict + pointer (**decided 2026-08-10**) |
| `research/v1-release-readiness-plan.md` | 362 | Rewrite against current numbering; delete the "read every M22 as M23" banner (Rule B). M20 shipped, M21 is nearly done (**decided 2026-08-10**) |

### 6.4 Two stale claims in canonical docs

- **`MVP_Spec.md` §5** asserts three times that the MVP "runs on a small, fixed sample dataset."
  M9 and M19 shipped real VietnamWorks ingestion with a nightly workflow.
- **`Repo_Current_State.md`** names the working branch, which is stale the moment M22 merges.
  State `main` plus the head SHA instead.

---

## 7. Phase E — make it stick

| Check | Rule | Catches |
|---|---|---|
| `size-cap` | **Ship it.** T1 ≤150, T2 ≤650, T3 ≤250, T4 uncapped | The reason `Known_Issues.md` reached 1,199 lines unnoticed |
| `eviction-rule` | Every capped doc's header states what leaves it | Rule A |
| `amendment` | Warn on `no longer`, `read every`, `correcting an earlier`, `superseded above` outside `archive/**` | Rule B |
| `orphan` | Warn on a tracked `.md` no other doc links to | How a blank template survived 200 lines and zero readers |

`stamp` and `duplicate-heading` are still deferred from phase 1 and stay deferred — the four
above are what this pass proves it needs.

---

## 8. End state

| Surface | Before | After |
|---|---:|---:|
| Markdown files | 53 | **46** |
| Total lines | 19,755 | **~14,400** |
| Lines a person actually reads (T1-T3 + live research) | ~6,700 | **~2,400** |
| `Known_Issues.md` | 1,199 | ~250 |
| `Tickets.md` | 945 | ~200 |
| `research/archive/` | 4,925 | ~3,500 |
| Docs over their tier cap | 4 | **0** |

---

## 9. Ticket sequence — T0022.10-.14

Extending M22 rather than renumbering: the work is thematically identical, and phase 1 already
paid the cost of one renumbering (M22 → M23) whose correction banners §2.1 now cleans up.
**T0023 remains the v1.0 release cut.**

| Ticket | Scope | Depends on | Risk |
|---|---|---|---|
| **T0022.10** | **Prune (§3).** Tag, delete 7 files + `infra/`, repair 4 inbound links, close the Langfuse security entry, reconcile `Full_Design_Document.md` §5 and `Tech_Stack.md`, record the `skills/` reversal (§3.1.1) | .9 merged | Low | <!-- archived-on-tag -->
| **T0022.11** | **Archive collapse (§4).** Collapse 5 research docs to decision records; fix `deployment-research-plan.md`'s stale banner; trim `Code_Review_Notes.md` | .10 | **Medium** — section identity is a citation target |
| **T0022.12** | **Registers (§5).** Harvest the 2 gaps into `Decision_Log.md`; re-triage 46 open entries against code; rebuild `Known_Issues.md` | .11 | **Highest** — needs code reading, not just doc editing |
| **T0022.13** | **Structure (§6).** `Tickets.md` split; `MVP_Technical_Design.md` split; the 7 smaller fixes; 2 stale canonical claims | .10 | Medium |
| **T0022.14** | **Enforcement (§7).** Ship `size-cap`, `eviction-rule`, `amendment`, `orphan`; raise the T2 cap to 650; update `Docs_Conventions.md` with Rules A and B | all | Low |

**Order matters:** prune first so nothing is restructured and then deleted; enforcement last so
the new checks land against an already-clean tree and never start warn-only.

---

## 10. Manual verification

**After T0022.10**
- [ ] `git tag` shows `archive/docs-pre-prune`, and
      `git show archive/docs-pre-prune:docs/Prompt_Playbook.md` prints the deleted file. <!-- archived-on-tag -->
- [ ] `python scripts/docs_lint.py` exits 0 — especially `link-path` and `index`.
- [ ] `skills/generate-ticket-prompt/SKILL.md` is **still tracked** (§3.1.1), and
      `/generate-ticket-prompt` still runs after `Prompt_Playbook.md` is absorbed into it. <!-- archived-on-tag -->
- [ ] `docker compose up -d` still starts app Postgres with `infra/` deleted — it is a <!-- archived-on-tag -->
      separate compose file.
- [ ] Grep for `infra/langfuse` across live docs returns nothing. <!-- archived-on-tag -->

**After T0022.11**
- [ ] Every `Decision_Log.md` section citation still names a section that exists in the
      collapsed file.
- [ ] `git diff --word-diff` shows no *reworded* findings — only removals.

**After T0022.12**
- [ ] `Known_Issues.md` ≤250 lines; no entry over 6 lines; the triage table totals match a
      manual recount.
- [ ] Every entry closed during re-triage has a matching `Resolved_Issues.md` entry that names
      the fixing commit or test.
- [ ] Open `Decision_Log.md` cold and answer *"why Vietnamese job boards?"* without opening
      another file.

**After T0022.13 / .14**
- [ ] `Tickets.md` shows open work within the first screenful.
- [ ] A PR adding 200 lines to `Known_Issues.md` is **blocked** by `size-cap`.
- [ ] A PR adding "this is no longer true" to a living doc **warns** via `amendment`.
- [ ] The newcomer path — `README` → `Tech_Stack` → `Repo_Current_State` — still answers
      what/how/where-now in 10 minutes.

---

## 11. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Collapsing an archive drops a cited section** | **Medium-high** | Citations live in link *text*, so `link-path` cannot catch this. Enumerate every cited section before editing; §4.1 constraint 1 |
| **Re-triage mislabels an open issue as fixed** | Medium | Every closure names the commit or test that fixed it; when evidence is absent the entry stays open |
| **Deleting `infra/` removes a wanted local Langfuse** | Low | Tagged; D-029 already chose Cloud; app Postgres is a separate compose file | <!-- archived-on-tag -->
| **Splitting `MVP_Technical_Design.md` breaks inbound links** | Medium | 6 live docs cite it by section; rewrite in the same commit, `link-path` green before and after |
| **T0022.12 grows into code changes** | Medium | Re-triage *reads* code and *records*. A fix found during triage becomes a follow-up ticket (CLAUDE.md §1) |
| **A fifth cleanup milestone** | Medium | §7 is the answer. Phase 1 decayed nothing because it enforced; the caps it did not enforce are exactly what breached |

---

## 12. Out of scope

- **Rewriting research findings.** Phase 1's non-goal holds: collapse removes, it never rewords.
- **`Tickets_Archive.md` and `Manual_Verification_Archive.md`** — decided 2026-08-10.
- **A docs site, generator, or new dependency.** Plain Markdown in git.
- **`Agent_Behavior_Spec.md`'s unlanded `behavior_glossary`.** A real open item that changes agent
  output; it belongs to the behavior track.
- **The four archived research docs kept at full length** (§4.2), beyond the two harvests and one
  banner fix.
- **Auto-generating `Repo_Current_State.md` from git.** Still premature.
