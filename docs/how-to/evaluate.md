# Evaluate agent behavior

> **Eviction:** A procedure leaves when the instrument it drives is retired or replaced.

How to run, inspect, calibrate, and publish evidence from the evaluation harness.
The instrument's layout and operating limits live in [`evals/README.md`](../../evals/README.md) and
[`evals/Operating_Manual.md`](../../evals/Operating_Manual.md).

## Design

## 7. Evaluation harness

The harness is offline quality tooling under the same isolation rule as ingestion.
It treats the agent as a black box through its public entrypoint plus the tracing callback seam.
Its job is to establish a measurable baseline of task correctness and the honesty bar in section 1.3
*before* any work whose design depends on measured model behavior is built.

Evaluation measures behavior; it does not fix it.
Remediation is separate work.

### 7.1 What it measures: three seams

The agent is not one model call.
The query tool takes a **natural-language question**, and a *separate, nested* call turns it into
SQL that deterministic code then validates and runs.
So a single agent run has three distinct decision points, and the harness scores each.

| Seam | What the model decides | Metric attaches to |
|---|---|---|
| 1. Routing | which tool, and the question passed to it | the agent tool-call span |
| 2. Natural language to SQL | the SQL string, invisible to the ReAct trace | the nested generation span |
| 3. Synthesis | the final user-facing answer | the final output |

Seam 2 is the most failure-prone point, and it is **not** on the tool call: it is inside the nested
generation.
Capturing it is a tracing concern, so per the tracing-boundary law it must **not** be met by
hard-coding an evaluation decorator inside the tools layer.
Instead the harness threads its callback in through **runtime config**, the same injection seam
Langfuse tracing already uses, so the nested call surfaces as its own span without evaluation
concerns leaking into tool code.

### 7.2 Metric stack

Deterministic checks for everything exact; judge checks for everything semantic.

- **Seam 1, routing.** Deterministic tool-correctness - was the right tool chosen, in the right
  order - plus a light referenceless check on the question the agent passed.
- **Seam 2, SQL.** A referenceless argument check plus a schema-aware judged criterion asking
  whether the SQL respects the schema and answers the question. No expected SQL string is stored.
- **Seam 3, synthesis.** Task completion, plus faithfulness against the tool's returned string as
  context, which catches *fabrication* such as invented freshness or hidden-salary claims not in the
  data, plus a judged honesty criterion for *omission*. The truncation caveat is emitted
  deterministically by the tool; the risk is the agent stripping it when it rewrites the answer.

Where a structural check and the judge disagree, the structural check wins (D-042).
Thresholds are **calibrated after a baseline run**, never pre-set: a threshold above the baseline
blocks every build, and below it nothing signals.

### 7.3 Scenario registry and the seeded fixture

The scenario registry in `evals/scenarios_v1.yaml` owns the cases, their probe flags, reference SQL,
tool expectations, and grading rules, and is the single source of truth for evaluation cases
(D-041).
Goldens are generated from it, which ends probe-flag drift structurally.
Scenario ids are class-first and self-describing (D-039).

Twenty-nine scenarios span five categories: grounded retrieval asserting the fixture's pinned
totals; multi-turn refinement, stored as conversational cases so the agent's own context-carry is
what gets scored rather than a pre-flattened turn; honesty probes covering freshness, cross-currency
ranking, absent technology, out-of-schema attributes, hidden salary, and hidden seniority; safety
and refusal, asserting both an empty tool list *and* a refusal, so a model that queries the database
before refusing still fails; and resilience, covering vague input and a dangling pronoun with no
prior turn.

**The harness runs against a small version-controlled seeded fixture database, not the live
corpus.**
That is what lets honesty scenarios assert exact counts, truncation notices, and specific rows, and
what makes before-and-after comparison valid: a scenario's baseline is only meaningful against a
fixed dataset version (D-037).
The fixture is versioned with the scenarios, and changing it changes the baseline.
Its free text is drawn from real captured postings so answers read authentically, while the
structured columns are *engineered* to a fixed distribution that pins every scenario.
Internship-ness is one filterable attribute among many: the fixture, like the real corpus, is mostly
non-internship AI and data postings.

### 7.4 Judge, replay, and writeback

The judge runs on a provider that does not serve the agent (D-017), which keeps evaluation load off
the serving account and keeps a provider out of judging its own arm.
Gemini judges; the judge is wrapped so the harness sees one interface.
Evaluation quality is bounded by judge quality.

**Committed replays are the CI gate.**
A completed capture is frozen into a sanitized replay, and CI replays it on every pull request with
no model or judge call.
A replay retains the evidence needed to reproduce a fixture-bound verdict - questions, answers,
called tools, generated SQL, expected deterministic outcomes, and the prompt version its capture ran
- and excludes per-turn latency, token usage, finish reasons, tool output, and every trace
identifier (D-046).
The freeze step refuses a capture that still carries a live trace identifier or cannot name its
prompt.
Replay validation also refuses a scenario whose question has drifted from the registry, so a replay
cannot keep passing against a question the registry no longer asks.

**Score writeback.**
A post-run step writes each metric score onto the same trace as the raw run, so Langfuse stays the
single pane of glass.
Re-runs are idempotent by construction of the score identity.

For the instrument's layout, seams, grading, and limits see
[`evals/README.md`](../../evals/README.md) and
[`evals/Operating_Manual.md`](../../evals/Operating_Manual.md).

### 7.5 Boundaries

- **Layer isolation.** The only touch inside the agent boundary is the config seam that lets the
  nested generation span be observed, which carries no evaluation logic and is inert in production.
- **No online evaluation.** Production-trace scoring, production-sampled goldens, judge matrices,
  and chart metrics are out of scope.
- **The harness measures; it does not remediate.**


## Provider quotas and evaluation cost

### 10.4 Provider quotas and cost

The serving agent is metered and the judge is on a free tier, which keeps evaluation work off the
serving provider's account (D-017).

DeepSeek has no free tier and publishes no per-minute or per-day token limit, only account
concurrency.
A full 29-scenario evaluation run measured about four cents at list rates, spending roughly 3.7K
tokens per turn across 77 turns.
Serving traffic on the demo is the same per-turn shape.
For the measured derivation see [T0027.3 DeepSeek arm](../../evals/t0027_deepseek_arm.md); for the
judge-side rate-limit caveats see
the archived evaluation strategy sections 4a and 4b (preservation tag `docs-history-pre-redesign`).

The Groq arm remains selectable on its free tier, at 8000 tokens per minute and 200K per day.
That ceiling is what the driver's turn-pacing setting exists for: restore it whenever a profile
moves back to Groq.

