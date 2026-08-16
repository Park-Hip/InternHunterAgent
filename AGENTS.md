## 1. General Operational Rules
These rules apply to every ticket and interaction to ensure we maintain control over the
repository's scope and quality.

* Implement one ticket only.
* Do not implement future-ticket features.
* Do not refactor unrelated systems.
* Do not introduce new architecture unless explicitly required by the ticket.
* Avoid unnecessary dependencies.
* Run build/tests when possible before finalizing.
* Report all follow-ups or out-of-scope issues separately; do not fix them automatically.
* Never over-engineer a problem, find a suitable solution to the MVP.
* Models should be seperated in models.py
* Paramters must be set at config/settings.yaml
* Before designing, planning, or implementing any stage, read `docs/Decision_Log.md`, then the
  relevant document in `research/` (start at `research/README.md`). It holds the pre-design
  research,
  live-tested facts, and ruled-out dead-ends behind each decision - do not re-derive what is already
  recorded there.
* Before changing Markdown documentation, read `docs/Docs_Conventions.md` and follow its ownership,
  verification-stamp, and lint-exemption rules.

## 2. Architecture-Specific Rules
This project is a React-style MVP utilizing FastAPI, LangChain, and Langfuse. Strict adherence to
these architectural boundaries is required.

* Maintain strict layer isolation: Keep the API layer, Application service, Agent runtime, and
  Tracing layer entirely separated.
* API Agnosticism: The API layer must not know how the agent is built internally.
* Route Constraints: FastAPI routes must never own LangChain logic directly.
* Tracing Boundaries: Keep tracing localized to its respective layer; do not let Langfuse or tracing
  concerns leak across the entire codebase.


## 3. Parallel Work Protocol
Sessions run in parallel and share one repository. These rules exist so two agents can finish on
the same day without touching the same lines.

**Identity comes from the registry, never from a document.**
* `docs/roadmap.yaml` is the sole owner of ticket and milestone numbers. Read it first.
* Never infer the next free number from `docs/Tickets.md`. If your work has no entry in
  `roadmap.yaml`, stop and ask for one; do not allocate your own.
* Milestone N owns tickets T00NN.x. One number, claimed once, before work starts.

**Stay inside your declared scope.**
* Your milestone's `scope:` in `docs/roadmap.yaml` lists the paths you may change. Widening it is a
  one-line edit in the same PR - make the edit deliberately, do not drift past it silently.
* Before running agents in parallel, intersect their scopes. A non-empty intersection means the
  tickets are not independent and must be sequenced.

**Branch off `main`, never off another branch.**
* Every ticket branch starts at the tip of `origin/main`. If your ticket needs another ticket's
  unmerged code, it is not parallelizable - sequence it instead.
* One PR per ticket, targeting `main`. Open it within a day of starting; a branch that lives longer
  accumulates other tickets and stops being reviewable on its own.
* Rebase onto `origin/main` before opening the PR and before each re-review. Never merge `main`
  into a ticket branch.

**Write to your own file, not to shared registers.**
* The `frozen:` list in `docs/roadmap.yaml` names the registers only the integration step writes.
  A ticket agent does not edit them.
* Everything a ticket has to record goes in one file under `docs/entries/`, named for your ticket,
  on a path no other branch owns. See [`docs/entries/README.md`](docs/entries/README.md) for the
  naming rule and the format.

**Work in your own git worktree.**
* Any session that will write to the repo (edit files, run builds or tests that mutate state) must
  work in its own git worktree. Read-only sessions do not need one.
* A worktree isolates the filesystem, not the logical scope. Both rules apply.

## 4. Manual Verification
* Always add manual verification that the developer can test after make changes not just  "build
  passed".
* Every ticket should have a small manual checklist.


## 5. Completion Report Requirement
At the end of every ticket execution, write the completion report as `## ` sections in your own
file under `docs/entries/`. Do not edit `docs/Completion_Reports.md`; the integration step folds
your entry into it. The report must strictly include:

* Summary of changes.
* Files created, changed, or modified.
* Commands executed/run.
* Build and test results.
* Specific manual verification steps required to validate the ticket.
* Risks.
* Follow-up tickets.
* Docs that need updating.

Anything you would have added to `docs/Known_Issues.md` goes in your entry's `## Known issues`
section instead, for the same reason.

## 6. Repo-State Updates
`docs/Repo_Current_State.md` is frozen against ticket agents: it is the repository's single
mutable snapshot, and one writer per merge is the only way it stays true. Record the same facts in
your entry file and let the integration step publish them:

* Current branch.
* Completed tickets.
* Current folder structure.
* Installed dependencies.
* Available scripts.
* Build/test status.
* Known issues — do not list these inline; they belong in your entry's `## Known issues` section,
  which the integration step files into `docs/Known_Issues.md` (the living register).
* Next recommended ticket.

## 7. Integration Step
One writer, run once per merge to `main`, by the maintainer or a session doing nothing else. This
is the only place the `frozen:` registers change.

1. Merge the PR. If several are ready, merge them one at a time.
2. Fold each new file under `docs/entries/` into the registers it belongs to: the completion
   report into `docs/Completion_Reports.md`, `## Known issues` into `docs/Known_Issues.md`,
   the manual checklist into `docs/Manual_Verification_Guide.md`, the milestone outcome into
   `docs/Tickets.md`, and archive the ticket plan when its milestone closes.
3. Rewrite `docs/Repo_Current_State.md` against the merged tree, and re-stamp `Last verified:`.
4. Set the milestone's `status:` in `docs/roadmap.yaml`, and move any cap that now binds.
5. Run `python scripts/docs_lint.py` and commit as one `docs(integration):` commit.

Step 2 and step 3 are mechanical and are being replaced by a generator under M31; until it lands,
they are done by hand.
