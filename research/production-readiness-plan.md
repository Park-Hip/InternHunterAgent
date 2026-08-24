# Production Readiness Plan - M27 to M29

> **Status:** design record, written 2026-08-16. No implementation.
> It feeds three new milestones - **M27 Serving Reliability**, **M28 Operational Telemetry &
> Quality Gate**, and **M29 Production Evaluation Loop** - indexed in
> [`docs/Tickets.md`](../docs/Tickets.md).
> It does not restate M24, whose design already exists in
> [`honesty-enforcement-design.md`](honesty-enforcement-design.md); it sequences around it.

> **Last verified:** 2026-08-16 against the deployed service, the checked-out tree, and
> [`evals/archive/v1_error_analysis.md`](../evals/archive/v1_error_analysis.md).

> **Eviction:** A block leaves this plan when its ticket records a completion report, or when a
> measurement contradicts the evidence the block rests on.

---

## 0. TL;DR

The repository holds a measurement instrument that is at or above the current production standard.
Everything it measures happens **offline**.
Nothing observes, scores, or protects the **running service**, and on 2026-08-16 the running
service stopped answering without anything in the repository noticing.

Three milestones close that, in order:

| Milestone | Closes | Gate |
|---|---|---|
| **M27 Serving Reliability** | The service answers, and stops silently when it does not | A canary run that fails loudly |
| **M28 Telemetry & Quality Gate** | No cost, latency, or regression signal exists | CI fails on a pass-rate drop |
| **M29 Production Evaluation Loop** | Live turns are never scored and never become cases | A live turn promoted into the registry |

M24 keeps its place ahead of all three for behaviour, and M23 keeps the release cut.
M27 is the exception: it is an outage response and precedes everything.

---

## 1. The evidence

### 1.1 The deployed service does not answer

Probed directly on 2026-08-16 against <https://internhunteragent.onrender.com>.

| Probe | Result | Reading |
|---|---|---|
| `GET /api/v1/health` | `200`, `api: online` | The process is up and Render is serving. |
| `GET /api/v1/ready` | `200`, `data_snapshot_date: 2026-08-16` | Nightly ingestion is working, same-day fresh. |
| `POST /api/v1/agent/chat/stream` | SSE opens, then `event: error` | The turn fails before a single token. |
| Both built-in demo prompts | `BUSY_MESSAGE` | Reproducible, not transient. |

The returned string is `BUSY_MESSAGE`, which only `ProviderBusyError` raises.
`classify_provider_busy_error` in `src/core/errors.py` returns `None` for any psycopg error, so
the database is excluded by construction.
That leaves the model provider, and three candidates ordered by cost to rule out:

1. The `GROQ_API_KEY` is invalid or revoked.
2. The `qwen/qwen3.6-27b` pin is no longer served.
   [`Known_Issues.md`](../docs/Known_Issues.md) already carries this exact risk as open and <!-- archived-on-tag -->
   unconfirmed, recorded during T0011.5 preparation.
3. The Groq free-tier daily budget is exhausted.
   One turn reserves roughly 9.2K tokens across routing, SQL generation, and synthesis, so a low
   tens of visitor turns consumes a 200K daily allowance.

This is the same `INFRA_EMPTY_ANSWER` class that
[`evals/archive/v1_error_analysis.md`](../evals/archive/v1_error_analysis.md) ranks first by
frequency times severity, at 8 turns and a score of 24.
The instrument found and ranked the failure mode.
Nothing carried that finding to the serving path.

### 1.2 What the repository already meets

These are recorded so no milestone below tries to rebuild them.

| Capability | Evidence |
|---|---|
| Per-stage evaluation | Three seams captured and graded independently in `evals/harness.py` |
| Execution accuracy | Generated and reference SQL executed and compared as unordered multisets |
| Free re-grading | Capture and grade split, so the CI gate spends no model, judge, or network call |
| Measurement integrity | `INFRA` and `UNRUN` excluded from pass-rate denominators |
| Judge calibration | 13 of 13 audited turns agree with human labels |
| Deterministic guardrails | Single-table allowlist, verb denylist, catalog block, literal masking |
| Failure analysis | 73 answers open-coded into 15 ranked modes |

### 1.3 Where the gap actually is

| Gap | Today | Owning milestone |
|---|---|---|
| Provider failure takes the service down | Retries only, no fallback provider | M27 |
| Nothing watches the deployed service | No canary, no alert | M27 |
| No cost or latency figure exists anywhere | Viewer prints no telemetry for a turn | M28 |
| A quality regression can merge green | Replay covers 5 turns, no threshold fails the build | M28 |
| Live turns are never scored | Traces are recorded, never judged | M29 |
| No user feedback signal | No rating, no retry or abandonment capture | M29 |
| A live failure never becomes a test case | The registry only grows by hand | M29 |

---

## 2. The organising finding

Every capability the repository already meets is **offline**.
Every gap is **online**.

The instrument was built to a high standard and never pointed at production.
That single sentence is the whole remaining distance, and it is why these three milestones are
one coherent piece of work rather than a feature list.
It also sets their order: restore the signal, then measure it, then close the loop on it.

---

## 3. M27 - Serving Reliability

**Objective.** The deployed service answers a visitor's question, and when it cannot, a scheduled
check says so before a visitor does.

**Why it precedes everything.** M23 cuts a v1.0 release.
Cutting a release while the deployed demo returns an error on both of its own sample prompts
records a tag against a service that does not work.

### T0027.1: Diagnose and restore the serving path

**In scope.** Establish which of the three causes in section 1.1 is live, by elimination in the
listed order.
Record the finding in [`Known_Issues.md`](../docs/Known_Issues.md) with its evidence. <!-- archived-on-tag -->
Restore answering on both sample prompts and confirm by direct probe, not by reading logs.

**Out of scope.** Any provider or model change beyond what restoration requires.
That belongs to T0027.2.

### T0027.2: Cross-provider failover

**In scope.** A configured fallback provider in `config/settings.yaml`, selected when the primary
raises `ProviderBusyError`.
The selection belongs in `src/agents/runtime/provider.py`, behind the existing provider seam, so no
route or tool learns that a fallback exists.
Record which provider served each turn so a capture cannot silently mix two models.

**Out of scope.** Routing by cost or latency.
Choosing a permanent primary - that is a measured decision M28 enables, not a guess made here.

**Prior evidence.** A non-Groq provider has already been observed on this repository's own
scenario load at a cost of a few cents for a full pass, so the failover path is affordable to
exercise.
Confirm that figure during T0028.1 rather than carrying it forward as an assumption.

### T0027.3: Synthetic canary against the live endpoint

**In scope.** One scheduled request to the deployed `/api/v1/agent/chat/stream` asserting that a
known question returns a non-error answer.
It fails loudly.
The nightly ingestion workflow and the windowed keep-alive ping already establish the scheduling
pattern, so this adds a check, not infrastructure.

**Out of scope.** A full scenario run against production.
The canary answers "is it serving", not "is it correct".
Correctness against a live corpus has no frozen reference to grade against, which is precisely why
the fixture exists.

### Milestone gate

Both demo prompts answer on the public URL, a provider outage is survivable, and a failure to
serve produces a signal without a human clicking the demo.

---

## 4. M28 - Operational Telemetry & Quality Gate

> **Renumbered to M39 on 2026-08-19, and re-scoped there.** Every milestone number in this plan is
> wrong. `M27`, `M28` and `M29` were already spent when it was written - on DeepSeek Provider
> Integration, Evaluation Documentation Ownership and Evaluation Readability - because this plan
> inferred its numbers from a document instead of from
> [`docs/roadmap.yaml`](../docs/roadmap.yaml), which is the exact defect the registry's header <!-- archived-on-tag -->
> warns about. Only the titles carry forward.
> This section is now **M39**, allocated in the registry and scoped into `T0039.1-.4` in
> [`docs/Tickets.md`](../docs/Tickets.md). Read the ticket bodies, not this section: four of the
> claims below were checked against the merged tree on 2026-08-19 and did not survive. Per-seam
> telemetry already exists and is already drawn in the viewer, so only aggregation is missing;
> the Groq TPM ceiling that shaped T0028.2 is spent, and with it the D-ii paid-tier decision; the
> replay gate pins every turn rather than computing a pass rate, which answers D-iii and retires
> it; and the freezer's rejection of no-SQL turns, unknown when this was written, blocks the full
> baseline and now has its own ticket ahead of it.
> Sections 3 and 5 keep their `M27` and `M29` numbers here and have **not** been re-scoped or
> re-allocated. Do not start either from this document.

**Objective.** State what a turn costs and how long it takes, and stop a quality regression from
merging.

**Depends on** M24 landing first, because the baseline this milestone freezes should be the
post-obligation-seam number, not a number the next milestone immediately invalidates.

### T0028.1: Cost and latency per seam

**In scope.** Record tokens in, tokens out, and wall time for routing, SQL generation, and
synthesis.
The driver already records latency and token usage per turn, so this surfaces and aggregates an
existing signal rather than adding instrumentation.
Publish p50, p95, and cost per turn in the README with the date they were measured.
Fill the trace viewer's telemetry panel, which currently reads that no telemetry was recorded.

**Out of scope.** Optimising anything.
Measure first; an optimisation without a before figure cannot be stated as a result.

### T0028.2: Freeze a committed baseline

**In scope.** One full 29-scenario capture on a paid tier, sanitised and committed, replacing the
partial acceptance that left 13 of 19 turns measured and `HLP-CONTEXT-1` and `HLP-COMPOUND-1`
never captured.
The 8000 TPM admission ceiling is what excludes those two scenarios, and lowering `max_tokens` or
`agent.query.max_rows` to admit them would change what the instrument measures.

**Out of scope.** Changing a scenario, a threshold, or a grading rule to make the number look
better.

**Decision required.** The paid-tier spend.
[`Known_Issues.md`](../docs/Known_Issues.md) has carried this as an open maintainer decision since <!-- archived-on-tag -->
M25; this ticket is where it is answered or the milestone stops.

### T0028.3: Fail the build on a pass-rate regression

**In scope.** The replay gate computes a pass rate over the committed evidence and exits non-zero
when it falls more than an agreed margin below the frozen baseline.
Expand committed replay evidence beyond its current five turns toward the full registry.
Turn on the branch protection that [`Known_Issues.md`](../docs/Known_Issues.md) records as <!-- archived-on-tag -->
configured-but-unenforced, so a red gate actually blocks a merge.

**Out of scope.** Gating on latency or cost.
Those get a recorded baseline in T0028.1 and become gates only once drift is observed.

### Milestone gate

A cost and latency figure exists and is dated, the baseline is a full 29-scenario capture, and a
deliberate quality regression in a pull request turns CI red and cannot merge.

---

## 5. M29 - Production Evaluation Loop

**Objective.** Live turns produce scores, and a bad live turn becomes a regression case.

**Depends on** M28, because a loop that feeds an ungated suite changes nothing.

### T0029.1: Capture a user feedback signal

**In scope.** A rating control on each answer in the demo UI, writing a score onto that turn's
Langfuse trace.
The editorial design system in `src/api/static/styles.css` already carries the vocabulary for it,
so this is a small addition rather than a redesign.

**Out of scope.** Implicit signals such as retry and abandonment.
They are real production signals and deserve their own ticket once the explicit path is proven.

### T0029.2: Score sampled production traces

**In scope.** A sampled online judge over live traces, reusing the existing `evals/judge.py`
adapter and its throttle.
Sampling rate and budget belong in `config/settings.yaml`.

**Out of scope.** Judging every turn.
The judge tier is the expensive one, and no scenario rule reaches it today.

**Constraint.** A production turn has no reference SQL, so only the textual and judge tiers apply.
Structural and execution-accuracy grading stay fixture-bound.
Do not blur that boundary: it is what makes the offline number trustworthy.

### T0029.3: Promote a live failure into the registry

**In scope.** The documented path from a low-scoring production trace to a new scenario in
`scenarios_v1.yaml`, with its probe flags, reference SQL, and grading block.
Prove it once, end to end, with a real trace.

**Out of scope.** Automating the promotion.
A human deciding what deserves to become a permanent expectation is the correct design, not a
limitation.

### Milestone gate

A live turn has been scored, a rating has landed on a trace, and one production failure exists in
the registry as a graded scenario.

---

## 6. Sequencing

```text
M27 Serving Reliability   ── outage response, precedes everything
        │
M23 v1.0 Release Cut      ── unchanged, but must not tag a non-answering service
        │
M24 Honesty Enforcement   ── unchanged, still owns the behaviour failures M25 measured
        │
M28 Telemetry & Gate      ── baseline must be the post-M24 number
        │
M29 Production Loop       ── needs a gate to feed
```

M26 is closed and blocks nothing.
The interface work in section 7 has no position in this sequence by design.

---

## 7. Explicitly out of scope

Recorded so a later reader does not mistake an omission for an oversight.

| Not doing | Why |
|---|---|
| Multi-agent orchestration | Error amplification is measured and real; a single agent over two tools is the correct shape for one measurable job |
| Retrieval or RAG over postings | The corpus is structured and the answers are counts and filters, which SQL answers exactly and execution accuracy can verify. Retrieval would remove the property that makes this system gradable |
| Fine-tuning | No evidence that the failures are capability failures. The measured ones are architectural, and M24 addresses them in code |
| Judging production against reference SQL | A live turn has no frozen reference. See the T0029.2 constraint |

**Deferred, not rejected.** Two items are real but story-neutral, and belong in the backlog rather
than in a milestone:

- Exposing `query_clean_jobs` and `get_job_details` over MCP, as a thin server over existing tools.
- Replacing the regex SQL validator with AST parsing, keeping the regex as defence in depth.
  The current validator masks string literals and checks every `FROM` and `JOIN` target, which is
  sound for the shapes it has seen, but a regex is not a parser and the distinction is worth
  closing once nothing more urgent is open.

---

## 8. Open decisions

| # | Decision | Owner | Blocks |
|---|---|---|---|
| D-i | Which provider becomes the primary after failover exists | Maintainer | T0027.2 close |
| D-ii | The paid-tier spend for a full 29-scenario baseline | Maintainer | T0028.2 |
| D-iii | The regression margin that fails the build | Maintainer | T0028.3 |
| D-iv | Sampling rate and monthly budget for the online judge | Maintainer | T0029.2 |

Harvest each into [`Decision_Log.md`](../docs/Decision_Log.md) when answered, and retire the row.
