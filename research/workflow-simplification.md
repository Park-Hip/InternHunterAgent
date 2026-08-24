# Workflow Simplification

> **Status:** research record, written 2026-08-19. No implementation.
> It measures how large the documentation system has grown, identifies which parts of it are
> load-bearing and which are ceremony, and proposes an aggressive prune with a target state.
> It does not restate the generator's contract, which is
> [`docs/entries/README.md`](../docs/entries/README.md), nor re-derive the pipeline's throughput,
> which is [The agentic workflow](agentic-workflow.md).

> **Last verified:** 2026-08-19 against `main` at `cf5027a`, all 83 tracked Markdown files,
> `scripts/docs_lint.py`, `scripts/docs_build.py`, their two test modules, and the external <!-- archived-on-tag -->
> practice sources listed in section 8.

> **Eviction:** A block leaves this record when its prune ships, when a measurement contradicts it,
> or when the target state in section 6 is reached and the record is harvested into
> [`docs/Decision_Log.md`](../docs/Decision_Log.md).

---

## 0. TL;DR

1. **The documentation tooling is 89% the size of the application it documents.**
   2,457 lines of Python across the linter, the generator and their tests, against 2,766 lines in
   `src/`.
2. **28,606 lines of Markdown across 83 files**, 10.3 lines of prose per line of application
   source. 10,015 of those lines already sit in `archive/` and cost nothing, so the live, linted,
   cap-bearing surface is 18,593 lines.
3. **The linter is two tools wearing one name.** Three checks worth 283 lines enforce
   parallel-agent coordination and are genuinely load-bearing. Eleven checks worth roughly 440
   lines police prose style on documents nobody reads.
4. **The three load-bearing checks are the wrong shape.** They detect after the fact what a
   `PreToolUse` hook prevents at the source. Anthropic states the principle directly: an
   instruction is a request, a hook is enforcement.
5. **The prune is unusually safe** because the two biggest targets are verbatim archive moves with
   an existing precedent commit, and because a check that has never fired cannot break when
   deleted.
6. **Target:** 979-line linter down to about 250, 15 checks down to 6, the live surface down from
   18,593 lines to about 9,000, and a ticket entry from 9 sections to 4.
   No coordination guarantee is given up.

---

## 1. Method

Counted every tracked Markdown file with `git ls-files '*.md'` and `wc -l`.
Measured the generated share of each register by parsing its `generated:*:begin` and `:end`
markers.
Sized every lint check by reading the span between consecutive `def check_` statements.
Sampled which checks produce work by grepping all commit messages for each check name, and ran
`scripts/docs_lint.py` against the working tree.
External practice is drawn from the sources named in section 8, read directly rather than
summarised from secondary write-ups.

---

## 2. How big the system actually is

### 2.1 The tooling

| Component | Lines | What it is |
|---|---:|---|
| `scripts/docs_lint.py` | 979 | 15 checks |
| `tests/test_docs_lint.py` | 650 | Tests for those checks |
| `scripts/docs_build.py` | 496 | Renders entries into 4 registers | <!-- archived-on-tag -->
| `tests/test_docs_build.py` | 332 | Tests for the generator | <!-- archived-on-tag -->
| **Total** | **2,457** | |
| `src/` for comparison | 2,766 | The application |

The documentation machinery is 89% the size of the product.
That ratio is the single clearest signal that the system has outgrown its purpose, and it is the
number to watch after the prune.

### 2.2 The prose

83 tracked Markdown files, 28,606 lines. The distribution is heavily concentrated:

| File | Lines | Note |
|---|---:|---|
| `docs/Completion_Reports.md` | 4,839 | 3,030 hand-written legacy, 1,809 generated |
| `docs/archive/Tickets_Archive.md` | 4,379 | Already archived |
| `docs/archive/Manual_Verification_Archive.md` | 1,444 | Already archived |
| `docs/Resolved_Issues.md` | 917 | Closed history, still live and linted |
| `research/archive/deployment-research-plan.md` | 892 | Already archived |
| `research/docs-hygiene-and-system-plan.md` | 814 | Research about documentation hygiene |
| `docs/MVP_Technical_Design.md` | 726 | | <!-- archived-on-tag -->
| `docs/T0020.4_Cron_Activation_Runbook.md` | 594 | The cron it gates closed on 2026-08-17 |
| `research/docs-prune-and-structure-plan.md` | 464 | Research about pruning documentation |

The top nine files carry 15,069 lines, 53% of all Markdown in the repository.
Six of those nine are history that is complete, or documentation about documentation.

There are 1,278 lines of live research explaining how to keep documentation small.
That is not an argument against those records, which produced the caps table and the entries
split, both of which work.
It is an observation that the meta-layer is now large enough to be a prune target itself.

---

## 3. The linter is two tools

Sizing each check by lines of implementation separates them cleanly.

### 3.1 Coordination checks: load-bearing

| Check | Lines | What it guarantees |
|---|---:|---|
| `frozen` | 167 | A ticket agent did not write a shared register |
| `scope` | 72 | A ticket stayed inside its declared paths |
| `generated` | 44 | Committed regions match the entries they derive from |
| **Total** | **283** | 29% of the linter |

These earn their place.
They are the enforcement behind the parallel-agent design, and section 3 of
[`CLAUDE.md`](../CLAUDE.md) is unenforceable prose without them.
Nothing below proposes weakening the guarantee.

### 3.2 Referential integrity checks: keep, they catch real drift

| Check | Lines | What it catches |
|---|---:|---|
| `scenario-id` | 91 | A documented scenario ID the registry does not define |
| `link-path` | 32 | A repository path reference that no longer resolves |
| `encoding` | 23 | Mojibake and BOMs from a PowerShell round-trip |
| `stack` | 20 | A dependency claim that disagrees with `pyproject.toml` |
| **Total** | **166** | |

Each of these compares a document against a machine-readable source of truth.
That is the only kind of documentation check that cannot be satisfied by writing worse prose, and
all four should survive.

### 3.3 Prose policing: the overengineering

| Check | Lines | Commit mentions | Assessment |
|---|---:|---:|---|
| `line-length` | 59 | 3 | Enforces a 100-character wrap. Protects the readability of documents with no readers. |
| `stamps` | 52 | 37 | Requires a `Last verified:` date on 8 documents. The date is typed by an agent, so it attests to nothing a reader can rely on. |
| `orphan` | 34 | 16 | Requires an inbound link. Its only current finding is a false positive on a research file written today. |
| `size-cap` | 26 | 3 | Per-file line caps from `docs/README.md`. |
| `amendment` | 18 | 3 | Greps for `no longer`, `read every`, `correcting an earlier`, `superseded above`. |
| `agent-parity` | 12 | 0 | Checks `CLAUDE.md` and `AGENTS.md` are identical. Has never fired. |
| `eviction-rule` | 12 | 1 | Requires an `Eviction:` header line on capped documents. |
| **Total** | **213** | | |

Add the roughly 230 lines of shared scaffolding these checks need and the prose-policing layer is
close to 440 lines, plus its share of the 650-line test module.

The case against them is not that the conventions are wrong.
It is that the caps failed at the job they were built for.
`size-cap`, `eviction-rule` and `amendment` were added under M22 to stop documentation growth.
Documentation has since grown to 28,606 lines.
They cap individual files while growth arrives as new files, so the constraint binds on the wrong
axis.

`agent-parity` deserves its own note because it is the clearest example of the pattern.
It spends 12 lines detecting that two byte-identical files have diverged.
Generating `AGENTS.md` from `CLAUDE.md` makes divergence impossible and deletes the check, the
test, and the rule from both files at once.

To be explicit, because this repository is worked by both Claude Code and Codex: generation writes
the full text into `AGENTS.md`, byte for byte.
It does not replace the file with a pointer to `CLAUDE.md`, which would leave a Codex session
reading a stub.
The standing rule that both files carry the same content is preserved; what changes is that a
generator keeps it true instead of two agents remembering to.

---

## 4. The structural error: detection where prevention belongs

Anthropic's guidance states the principle without hedging:

> An instruction like "never edit `.env`" in CLAUDE.md or a skill is a request, not a guarantee.
> A `PreToolUse` hook that blocks the edit is enforcement.
> If a rule must hold every time, make it a hook rather than a prompt instruction.

Measured against that, all three coordination checks are the wrong shape.
Each one lets the agent make the mistake, lets it reach CI, and then reports it minutes later.

| Rule | Today | Cost | Should be | Cost |
|---|---|---:|---|---:|
| Ticket agents do not write frozen registers | `check_frozen`, reported by CI | 167 | `PreToolUse` hook on Write/Edit matching the 8 frozen paths, blocks the edit | ~15 |
| A ticket stays inside its declared scope | `check_scope`, reported by CI | 72 | `PreToolUse` hook reading `scope:` from `roadmap.yaml` | ~20 |
| Generated regions match their entries | `check_generated`, reported by CI | 44 | `Stop` hook running `docs_build.py`, exit 2 to keep the turn going | ~10 |
| **Total** | | **283** | | **~45** |

The saving is 238 lines, but the behaviour change matters more than the line count.
A blocked edit is a non-event.
A CI finding is a red build, a context switch, a fix commit and a re-run, and
[The agentic workflow](agentic-workflow.md) section 4.4 already measured the consequence:
the documentation gate is the most frequently failing step in the entire pipeline, it blocks
nothing, and the M33 integration session hand-filtered its findings six times.

Prevention also removes the false-positive class that made hand-filtering necessary.
`is_integration()` reads committed subjects in `origin/main..HEAD`, so an uncommitted working tree
reports every frozen register the integrator is entitled to edit as a violation.
A `PreToolUse` hook reads the session, not the commit log, and has no such blind spot.

---

## 5. What git and CI already carry

The entry format has nine sections. Four duplicate a machine-readable source.

| Section | Already available from | Verdict |
|---|---|---|
| `## Files` | `git show --name-only`, or the PR file list | Drop. Git is more accurate: the register's own header calls its paths "dated evidence rather than a live index" because later tickets move files. |
| `## Build and test` | The CI run attached to the PR | Drop. A sentence claiming tests passed is a weaker artifact than the run that proves it. |
| `## Commands` | `Repo_Current_State.md`, Available scripts | Drop. Written 25 times, re-run approximately never. |
| `## Docs` | Nothing, and it needs nothing | Drop. It is an instruction to the integration session, consumed once on merge. |
| `## Summary` | PR title and body, commit subjects carrying the ticket id | Move into the PR body. Merged PR bodies currently measure 328 to 692 characters, so the register is richer than git today and the move must come first. |
| `## Follow-ups` | `roadmap.yaml` or `Known_Issues.md` | Route. If it reached either register it is duplicated here; if it did not, nobody will ever find it. |
| `## Risks` | Nothing | Keep. The author's judgment at the moment of shipping is not reconstructible. |
| `## Known issues` | Its own register, with ids and dedup | Keep. Already routed correctly. |
| `## Manual verification` | Its own register, with an eviction rule | Keep. See the caveat in section 7. |

The pattern worth naming: every section that earns its place already has a dedicated register.
Only `Risks` has no home but the completion report.
Which is the honest case for shrinking `Completion_Reports.md` to a generated index rather than a
document.

You have already made this decision once.
`docs/archive/Completion_Reports_Archive.md` holds M0 to M14 and its header states the principle:

> Entries are condensed to the durable summary; the full implementation detail lives in the code
> and git history.

That was settled at M14 and stopped being applied at M16.

---

## 6. The target state

### 6.1 Tooling

| Component | Now | Target | How |
|---|---:|---:|---|
| `docs_lint.py` | 979 | ~250 | 6 checks: `scenario-id`, `link-path`, `encoding`, `stack`, `registry`, plus one repo-level size check |
| `tests/test_docs_lint.py` | 650 | ~180 | Tests follow the checks out |
| `docs_build.py` | 496 | 496 | Unchanged. The generator is the part that works. |
| `tests/test_docs_build.py` | 332 | 332 | Unchanged | <!-- archived-on-tag -->
| `.claude/settings.json` | 0 | ~45 | Three hooks replacing `frozen`, `scope` and `generated` |
| **Total** | **2,457** | **~1,300** | 47% reduction |

`check_registry` (147 lines) stays in the linter rather than becoming a hook.
It validates `roadmap.yaml` against itself, which is a data-integrity check with no lifecycle event
to hang on.

### 6.2 Documents

| Action | Lines out of the live surface |
|---|---:|
| Archive `Completion_Reports.md` lines 1 to 3,030 | -3,030 |
| Archive `Resolved_Issues.md` | -917 |
| Archive `T0020.4_Cron_Activation_Runbook.md`, its cron closed 2026-08-17 | -594 |
| Archive `docs/entries/` for milestones already folded and integrated | ~-2,400 |
| Merge 7 design documents into 2, keeping the frozen contracts separate | ~-900 |
| Archive `docs-hygiene-and-system-plan.md` and `docs-prune-and-structure-plan.md` once this record supersedes them | -1,278 |
| Trim the hand-written narrative in `Repo_Current_State.md` | ~-120 |
| **Total** | **~-9,240** |

The **live, linted, cap-bearing surface** falls from 18,593 lines to roughly 9,350, a little over
half.

Total Markdown in the repository barely moves, because archiving relocates rather than deletes;
only the design merge removes text, and only about 900 lines of it.
That is the point.
The cost of a document is not the disk it occupies, it is whether the linter reads it, whether a
cap has to be kept true against it, and whether two branches can collide on it.
Moving a file into `archive/` takes it out of all three.

Nothing in that table deletes information.
Every line is either moved into `archive/`, which
[`docs/Docs_Conventions.md`](../docs/Docs_Conventions.md) already exempts from the caps and the
orphan check, or merged into a surviving document.

### 6.3 The design-document merge

Seven documents hold 1,830 lines describing the same system:

| Document | Lines | Disposition |
|---|---:|---|
| `MVP_Technical_Design.md` | 726 | Merge into `Design.md` |
| `Offline_Pipelines_Design.md` | 323 | Merge into `Design.md` |
| `Full_Design_Document.md` | 179 | Merge into `Design.md` |
| `MVP_Spec.md` | 121 | Merge into `Design.md` |
| `Tech_Stack.md` | 144 | Merge into `Design.md`, the dependency list is generated anyway |
| `Agent_Behavior_Spec.md` | 221 | Keep. Frozen contract, referenced by the eval registry. |
| `Schema_Contract.md` | 116 | Keep. Frozen contract, referenced by the grader. |

A contract that another machine reads stays its own file.
A description that only a human reads merges, because five documents describing one system is five
places for the description to drift.

### 6.4 The ticket entry

Nine sections become four: `Plan`, `Risks`, `Known issues`, `Manual verification`.
`Summary` moves into the PR body, which is where the field puts it and where GitHub already renders
it next to the diff.

This also gives `## Plan` a job.
The entries contract currently renders it to nothing, and section 3 of
[The agentic workflow](agentic-workflow.md) has no gate on it at all.

---

## 7. Two findings that are fixes, not prunes

**The manual-verification lifecycle is not being exercised.**
Of 25 completed entries, 14 are `verified: no`, 10 `yes` and 1 `partial`.
Since the eviction rule for a checklist is that flag, 14 checklists can never leave
`Manual_Verification_Guide.md`.
The register is not redundant; it is a lifecycle with a stalled queue.
Either run the checks and flip the flag, or stop writing checklists for tickets that will not be
verified by hand.
Writing a check nobody runs is the documentation equivalent of a test that is always skipped.

**The review gate is in the wrong place, and this record does not fix it.**
Every external source places the human gate on the plan, before implementation.
The repository places it on the PR diff.
That is a workflow change rather than a prune, it is out of scope here, and it is recorded in
[The agentic workflow](agentic-workflow.md) section 8 so it is not lost.

---

## 8. What this was measured against

External practice, read directly:

- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices) - the
  verification loop, hooks as enforcement rather than request, and the CLAUDE.md pruning test:
  "For each line, ask: would removing this cause Claude to make mistakes? If not, cut it."
- [Extend Claude Code](https://code.claude.com/docs/en/features-overview) - the decision table for
  CLAUDE.md against skills, hooks and subagents, the 200-line CLAUDE.md guidance, and
  `.claude/rules/` with `paths` frontmatter as a way to scope rules without loading them every
  session.
- [Advanced Context Engineering for Coding Agents][ace-fca], the `ace-fca.md` record - research,
  plan, implement, and reviewing the plan rather than the code.
- [Codex best practices](https://developers.openai.com/codex/learn/best-practices) - Goal, Context,
  Constraints, Done-when, and AGENTS.md as the durable configuration lever.
- [Spec Driven Development: What It Fixes (and Breaks)][sdd] - the failure mode this record is
  written against: "running every phase gate on a one line CSS fix, and treating the human review
  step as a rubber stamp instead of an actual check."


[ace-fca]: https://github.com/humanlayer/advanced-context-engineering-for-coding-agents
[sdd]: https://dev.to/mudassirworks/spec-driven-development-what-it-fixes-and-breaks-1co3

In-repo evidence: all 83 tracked Markdown files, `scripts/docs_lint.py`, `scripts/docs_build.py`, <!-- archived-on-tag -->
`tests/test_docs_lint.py`, `tests/test_docs_build.py`, `docs/README.md`'s caps table, <!-- archived-on-tag -->
`docs/entries/README.md`, `.github/workflows/ci.yml`, and the frontmatter of all 26 ticket entries.

---

## 9. Sequencing

The prune has a dependency order, because two steps make later ones cheaper.

| Step | Change | Why it comes here |
|---|---|---|
| 1 | Write the three hooks into `.claude/settings.json` | Nothing else can be deleted until prevention exists |
| 2 | Delete `frozen`, `scope`, `generated` and their tests | Now redundant with step 1 |
| 3 | Delete the 7 prose-policing checks, generate `AGENTS.md` from `CLAUDE.md` | Independent of everything else |
| 4 | Archive: legacy reports, resolved issues, the cron runbook, folded entries | Verbatim moves, precedent exists |
| 5 | Merge the 5 design documents | Needs a careful read, do it once and slowly |
| 6 | Slim the entry format to 4 sections, move `Summary` into PR bodies | Changes the contract, so it needs the registers quiet first |
| 7 | Rewrite the caps table against the surviving documents | Last, because everything above changes the numbers |

Steps 1 to 4 are mechanical and safe.
Step 5 is the only one that risks losing content, and it is the only one that should not be done by
an agent unsupervised.

---

## 10. Open items

| Item | Status |
|---|---|
| Three hooks in `.claude/settings.json` | Proposed, needs a ticket number |
| Deleting 10 of 15 lint checks | Proposed, needs a maintainer decision on the prose conventions |
| Generating `AGENTS.md` from `CLAUDE.md` | Proposed; removes a rule, a check and a test together |
| Archiving 4 registers and the folded entries | Proposed, integration-session work, precedent commit `8359c67` |
| Merging 5 design documents into `Design.md` | Proposed, needs a supervised session |
| 14 entries at `verified: no` | Open, from section 7 |
| Moving the review gate onto the plan | Out of scope here, tracked in [The agentic workflow](agentic-workflow.md) |
