# DeepEval: Planner Research Document - Decision Record (archived)

> Archived 2026-08-11. M11 shipped. Outcome owned by
> `docs/MVP_Technical_Design.md` section 8 and D-016, D-017, and D-018.
> Preserved for the reasoning and rejected alternatives; not implementation guidance.

## Decisions taken

- D-016: evaluation covers outcome, trajectory, and component layers.
- D-017: Gemini judges evaluation while Groq serves the agent.
- D-018: offline evaluation precedes online monitoring.

## 2. The Three Evaluation Layers

DeepEval decomposes agent evaluation into three layers that each answer a different question.
All three can run in the same evaluation loop.

### Layer 1 - End-to-end evaluation (did the task succeed?)

Treats the entire agent as a black box.
The input is the user question; the output is the agent's final response.
The evaluator does not look inside the agent's steps.

### Layer 2 - Trajectory-level evaluation (was the reasoning path sound?)

Evaluates the plan and the sequence of steps the agent took, not just the final output.
Checks whether the agent's reasoning was logical and whether it followed its own plan without
drifting.

### Layer 3 - Component-level evaluation (which part broke?)

Scores individual components inside the agent - the LLM's tool selection decision, the arguments
it generated for the tool call, or the tool's output.
This is the layer that provides actionable failure attribution: not "the agent failed" but "the
agent generated the wrong SQL argument on this span."

The three layers are not mutually exclusive.
The recommended pattern is to run all three in the same loop:

- End-to-end metrics on the trace catch overall task failures.
- Trajectory metrics on the trace catch path-quality issues.
- Component metrics on specific spans catch the root cause of failures.

When a trace fails an end-to-end metric, component-level scores on its spans identify the failing
span without requiring manual trace inspection.

## 4. Evaluation Trigger Strategy

### Offline evaluation (CI/CD gate)

Offline evaluation runs before deployment against a fixed golden dataset.
It is the primary quality gate.
A failing offline eval blocks the release.

### Online evaluation (production monitoring)

Online evaluation runs against live production traces - real user queries flowing through the
agent.
It is not a gate; it is a quality signal.

**Decision for Phase 1:** Defer online eval until the offline eval pipeline is stable.
Online eval adds operational complexity (score writeback, alerting thresholds, async judge
infrastructure) that is premature before the offline baseline is established.

Only referenceless metrics can run in production because expected tools and expected output are
not available for real traffic.
Online scoring is asynchronous: scores are written back to observability after the agent responds,
not during the request.
This higher judge volume needs confirmed rate limits and throughput before it is enabled.

### When to escalate to human review

- A deterministic metric below threshold fails automatically.
- A small LLM-metric miss is flagged for human review before blocking a release.
- A large LLM-metric miss blocks automatically and receives human review.

## 5. Judge LLM Decision

The judge LLM is the model that powers all LLM-based metrics.
It does not query the production database; it only reads the agent's inputs and outputs and
produces a score.

### Candidate options and tradeoffs

**Ollama local (Llama-3-70b, Mistral-7b, Gemma-2-9b)**

- Risk: Local setup dependency in CI (model must be pre-pulled).
  Not suitable for shared CI runners without a dedicated GPU.

**Google Gemini free tier (gemini-1.5-flash or gemini-2.0-flash)**

- Quality: Strong reasoning, good structured output.
  Free tier is generous (1,500 requests/day).
- Risk: Google free tier terms may restrict commercial use.
  Verify license compatibility.

### Judge quality caveat

The quality of the evaluation is bounded by the quality of the judge.
A weak judge produces noisy scores that cannot be trusted for release decisions.
Smaller models produce unreliable structured output and require significant prompt engineering to
compensate.

Deterministic metrics verify exact expectations such as tool-name matching and argument structure.
LLM-based metrics verify semantic intent, task completion, and domain-specific criteria.
The design principle is to use deterministic checks for everything exact and LLM-based checks for
everything semantic.

For the SQL agent, tool selection is deterministic while the semantic correctness of a query is
judge-scored because more than one SQL formulation can validly answer a user question.

`ToolCorrectnessMetric` checks the expected tool sequence.
`ArgumentCorrectnessMetric` scores the meaning of the generated argument.
`TaskCompletionMetric` evaluates the completed response from the user's perspective.
GEval provides criteria that are specific to the database schema and domain.

### Judge quality caveat

A critical architectural constraint: **the quality of the evaluation is bounded by the quality of
the judge**.
A weak judge produces noisy scores that cannot be trusted for release decisions.

## 8. Phasing and Evolution Plan

### Phase 1 - SQL tool only (current state)

The initial evaluation harness covers the existing SQL-querying agent with no chart generation.
It establishes the golden dataset, core metrics, and the offline quality gate before expanding
scope.

| Layer | Metric | Judge | Scope |
|---|---|---|---|
| Component | `ToolCorrectnessMetric` | None (deterministic) | Was `query_database` called? |
| Component | `ArgumentCorrectnessMetric` | Free judge | Was the SQL argument semantically correct? |
| End-to-end | `TaskCompletionMetric` | Free judge | Did the user get what they asked for? |
| End-to-end | `GEval` (SQL quality) | Free judge | Does the SQL respect the schema and return correct data? |

**Golden dataset:** 15-25 cases covering simple filters, aggregations, date ranges, and
multi-condition queries.

### Phase 2 - Chart generation tool added

The agent gains a second tool (`generate_chart`).
The eval system must be extended without redesigning what already works.

All Phase 1 metrics continue to run unchanged.
The eval system composes, not replaces.

The chart phase extends tool-correctness golden definitions to include the expected tool sequence.
It adds a chart-specific GEval criterion and a step-efficiency metric for unnecessary charting or
duplicate database calls.
The golden dataset expands with chart requests, categorical comparisons, time series, and cases
where data is insufficient for a visualization.

### Phase 3 - Production feedback loop (future)

Online evaluation samples Langfuse production traces, labels them with a domain expert, and
promotes appropriate examples into the golden dataset.
The dataset grows with production usage and coverage remains aligned with actual user behavior.

## 11. InternHunter-Specific Grounding & Version-Pinned Findings (recorded 2026-07-03)

Sections 1-10 are a **generic** SQL-agent planner (written before the eval stage was deferred).
This section grounds them in **our actual stack and code** and pins the 2026 external facts that
sections 5, 7, and 9 got wrong or left open.
Read this section first when planning T0011 - where it conflicts with sections 1-10, this section
wins.

### 11.2 The two-LLM architecture - the SQL is hidden (reshapes metric attachment)

`query_clean_jobs` does **not** take SQL.
The ReAct agent passes a **natural-language question**; inside the tool, `generate_sql()` makes a
**separate nested `model.invoke()`** that translates NL to SQL.

**Instrumentation decision (grounded):** use DeepEval's **`CallbackHandler`** (passed into
LangChain's `config`) for the agent trace plus tool and LLM spans - no app rewrite.
For seam 2, **do not** rely on `next_llm_span` - it is *one-shot on the first LLM span in the
block*, which is the routing call, not the SQL call.
Instead wrap `generate_sql` with **`@observe`** and stage the SQL metric with
`update_current_span()`.

### 11.3 Honesty = Faithfulness + GEval (two halves)

> **Update - `FaithfulnessMetric` dropped (T0012.10).** This section's plan was implemented,
> then the metric was **removed** in T0012.10 as redundant with `GEval("Honesty")`.
> Honesty today is carried entirely by the single `GEval("Honesty")` metric described in
> `pre-deploy-refinement-plan.md` section 5a/5f, not the two-halves split below.

The eval targets the model's *rewriting* at seam 3, not the guardrails.

### 11.4 Judge model - section 5's "Llama-3-70b" recommendation is DEAD

> **Update - judge moved to Google Gemini, not a Groq fallback.** The options weighed below
> are all Groq-hosted; the decision that actually shipped went a different direction:
> `config/settings.yaml` has `eval.judge.provider: google`, `model: gemini-2.5-flash`
> (`thinking_budget: 0` for cost).
> See `eval-cost-and-rate-limits.md` for the current agent-Groq/judge-Google split and its
> cost/rate-limit analysis - that doc reflects what's actually running; this section is the
> earlier decision trail.

- Groq **deprecated `llama-3.3-70b-versatile` on 2026-06-17; shutdown 2026-08-16**
  (free/developer tier). Replacements Groq names: **`openai/gpt-oss-120b`** or
  **`qwen/qwen3.6-27b`**.
- **Risk:** `openai/gpt-oss-120b` has **reported structured-output regressions** on Groq.
  DeepEval metrics **hard-fail without reliable JSON**.
  Do **not** assume it works - implementation requires a live JSON-reliability spike before
  committing the judge.
- Judge wrapper path: custom **`DeepEvalBaseLLM`**; smaller or non-OpenAI judges need a
  structured-output adapter for valid JSON.

### 11.5 Langfuse 4.x score writeback - pattern survives v4

`langfuse.create_score(name=, value=, trace_id=, data_type=, comment=)` still exists in v4.
Use `data_type="BOOLEAN"` for honesty pass/fail and numeric values for GEval.
Idempotency for re-runs uses `score_id = f"{trace_id}-{metric}"`.
The open seam is getting the Langfuse `trace_id` onto the DeepEval test case.

### 11.6 CI recipe (greenfield) + the double-Groq-load problem

The judge moved to Google Gemini.
The real constraint is now two **separate** free-tier budgets: Groq for the agent and Google for
the judge.
`GROQ_API_KEY` is still needed for the agent; a Google API key is now also required for CI.

`deepeval test run` belongs in a GitHub Actions workflow.
The local cache can skip unchanged cases, while parallelism raises concurrent model calls.

### 11.7 Follow-ups surfaced (out of T0011 scope - report separately per CLAUDE.md section 1)

These are not T0011 scope, but were surfaced by grounding the plan against the actual code.

- **Prompt v2 few-shot pass needs the eval baseline first.** The `prompt-v2` work should not
  start until the initial eval suite has established the current behavior baseline.
- **Score writeback is explicitly deferred.** The current milestone runs offline only; Langfuse
  score writeback and production monitoring belong after a stable offline baseline.

### 11.8 Other premade metrics surveyed (not adopted) - recorded 2026-07-07

Premade metrics were not adopted where they did not measure the project-specific failure mode.
The retained metric set follows the component, trajectory, and outcome layers above.

## Rejected alternatives

- Groq as both serving model and judge would put both workloads on the same free-tier quota.
- Online evaluation before an offline baseline would add premature operational complexity.
- A local judge is not suitable for shared CI runners without a dedicated GPU.

## Sources

- DeepEval documentation and live package checks recorded in the original research document.
- `research/eval-cost-and-rate-limits.md` owns the current quota and cost analysis.

The current evaluation configuration, quota findings, and judge-model availability are maintained
outside this historical decision record.

## Preserved evaluation boundaries

- The evaluation harness is an offline pipeline, not part of the serving request path.
- The judge receives inputs and outputs, not production database access.
- Agent serving and judge demand use separate provider budgets.
- Online scores remain deferred until the offline baseline is stable and measurable.
