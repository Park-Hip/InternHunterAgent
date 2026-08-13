# Prompt Refinement Methods, and the `behavior_glossary` Decision

> **Status:** Live research record, written 2026-08-12. External practice reviewed the same day;
> sources at the end. It answers one open question — whether the archived `behavior_glossary`
> belongs in `config/prompts.yaml` — and records the production prompt-refinement methods and
> tradeoffs behind the answer. It feeds the improve phase in
> [`evaluation-strategy.md`](evaluation-strategy.md) §6 and the mechanism design in
> [`honesty-enforcement-design.md`](honesty-enforcement-design.md).

## 0. The answer

**Land the glossary as a config artifact. Do not paste it into the system prompt.** Inject a
canonical string only when its obligation fires — one or two per turn instead of eighteen on every
turn.

This is a third option, and neither of the two on the table. T0015.2 planned to add the whole block
to the system prompt; the current position leaves it stranded on an archive tag. Both are wrong for
the same reason: they treat the glossary as one thing when it is two.

| Part | What it is | Where it belongs | Cost in the prompt |
|---|---|---|---|
| The 18 **tokens** (`CROSS_CURRENCY`, `ZERO_RESULTS`, …) | A machine-readable contract shared by the behavior spec, the graders, and the obligation mechanism | `config/prompts.yaml`, loaded by code and tests | **zero** — nothing requires them to reach the model |
| The 18 **canonical phrasings** | Approved wording for each hedge | Same file, injected per-obligation at runtime | ~35 tokens for the one that fires, not 635 for all |

---

## 1. What the decision costs, measured

| Item | Size | Note |
|---|---:|---|
| `prompts.system_prompt` today | 2,787 chars ≈ **697 tokens** | |
| Archived `behavior_glossary`, 18 entries | 2,542 chars ≈ **635 tokens** | |
| Combined system prompt | ≈ **1,332 tokens** | **+91%** |
| Measured cost per agent turn today | ~1,400–1,500 tokens | agent call + nested SQL call |

A ReAct turn sends the system prompt on each loop iteration, so a two-iteration turn pays the
glossary twice: roughly **+1,270 tokens per turn**, taking a turn from ~1,450 to ~2,700. Across a
78-turn evaluation pass that is ~117K → ~210K tokens, **against a 200K daily cap**.

**That arithmetic is real but it is not the reason to say no** — see §3d. Groq's prompt caching
excludes cached tokens from rate limits, and a static system prompt is exactly the stable prefix
caching is built for. The cost objection is largely answerable. The attention objection is not.

---

## 2. How production teams refine prompts

Four methods, in rough order of maturity. They are cumulative, not alternatives.

**Method 1 — Version the prompt and gate it on evals.** The baseline discipline. Semantic
versioning carries meaning: major for restructured logic, minor for backward-compatible
improvements, patch for wording fixes, so the version itself says how much testing is owed. Each
version carries metadata on *why* it changed and what it moved. Evaluation suites fire on prompt
events — commit, merge, promotion — so regressions surface in review rather than after deploy.

**Method 2 — A/B and staged rollout.** Compare versions against a fixed dataset, then promote
through environments. Requires enough traffic or enough scenarios for the comparison to mean
something; §3e is why this is weak for us specifically.

**Method 3 — Automated prompt optimization.** DSPy's optimizers treat the prompt as a parameter to
search rather than prose to hand-tune. MIPROv2 proposes instruction candidates and searches
instruction-plus-demonstration combinations; GEPA evolves prompts using natural-language reflection
on failures and reports **>10% improvement over MIPROv2** across several benchmarks while being
more sample-efficient. The honest caveat is that MIPROv2 can overfit the examples it was given,
because it optimizes against scores without reading feedback.

**Method 4 — Take the rule out of the prompt.** The most reliable fix is often to stop asking. The
governing observation from production practice: *models don't execute rules; they approximate
them*, so enforcing a deterministic business rule with `NEVER`/`ALWAYS`/`MUST` in a prompt is a
category error. Workflow logic — routing, retries, confirmations, state — belongs in code. The
related **lazy-loaded procedural policy** pattern keeps only core identity and invariant
constraints in the system prompt, and pulls scenario-specific procedure in at runtime when it
applies.

Method 4 is the one that decides our question.

---

## 3. The tradeoffs

### 3a. Instruction count — the binding constraint

Performance degrades **consistently and predictably** as the number of simultaneous instructions
rises. The ManyIFEval work measures this across ten models with up to ten instructions and finds
the degradation regular enough that a logistic regression **on instruction count alone** predicts
performance within ~10% error, even for unseen instruction combinations. Practitioner guidance puts
the practical knee at **eight to ten distinct instructions**, past which attention to any one of
them measurably drops and the model begins triaging which rules to follow.

**Eighteen canonical behaviors presented as eighteen rules sits well past that knee.** This is the
load-bearing objection, and no amount of caching or context headroom addresses it.

### 3b. Position and length effects

Two separate effects, often conflated:

- **Lost in the middle** — retrieval is strongest at the beginning and end of the input and weakest
  in the middle. The evidence here is genuinely mixed for *instructions* specifically: at least one
  study found no consistent relationship between instruction position and following rate, so this
  is a real risk but not a settled law.
- **Context rot** — accuracy falls as total input grows *even when the evidence is fixed and well
  placed*. One controlled study reports reasoning accuracy dropping from **0.92 to 0.68** as input
  grew from a few hundred to ~3,000 tokens.

For us, the second matters more than the first. Doubling the system prompt does not push it out of
the high-attention zone, but it does grow every request in a regime where growth alone costs
accuracy.

### 3c. Few-shot examples — and why our case inverts the usual warning

The standard caution is that examples cause overfitting: the model copies structural choices
(quote style, field order, code fences) and, in A/B tests, **example phrasing leaks into production
copy verbatim**. Guidance is to describe voice and style in prose and trust the model, reserving
examples for genuine pattern-inference.

Our case inverts it. Verbatim reproduction of an approved string is **the goal**, not the failure —
so the usual downside becomes the mechanism. The residual risk changes shape: not that wording
leaks, but that it leaks into scenarios where the caveat does not apply. That is an over-hedging
failure, and it is the one to watch for if canonical strings are ever supplied unconditionally.

### 3d. Cost and quota — weaker than it looks

Groq's prompt caching is **automatic, with no code changes**, gives a **50% discount on cached
input tokens**, and — decisively for us — **cached tokens do not count toward rate limits**. The
conditions: **exact prefix match**, a minimum cacheable length of **128–1,024 tokens depending on
model**, and a **2-hour TTL** on unused entries. Cache hits are not guaranteed, and the docs note
tokens are subtracted from limits *after* processing, so parallel large requests can still trip a
limit.

A static glossary at the front of the system prompt is close to the ideal cached prefix: stable,
above the minimum length, unchanging across a run. **So the §1 quota arithmetic is probably not
what would happen** — a warm cache could make the glossary nearly free against TPD.

Recording this matters because it removes a bad argument. Rejecting the glossary "because we cannot
afford the tokens" would be wrong, and would collapse the moment we moved to a paid tier or a
provider with better caching. The reason to reject it is §3a.

The general prompt-caching lesson is worth carrying anyway: one team lifted cache hit rate from 7%
to 84% and cut total cost 59% purely by **moving dynamic content out of the system prompt into a
trailing user message**. Whatever we inject per-turn should go at the end, not spliced into the
prefix, or it destroys the cacheability of everything before it.

### 3e. Maintenance and measurement

**Instruction accretion** is the named anti-pattern: prompts that grow a rule per bug report until
fifteen or twenty bullets saturate attention and the original task statement loses its weight. Our
Class 3 wording defects are exactly the kind of finding that generates such accretion one bullet at
a time.

And measurement bounds all of it. With 29 scenarios we can detect gross regressions only — a prompt
A/B whose true effect is a few percent is not resolvable here, which limits Method 2 and rules out
Method 3 outright. **DSPy-style optimization needs hundreds of scored examples we do not have**, and
its optimizers would be fitting to a 29-case set with a judge whose agreement is unvalidated. It is
the right technique at the wrong scale; recorded as ruled out for v1, not as a bad idea.

---

## 4. Applying this to the glossary

### 4a. Why per-obligation injection wins

| Property | Whole block in the system prompt | Injected when the obligation fires |
|---|---|---|
| Instructions competing for attention | 18, past the ~8–10 knee (§3a) | 1–2, comfortably inside it |
| Tokens added per turn | ~635, ~1,270 across two ReAct iterations | ~35–70 |
| Prefix cacheability | good — static prefix | preserved, if injected as a trailing message (§3d) |
| Over-hedging risk | high — all 18 caveats visible on every turn | low — the model sees only what applies |
| Determinism | the model decides *whether* the rule applies | code decides; the model only relays |

The last row is the real argument. Putting the hedge in the prompt asks the model to make two
judgments — *does this situation call for a caveat* and *how do I word it*. Computing the obligation
in code collapses that to one, and the one it is reliably good at.

**We already have in-repo evidence that this works.** The single honesty caveat the agent gets
right is truncation (HLP-TRUNCATION-1, 2 of 2), and truncation is the only caveat
**computed in code and handed to the model as text**. Everything it must infer, it misses.
That is one observation, not a proof,
but it points the same way as the external practice.

Regulated-industry practice converges here too, from a different direction: where exact wording
carries risk, approved templates are held **fixed and not AI-editable**, rather than regenerated per
response. Our hedges are not legally binding, but they are the product's core promise, which is the
same argument at lower stakes.

### 4b. What this means concretely

1. **Land the glossary into `config/prompts.yaml`** with a loader and a test that every token
   referenced by the graders, the behavior spec, and the mechanism exists. This is unchanged from
   the existing plan and is still the cheapest unblocked item.
2. **Do not add it to `system_prompt`.** The system prompt keeps identity, the schema context, and
   the small set of invariant rules.
3. **Inject the fired obligation as a trailing block**, after the tool result, per
   [`honesty-enforcement-design.md`](honesty-enforcement-design.md) — which preserves prefix caching
   and keeps the caveat in the recency-favoured position.
4. **Keep the refusal behaviors separate from the hedges.** `DESTRUCTIVE_REFUSAL`,
   `INJECTION_REFUSAL`, `SECRET_REFUSAL`, `DISCRIMINATORY_DECLINE`, and `OFF_TOPIC_REDIRECT` cannot
   be computed from a SQL result — there is no result. Those five are genuine prompt-resident rules,
   and five is inside the attention budget. **The split is not arbitrary: hedges are functions of
   the data, refusals are functions of the request.**
5. **Grade the string at tier 2 only, never as the binding assertion.** Once the canonical text is
   injected, a grader matching that text is close to tautological. The binding check stays
   structural — *no single job is named as highest-paid* — exactly as the strategy record requires.

### 4c. What would change this answer

- If the obligation mechanism proves unable to detect an obligation that the model detects reliably
  on its own, that specific behavior moves back into the prompt.
- If a future model shows no degradation across ~20 simultaneous instructions, §3a's objection
  weakens and the simpler whole-block approach becomes viable.
- If the corpus ever reaches the low hundreds of scored cases, Method 3 becomes available and the
  hand-tuning question is superseded.

---

## 5. Limits of this record

No prompt experiment was run. The token counts in §1 are measured from the files; the per-turn
projection is arithmetic over a measured per-turn average, not an observed figure. The ~8–10
instruction knee is practitioner guidance, not a result measured on `qwen/qwen3.6-27b` — the
published degradation curves are model-general. The truncation contrast in §4a is a single
two-run observation. Everything here is a design argument to be confirmed by the improve phase,
which is where the injected-caveat relay fidelity is measured for the first time.

---

**Sources** (reviewed 2026-08-12):

- [When instructions multiply - measuring LLM multiple-instruction
  following (ManyIFEval)](https://arxiv.org/abs/2509.21051)
- [Benchmarking complex instruction-following with multiple constraints
  composition (NeurIPS 2024)](https://openreview.net/forum?id=U2aVNDrZGx)
- Prompt anti-patterns - when more instructions may harm performance:
  https://community.openai.com/t/prompt-anti-patterns-when-more-instructions-may-harm-model-performance/1372460
- [Prompt engineering anti-patterns
  2026](https://www.digitalapplied.com/blog/prompt-engineering-anti-patterns-10-mistakes-2026)
- [Redis - prompt bloat: causes, costs and fixes](https://redis.io/blog/prompt-bloat-llm-apps/)
- [Redis - context rot explained](https://redis.io/blog/context-rot/)
- [Lazy-loaded procedural policy
  pattern](https://bechirtr97.medium.com/stop-bloated-agent-prompts-a-pattern-i-call-lazy-loaded-procedural-policy-b6ade44dd1aa)
- [Groq - prompt caching documentation](https://console.groq.com/docs/prompt-caching)
- [How we cut LLM cost with prompt
  caching](https://projectdiscovery.io/blog/how-we-cut-llm-cost-with-prompt-caching)
- [Few-shot examples done
  properly](https://promptingweekly.substack.com/p/few-shot-examples-done-properly)
- Multi-shot vs zero-shot - when adding examples hurts:
  https://dev.to/gabrielanhaia/multi-shot-vs-zero-shot-when-adding-examples-actually-hurts-accuracy-3bd2
- [DSPy compilers - automatic prompt
  optimization](https://www.statsig.com/perspectives/dspy-compilers-prompt-optimization)
- [MIPROv2 in DeepEval](https://deepeval.com/docs/prompt-optimization-miprov2)
- [Braintrust - prompt versioning tools for production
  teams](https://www.braintrust.dev/articles/best-prompt-versioning-tools-2025)
- [Canned responses guide - AI-safe use and fixed compliance
  language](https://www.kommunicate.io/blog/canned-responses-guide/)
