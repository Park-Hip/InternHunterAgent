# Issue sweep against the refactored tree

> **Last verified:** 2026-10-02, at `61af59b`
>
> **Eviction:** This is a point-in-time verdict record. Re-run the sweep when a refactor milestone
> merges, when a gate row changes, when a serving flag flips, or when roughly twenty issues
> accumulate without a maintainer decision. A later sweep replaces this file rather than editing it.

This is the recorded verdict of [the issue sweep](https://github.com/Park-Hip/InternHunterAgent/issues/558),
run against the tree at `61af59b`.

Every verdict rests on a fact about the current code, configuration, or database.
The evidence is in the closure comment on each issue, as the command and its result rather than a
restatement of the issue body.

## The baseline

The sweep's precondition was a green suite. It was not green, and the cause was a live blocker the
issue itself had already predicted.

| | Before | After |
| --- | --- | --- |
| `uv run pytest -q` | 972 passed, 15 skipped, **87 errors** | **1074 passed, 12 deselected, 0 skipped, 0 errors** |

All 87 errors were one teardown defect, fixed in [#559](https://github.com/Park-Hip/InternHunterAgent/pull/559)
which closes [#525](https://github.com/Park-Hip/InternHunterAgent/issues/525).
The after figure is with a disposable PostgreSQL 16 behind `SCRATCH_DATABASE_URL`, so the 15
previously skipped integration tests ran instead of being reported as a green suite.

The suite is green. Every verdict below that rests on a test result is therefore falsifiable, which is
the condition the sweep set for itself.

## Four facts about the tree that changed the board

1. **Serving crossed over to v0.** `config/settings.yaml:33` sets `agent.agent_v0: true`, and
   `src/agents/mcp/job_server.py::create_job_mcp_server` registers exactly one tool when it is on.
   An issue about the legacy `query_clean_jobs` / `get_job_details` pair describes a path no user
   reaches, except through the one-line rollback.
2. **The evaluation harness was rebuilt.** `evals/` is 12 modules ending in `run.py` and `v0_gate.py`.
   `harness.py`, `replay.py`, and the v1 registry are gone.
3. **Two issues were delivered by work filed after them.** #521 was implemented by `6fdbc92`, which
   narrowed the `docs_lint` exemption to `evals/archive/` alone.
4. **One claimed premise is false.** #553 asserts `.env` carries `DEEPSEEK_API_KEY` and
   `GROQ_API_KEY`. There is no `.env` in this repository.

## Board movement

35 open issues before the sweep. Every one carries a verdict with its evidence.

### Closed, 6

| Issue | Why | The check that decides it |
| --- | --- | --- |
| [#525](https://github.com/Park-Hip/InternHunterAgent/issues/525) | Defect real and now fixed | `uv run pytest -q` went 972 passed / 87 errors to 1074 passed / 0 errors |
| [#521](https://github.com/Park-Hip/InternHunterAgent/issues/521) | Delivered by work filed after it | `6fdbc92` narrowed `docs_lint.py` to `is_archive` and moved 15 stale manuals into `evals/archive/` |
| [#225](https://github.com/Park-Hip/InternHunterAgent/issues/225) | Defect no longer reproduces | `health.py::get_data_snapshot_date` returns `data_snapshot_date_provenance`; `tests/api/test_ready.py:58` pins `"configured_fallback"` |
| [#213](https://github.com/Park-Hip/InternHunterAgent/issues/213) | Absorbed by a contract the refactor introduced | `build_manifest`, `prompt_hash`, `config_hash`, and `_assert_comparable` no longer exist; prompt surfaces are identified by a release-pinned version string |
| [#407](https://github.com/Park-Hip/InternHunterAgent/issues/407) | Superseded by a recorded decision | `f20e688` removed the gate; `ci.yml` has no gate job; `docs/how-to/release-gate.md` reads Retired |
| [#419](https://github.com/Park-Hip/InternHunterAgent/issues/419) | Subject is outside this repository | The target is `D:/DevBrain/remote-blog/30_Resources/LangChain.md`, a personal vault, not this tree |

### Kept and ranked, 5

#404, #550, #551, #556, #175.

### Kept, re-targeted or re-scoped, 4

#180, #403-equivalent naming corrected in #404, #447, #553.

### Kept, blocked on a named condition, 5

#121 on #137, #131 on a live model probe, #447 on the component-index update,
#517 on #553, #553 on provider credential and spend authorization.

### Kept as a decision surface, 9

#117, #137, #321, #409, #457, #468, #479-equivalent superseded by #501,
#501, #504.

### Kept, defect confirmed against the current tree, 6

#122, #123, #127, #131, #179, #524.

## The ranked shortlist

Ranked by effort against value, with reachability first.
A cheap user-visible defect outranks an architectural proposal regardless of age.

### 1. #404 - the served tool leaks raw column names into the answer

User-visible, on the served path, and one function.

`_row_lines` in `src/agents/tools/v0_query_jobs.py:221` renders every column as `key=value`,
including the surrogate `id`. Measured by calling it:

```
- id=18, title=AI Expert, company_name=Viettel High Tech, location=Hanoi, salary_min=2500
```

The issue names `src/agents/tools/get_job_details.py:53`, which has the same defect, but that is the
legacy tool and `agent.agent_v0: true` means no user reaches it.
This is the same class as #359, which measured the answer quoting `listing_expires_on` to the user
and failing `no_schema_identifier_leak`.

**Ranked first because** it is the cheapest live user-visible defect on the board, and it shares a
root cause with a second open issue, so one fix closes a class rather than an instance.

### 2. #550 - a two-minute turn with no visible progress

The user reads a disabled composer as a hang, and presses Stop on a turn that was about to succeed.
Reproduced E2E in the issue body with real SSE captures; a turn takes about 120s.

The issue already splits itself into four independent pieces, and piece **D** is two lines:

```js
turn.appendChild(you);
turn.appendChild(agent);
conversation.appendChild(turn);            // line 138 - announces here
conversation.setAttribute("aria-busy", "true");  // line 141 - mutes here
```

With `aria-relevant="additions text"`, the append announces before the log is muted, so a turn likely
produces two utterances rather than the one #496 promised.
That is an accessibility defect, not a polish item, and it is the cheapest item on this list.

### 3. #551 - the tool card shows no evidence

`format_arguments` in `src/agents/runtime/tool_events.py:50-62` collapses any dict, list, tuple, or
set to `…`, so the only bound tool renders as `query_jobs  request: …  412 ms`.
It erases the fields that carry evidence and preserves the one field that does not.

`QueryResult.applied` already holds the resolved criteria with a `basis` that distinguishes a literal
filter from a vocabulary fallback. It is computed one layer up in `src/services/query/` and thrown
away at the rendering boundary.

**Blocked on one decision** before implementation, stated in the issue: does the `tool` event gain a
`criteria` field? That is a contract change and needs a proposal. Parts 1 and 2 need none.

Note the gap #551 filed as #554 is now closed. `publish_tool_result` is called from
`v0_query_jobs.py:107,126,128` since #557 merged, so the no-answer card is reachable on the served
path.

### 4. #556 - no English coverage for any honesty arm

Measured on the live registry:

```
$ grep -o "language: \w+" evals/datasets/scenarios.yaml | sort | uniq -c
    49 language: vi
```

Zero English scenarios. A regression in `NEGOTIABLE-SALARY`, `FRESHNESS_REFUSAL`, or the
currency-scope behaviour would not be caught on the English path at all.
Evaluation registry only; no runtime change.

### 5. #447 - separate command configuration from serving configuration

The refactor's own ordered item 2, and the one slice everything else queues behind.

**Blocked, and the block is easy to miss.** #445 is closed. Its own body reads
*"Blocked by: #445 completion **and** the corresponding active-backlog/component-index update."*
The second clause is unmet: `docs/refactor/component-index.md` is still dated 2026-09-25 and its
"Current next action" still says *"create and approve one focused proposal to replace the
application's concrete tracing dependency"* - which #445 did.
**#447 is not ready, and the index update is a five-line documentation fix.**

## Blockers, named

| Blocker | Blocks | Unblock condition |
| --- | --- | --- |
| No serving-model credential and no spend authorization | #553, #517 Part One | A maintainer authorizes one run and names the deployment |
| No production traffic | #517 Part One row 1 | The first N real requests after launch |
| `component-index.md` not updated after #445 | #447, then every later serving-path slice | Update the index, or record the agent-v0 exception there |
| Bright Data G2 row names one exposed key; #470's is tracked in no issue | #504, D9 | An issue covering both keys |
| No LICENSE file, and `pyproject.toml` declares no license | #409 | The maintainer recorded MIT on 2026-09-18; only the file and metadata are missing |

## What this sweep did not do

- No gate row moved. `docs/refactor/ingestion-gate-register.md` still reads 9 of 10 **Not met**, which
  is the accurate state.
- No closed issue was reopened.
- No fix was written except #525, whose teardown blocked the precondition for the sweep itself.