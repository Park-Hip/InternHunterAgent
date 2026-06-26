# DeepEval: Planner Research Document

**Purpose:** Feed this document to a planning agent or technical planner to produce a technical design document and architecture for evaluating a LangChain SQL-querying agent using DeepEval.

**Scope:** Architecture patterns, technical decisions, and system context. Code-level implementation is intentionally excluded — that is handled by coding agents downstream.

---

## 1. DeepEval's Core Mental Model

### What it is

DeepEval is an open-source (Apache 2.0) evaluation framework that brings pytest-style unit testing to LLM applications. It is evaluation-first and runs entirely locally — the only external dependency is the LLM used as a judge. No platform account is required to run evals.

The central analogy: DeepEval is to LLM output quality what pytest is to code correctness. The same test-write-assert loop applies, but instead of asserting string equality, the framework asserts semantic quality scores against thresholds.

### The three primitives

Everything in DeepEval is built from three concepts that compose together at any granularity:

**Golden** — A single evaluation scenario defined before running the agent. It stores the user input and, optionally, the expected tool calls, expected output, and metadata. A collection of Goldens is a dataset. Goldens are the ground truth anchors.

**Test Case (LLMTestCase)** — The runtime record produced when the agent runs against a Golden. It captures the actual input, the actual output, the tools the agent called, the arguments passed to each tool, and any retrieval context. A Test Case is what gets scored.

**Metric** — The scoring logic that evaluates a Test Case (or a span within a trace) and produces a score between 0 and 1 with a pass/fail result based on a threshold. Metrics can be deterministic (no LLM involved) or LLM-based (using a judge model).

### Traces and spans

When an agent runs across multiple steps, DeepEval uses tracing to capture each step as a **span** inside a **trace**:

- A **trace** is the complete execution of one agent run from user input to final response. It maps to one end-to-end Test Case.
- A **span** is one component step inside that trace — an LLM call, a tool invocation, or a reasoning step. Each span maps to one component-level Test Case.

The key design insight: a trace and a span use the same LLMTestCase primitives, just at different scopes. This means the same metrics that score a full trace can also be attached to individual spans with no conceptual difference — only the granularity changes.

---

## 2. The Three Evaluation Layers

DeepEval decomposes agent evaluation into three layers that each answer a different question. All three can run in the same evaluation loop.

### Layer 1 — End-to-end evaluation (did the task succeed?)

Treats the entire agent as a black box. The input is the user question; the output is the agent's final response. The evaluator does not look inside the agent's steps.

**Use when:** You need a single pass/fail signal for the overall interaction — "did the user get what they asked for?"

**Limitations:** A passing end-to-end score tells you the task was completed but not *why* it worked or *where* it would fail with a different input. A failing score tells you something broke but not which component broke.

**Attachment point in DeepEval:** Metrics passed to `evals_iterator(metrics=[...])` at the trace level.

### Layer 2 — Trajectory-level evaluation (was the reasoning path sound?)

Evaluates the plan and the sequence of steps the agent took, not just the final output. Checks whether the agent's reasoning was logical and whether it followed its own plan without drifting.

**Use when:** You need to catch cases where the agent arrives at the right answer through a flawed or inefficient path — for example, calling the database twice when once was sufficient, or producing a plan and then ignoring it mid-run.

**Limitations:** Requires tracing to be active. The agent's internal reasoning steps must be captured as spans.

**Attachment point in DeepEval:** Metrics like `PlanQualityMetric` and `PlanAdherenceMetric` that read the full trace rather than individual spans.

### Layer 3 — Component-level evaluation (which part broke?)

Scores individual components inside the agent — the LLM's tool selection decision, the arguments it generated for the tool call, or the tool's output. This is the layer that provides actionable failure attribution: not "the agent failed" but "the agent generated the wrong SQL argument on this span."

**Use when:** You need to pinpoint failure causes rather than just detect failures. This is the layer most relevant to a SQL-querying agent, because the SQL argument itself is the most failure-prone component.

**Limitations:** Requires instrumenting the agent code with span markers. Currently single-turn only per span (multi-turn component-level is on the roadmap).

**Attachment point in DeepEval:** Metrics attached to `@observe(metrics=[...])` decorators on specific functions, typically the LLM call that generates tool arguments.

### How the layers compose

The three layers are not mutually exclusive. The recommended pattern is to run all three in the same loop:

- End-to-end metrics on the trace catch overall task failures.
- Trajectory metrics on the trace catch path quality issues.
- Component metrics on specific spans catch the root cause of failures.

When a trace fails an end-to-end metric, the component-level scores on its spans tell you exactly which span caused the failure — without this, failure attribution requires manual trace inspection.

---

## 3. Metric Selection Rationale

### The nature of each metric: deterministic vs. LLM-based

This distinction drives the cost, speed, and reliability of the eval system:

| Nature | Characteristic | Used for |
|---|---|---|
| Deterministic | No LLM call. Exact or rule-based comparison. Instant and free. | Tool name matching, argument structure validation |
| LLM-based | Calls the judge model. Slower and incurs inference cost. Semantic understanding. | Argument intent correctness, task completion quality, custom SQL logic criteria |

The design principle: **use deterministic checks for everything exact, and LLM-based checks for everything semantic**. For a SQL agent, this means the decision to call the database tool is deterministic; whether the SQL query correctly addresses the user's intent is LLM-based.

### The metrics selected and why

**ToolCorrectnessMetric** — *Deterministic at its core, optionally LLM-augmented*

Answers: did the agent call the right tool(s) and call them in the right order?

This metric compares the tools the agent actually called against the expected tools defined in the Golden. The comparison is exact-match by default — no LLM needed. If `available_tools` is also provided, a secondary LLM check evaluates whether the selection was optimal given all available options; the final score is the minimum of both.

Why it's important for this project: A SQL agent with only one tool (the database query tool) should always call that tool for database questions. Any trace where the tool is not called, or where the agent hallucinates a non-existent tool, is a critical failure. This metric catches it at zero judge cost.

Blind spot: It validates *that* the tool was called, not *how well* it was called. The argument is evaluated separately.

**ArgumentCorrectnessMetric** — *Fully LLM-based, referenceless*

Answers: did the agent pass arguments to the tool that make sense given the user's question?

This metric evaluates the input parameters the agent generated for each tool call — in this case, the SQL query string. It is referenceless: it does not compare against a pre-defined expected SQL query. Instead, the LLM judge evaluates whether the argument is logically correct given the input context (user question + schema context if provided). This is the right approach for SQL because the same question can have multiple valid SQL formulations.

Why it's important for this project: This is the most critical failure mode for a SQL agent. The agent may correctly decide to call the database tool but generate SQL that queries the wrong table, uses the wrong filter condition, or produces a result that doesn't answer the user's question. `ToolCorrectnessMetric` would pass; only `ArgumentCorrectnessMetric` would catch this.

Blind spot: Being LLM-based, it is non-deterministic — the same test case can score slightly differently across runs. It also does not validate SQL syntax; a syntactically broken query that clearly attempts to address the question might still score well.

**TaskCompletionMetric** — *Fully LLM-based, reads the full trace*

Answers: did the agent ultimately accomplish what the user asked?

This is the end-to-end metric. It reads the full execution trace — all tool calls, all intermediate outputs, the final response — and judges whether the task was completed from the user's perspective. It is the highest-level quality signal.

Why it's important for this project: A user asking "show me last month's sales by region" needs the final answer to be correct, readable, and complete. Even if the tool was called correctly with reasonable SQL, the agent might misinterpret the result, return raw data instead of a summary, or truncate the output. This metric catches final-output failures that the action-layer metrics miss.

Blind spot: It says something broke end-to-end, but not where. It must be paired with the component-level metrics to make failures actionable.

**GEval (custom)** — *LLM-based, custom criteria defined in natural language*

Answers: does the agent's output meet domain-specific quality criteria that no off-the-shelf metric covers?

GEval lets the team define evaluation criteria in plain language, such as: "Given the user's question and the database schema, evaluate whether the SQL query is semantically correct and would return data that answers the question." The LLM judge uses chain-of-thought reasoning to produce a score against this rubric.

Why it's important for this project: Neither `ArgumentCorrectnessMetric` nor `TaskCompletionMetric` is aware of the database schema or business domain. A GEval metric with the schema embedded in its criteria can catch SQL that is logically plausible but wrong given the actual table structure — for example, filtering on a column that doesn't exist, or joining tables in the wrong direction.

GEval is also the primary instrument for the chart generation phase: when the agent gains a chart tool, a GEval criterion can evaluate whether the chart type chosen is appropriate for the data shape returned.

Blind spot: GEval is non-deterministic and its score depends heavily on how the criteria are written. Vague criteria produce noisy, unreliable scores. Well-written, specific criteria correlate well with human judgment.

**DAGMetric (optional, for structured SQL validation)** — *Deterministic decision-tree with LLM leaf nodes*

Answers: does the SQL argument meet a sequence of hard, ordered quality gates?

DAGMetric builds a decision tree where each node is a binary or graded judgment. For SQL, a useful DAG would be: first check if the output is syntactically valid SQL (deterministic gate); if yes, check if the table names exist in the schema (deterministic gate); if yes, evaluate semantic correctness with a GEval-style leaf judge. This produces deterministic, traceable scores and prevents the LLM judge from being asked to evaluate structurally broken SQL.

Why it's important: DAGMetric is the right escalation from GEval when the team needs reproducible, auditable scores — for example, if evaluation results are used in release decisions and need to be explained to stakeholders.

Trade-off: DAGMetric requires more upfront design work than GEval. It is best introduced in Phase 2 after GEval has established baseline criteria.

---

## 4. Evaluation Trigger Strategy

### Offline evaluation (CI/CD gate)

Offline evaluation runs before deployment against a fixed golden dataset. It is the primary quality gate. A failing offline eval blocks the release.

Characteristics:
- Triggered on every pull request that changes the agent prompt, model, or tool schema.
- Runs the full metric stack including LLM-based metrics.
- Uses the full golden dataset (20–50 cases to start, growing over time).
- Results are deterministic per golden dataset version — the same goldens produce comparable scores across runs.
- Slower than a standard unit test run (minutes, not seconds) due to LLM judge calls.

**Decision rule for the team:** What score drop constitutes a regression? A reasonable starting point is any metric dropping more than 5 percentage points from the baseline run. This threshold must be calibrated after the first few evaluation cycles.

### Online evaluation (production monitoring)

Online evaluation runs against live production traces — real user queries flowing through the agent. It is not a gate; it is a quality signal.

Characteristics:
- Only referenceless metrics can run in production (no expected_tools or expected_output is available for real traffic).
- Suitable for: `TaskCompletionMetric`, `ArgumentCorrectnessMetric`, and GEval custom criteria.
- Not suitable for: `ToolCorrectnessMetric` (requires expected_tools ground truth).
- Asynchronous — scores are written back to the observability system after the agent responds, not during the request.
- Higher judge volume than offline eval, so the free judge model must have sufficient rate limits or throughput.

**Decision for Phase 1:** Defer online eval until the offline eval pipeline is stable. Online eval adds operational complexity (score writeback, alerting thresholds, async judge infrastructure) that is premature before the offline baseline is established.

### When to escalate to human review

Not all eval failures require automated action. The team needs a triage policy:

- Score below threshold on a deterministic metric → automated fail, no human needed.
- Score below threshold on an LLM metric by a small margin (< 10%) → flag for human review before blocking the release.
- Score below threshold on an LLM metric by a large margin (> 10%) → automated block + human review.
- GEval score consistently drifting downward across multiple runs → prompt engineering investigation.

---

## 5. Judge LLM Decision

### The decision

The judge LLM is the model that powers all LLM-based metrics. It does not query the production database; it only reads the agent's inputs and outputs and produces a score.

### Candidate options and tradeoffs

**Groq free tier (Llama-3-70b or Llama-3.1-70b)**

- Latency: very fast (Groq's LPU hardware, sub-second for most prompts).
- Quality: 70B-class reasoning is sufficient for argument correctness and task completion judgment. Strong structured output support — important for DeepEval's internal JSON parsing.
- Cost: Free tier. Rate limits apply (varies by model, typically 30 requests/minute on free tier).
- Risk: Rate limits can stall CI runs with large datasets. The free tier has no SLA.
- Best for: Offline CI eval with datasets up to ~30 goldens per run. Suitable for Phase 1.

**Ollama local (Llama-3-70b, Mistral-7b, Gemma-2-9b)**

- Latency: Depends on local hardware. GPU required for 70B models at acceptable speed; 7-9B models run on CPU but produce noisier scores.
- Quality: 70B local matches Groq quality. 7-9B models require DeepEval prompt template overrides per metric to produce reliable structured output.
- Cost: Zero API cost. Infrastructure cost of GPU compute.
- Risk: Local setup dependency in CI (model must be pre-pulled). Not suitable for shared CI runners without a dedicated GPU.
- Best for: Developer local iteration. Not the primary CI judge unless dedicated hardware is available.

**Google Gemini free tier (gemini-1.5-flash or gemini-2.0-flash)**

- Latency: moderate.
- Quality: Strong reasoning, good structured output. Free tier is generous (1,500 requests/day).
- Cost: Free tier sufficient for offline eval volume.
- Risk: Google free tier terms may restrict commercial use. Verify license compatibility.
- Best for: Good backup option if Groq rate limits become a bottleneck.

### Recommendation

Use **Groq (Llama-3-70b)** as the primary judge for Phase 1. It is the free option with the best latency, strongest structured output, and lowest setup friction. Set Ollama as the developer fallback for local iteration without internet dependency. Re-evaluate when dataset size grows beyond Groq free tier rate limits.

### Judge quality caveat

A critical architectural constraint: **the quality of the evaluation is bounded by the quality of the judge**. A weak judge produces noisy scores that cannot be trusted for release decisions. The 70B model class is the minimum recommended for argument correctness and GEval criteria on SQL. Smaller models (7B, 8B) produce unreliable structured output and require significant prompt engineering to compensate.

DeepEval's default metric prompts are calibrated for GPT-4-class models. When using a smaller free model, the evaluation template for each metric should be reviewed and potentially overridden — this is a design decision, not an implementation detail.

---

## 6. Golden Dataset Design

### What a golden is for a SQL agent

A single golden for this project captures a complete evaluation scenario:

- **Input:** The natural language user question (e.g., "What were the top 5 products by revenue last quarter?")
- **Expected tools:** Which tool(s) should be called and in what order (e.g., `[query_database]`)
- **Expected output (optional):** What the final response should convey — not necessarily verbatim, but semantically (e.g., "A ranked list of 5 products with their revenue figures")
- **Additional metadata:** Difficulty level, question category (aggregation, filter, join, time-range), and whether the question requires schema knowledge

The expected SQL query itself is intentionally not part of the golden, because `ArgumentCorrectnessMetric` is referenceless — it judges SQL by intent, not by exact string match.

### Dataset sourcing strategy

Three complementary sources produce a high-quality golden dataset:

**Manual curation (start here):** 15–20 hand-crafted questions that cover the most important question types for the SQL agent's domain. These should include easy cases (single-table, single-condition), medium cases (aggregations, date ranges), and hard cases (multi-table, ambiguous phrasing). Quality over quantity — a small, diverse dataset is more useful than a large, homogeneous one.

**Production trace sampling (Phase 2 onward):** Real user questions from Langfuse production traces can be promoted to goldens. The team manually labels the expected tool call and expected output quality, then adds the case to the dataset. This creates a feedback loop where production failures automatically improve the test coverage.

**Synthetic generation (optional):** DeepEval includes a Golden Synthesizer that generates test cases from a description of the agent's task. This is useful for expanding coverage quickly but requires human review — synthetic cases can be unrealistic or redundant.

### Dataset sizing guidance

- **Phase 1 launch:** 15–25 goldens. Small enough to iterate quickly, large enough to cover the main question types.
- **Steady state:** 50–100 goldens. Covers edge cases, multiple SQL patterns, and known failure modes discovered in production.
- **Growth trigger:** Add new goldens whenever a production failure is found that no existing golden would have caught.

### Dataset versioning

The golden dataset is a versioned artifact — it must be version-controlled alongside the agent's prompt and tool schema. A change to the golden dataset changes the baseline, making before/after score comparisons invalid unless the same dataset version is used for both runs.

---

## 7. Integration Topology

### System map

The eval system connects four components. Understanding the data flow between them is necessary for the design document.

```
┌─────────────────────────────────────────────────────────────┐
│                    CI/CD Pipeline                           │
│                                                             │
│  Golden Dataset  ──►  DeepEval Test Run  ──►  Pass / Fail   │
│  (versioned JSON)      (pytest + metrics)      (build gate) │
└─────────────────────────────────────────────────────────────┘
         │                     │
         │                     ▼
         │           ┌─────────────────────┐
         │           │   Judge LLM          │
         │           │   (Groq / Ollama)    │
         │           └─────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Runtime                            │
│                                                             │
│  User Question  ──►  LangChain Agent  ──►  SQL Tool  ──►   │
│                       @observe()           (DB query)       │
│                            │                                │
│                            ▼                                │
│                      DeepEval Trace                         │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Langfuse                                 │
│                                                             │
│  Traces + Spans  ◄──  Score Writeback  ◄──  DeepEval       │
│  (observability)       (via Score API)       eval results   │
└─────────────────────────────────────────────────────────────┘
```

### Role of each component

**DeepEval** — the evaluation engine. Runs metrics, produces scores, integrates with pytest for CI/CD gating. Does not do observability or tracing on its own.

**Langfuse** — the observability layer. Captures traces from the production agent (and from eval runs if desired), stores them, and renders them in a UI. Receives DeepEval scores via its Score API so that eval results appear on the same trace record as the raw execution data.

**LangChain agent** — the system under test. Instrumented with DeepEval's `@observe` decorator (or Langfuse callbacks, which can coexist) so both systems receive trace data.

**Judge LLM (Groq/Ollama)** — stateless inference service. Called by DeepEval's LLM-based metrics. Has no access to the production database or Langfuse.

### The score writeback pattern (DeepEval → Langfuse)

DeepEval and Langfuse use separate tracing systems. The integration pattern is:

1. DeepEval runs an evaluation and produces a score for a given test case.
2. The test case has a `trace_id` that matches a Langfuse trace for the same agent run.
3. A post-eval script calls `langfuse.create_score(name=metric_name, value=score, trace_id=trace_id)` to attach the score to the Langfuse trace.
4. The Langfuse UI shows both the raw trace (tool calls, latency, token cost) and the eval scores on the same record.

This pattern keeps Langfuse as the single pane of glass for both operational and quality data. The eval scores are surfaced in Langfuse without requiring DeepEval's own cloud platform (Confident AI) for dashboards.

### What DeepEval does not provide

DeepEval is a testing framework, not an observability platform. It does not:

- Provide runtime tracing for production agents beyond what is needed to run metrics.
- Alert on quality degradation in real time.
- Store evaluation history beyond the local filesystem (unless Confident AI is used).
- Replace Langfuse for production observability.

This is why the integration topology keeps Langfuse as the production observability layer and uses DeepEval as the evaluation engine that feeds scores into it.

---

## 8. Phasing and Evolution Plan

### Phase 1 — SQL tool only (current state)

**What the eval system covers:**

| Layer | Metric | Judge | Scope |
|---|---|---|---|
| Component | `ToolCorrectnessMetric` | None (deterministic) | Was `query_database` called? |
| Component | `ArgumentCorrectnessMetric` | Free judge | Was the SQL argument semantically correct? |
| End-to-end | `TaskCompletionMetric` | Free judge | Did the user get what they asked for? |
| End-to-end | `GEval` (SQL quality) | Free judge | Does the SQL respect the schema and return correct data? |

**Golden dataset:** 15–25 cases covering simple filters, aggregations, date ranges, and multi-condition queries.

**CI/CD integration:** `deepeval test run` on every PR that touches the agent prompt, model, or tool schema.

**Score writeback:** Post-eval script writes scores to Langfuse traces. No online eval in Phase 1.

### Phase 2 — Chart generation tool added

**What changes:**

The agent gains a second tool (`generate_chart`). The eval system must be extended without redesigning what already works.

**New metrics added:**

- Extend `ToolCorrectnessMetric` golden definitions to include `[query_database, generate_chart]` as the expected tool sequence for questions that imply visualization.
- Add a new `GEval` metric with chart-specific criteria: "Given the data returned by the SQL query, evaluate whether the chart type selected by the agent is appropriate for the data shape and the user's question."
- Add `StepEfficiencyMetric` to catch cases where the agent generates a chart when none was asked for, or calls the database twice before charting.

**What does not change:**

All Phase 1 metrics continue to run unchanged. The eval system composes, not replaces.

**Golden dataset extension:** Add 10–15 cases involving chart requests, covering bar charts for categorical comparisons, line charts for time series, and edge cases like requesting a chart when the data is insufficient.

### Phase 3 — Production feedback loop (future)

Online evaluation is enabled. Langfuse production traces are periodically sampled, labeled by a domain expert, and promoted to the golden dataset. The eval dataset grows with production usage and test coverage stays aligned with real user behavior.

---

## 9. Quality Gate Definition

### What constitutes a passing build

The team must define explicit score thresholds before the CI eval is meaningful. Suggested starting thresholds based on industry practice:

| Metric | Threshold | Rationale |
|---|---|---|
| `ToolCorrectnessMetric` | 0.90 | Deterministic — a score below 0.90 means the agent failed to call the right tool on > 10% of cases. This is a critical failure. |
| `ArgumentCorrectnessMetric` | 0.70 | LLM-based — 0.70 is the typical starting point for semantic correctness metrics. Adjust up after calibration. |
| `TaskCompletionMetric` | 0.75 | LLM-based — slightly higher than argument correctness because task completion is the user-facing quality signal. |
| `GEval` (SQL quality) | 0.65 | Custom metric with higher variance — start lower and raise the bar as criteria are refined. |

**Calibration process:** Run the initial golden dataset through the eval pipeline before setting thresholds. Use the baseline scores as the reference point. A threshold below the baseline produces no signal; a threshold above it blocks every build. The right threshold is 5–10 points below the baseline score on the initial dataset.

### Regression definition

A regression is a statistically meaningful drop in score compared to the previous passing run. A pragmatic definition for Phase 1: any metric dropping more than 5 percentage points from the last passing run triggers a hold for human review before the release proceeds.

### Who reviews failed evals

- Deterministic metric failure → automated block, no human review needed. The failure is unambiguous.
- LLM metric failure by > 10 points → automated block + engineer review. Review the specific failing test cases and their score reasoning.
- LLM metric failure by < 10 points → engineer judgment call. The score may reflect metric noise rather than a real regression. Do not block without investigation.

---

## 10. Open Decisions for the Planner

The following decisions are not resolved by this research document. They require team input and should be explicitly addressed in the technical design document.

**Judge model finalization:** Groq (Llama-3-70b) is recommended, but the team must confirm the Groq free tier rate limits are sufficient for the planned dataset size and CI frequency. If the team runs CI on every commit (not just PR), volume may exceed the free tier.

**Score writeback ownership:** Which component is responsible for calling the Langfuse Score API after a DeepEval run? Options are: (a) the CI/CD pipeline as a post-test step, (b) a dedicated score-writeback script, or (c) inline in the DeepEval test file. The choice affects how trace IDs are passed between systems.

**Golden dataset storage:** Where does the golden dataset live — in the application repository alongside the agent code, in a separate data repository, or in a cloud dataset store (Confident AI or Langfuse datasets)? This affects dataset versioning, access control, and how the CI/CD pipeline pulls the dataset.

**Online eval timing:** When in Phase 1 does online eval get enabled? This requires agreement on a sampling rate, a score alerting policy, and who owns the alert response workflow.

**Human annotation process:** Who reviews failing eval cases and how? Is there a Langfuse annotation workflow, or are failing cases reviewed directly in the DeepEval output? This determines whether Langfuse's annotation features are needed or whether the eval output is sufficient.

**Threshold calibration schedule:** When are eval thresholds first set, and when are they revisited? A common pattern is to set thresholds after the first 2 weeks of eval runs, then revisit quarterly as the dataset and agent both evolve.

---

## Sources

- DeepEval documentation: https://deepeval.com/docs/introduction
- DeepEval agent evaluation guide: https://deepeval.com/guides/guides-ai-agent-evaluation
- DeepEval agent metrics reference: https://deepeval.com/guides/guides-ai-agent-evaluation-metrics
- DeepEval LLM tracing: https://deepeval.com/docs/evaluation-llm-tracing
- DeepEval CI/CD integration: https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd
- DeepEval custom LLM judge guide: https://deepeval.com/guides/guides-using-custom-llms
- Langfuse Score API: https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk
- Langfuse + DeepEval integration cookbook: https://langfuse.com/guides/cookbook/example_external_evaluation_pipelines
- DeepEval vs Langfuse: https://deepeval.com/blog/deepeval-vs-langfuse
