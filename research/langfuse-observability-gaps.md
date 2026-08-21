# Langfuse observability gaps and target practice

> **Status:** Research record. Feeds M28 operational telemetry and M29 the production evaluation
> loop in [production readiness plan](production-readiness-plan.md). No decision is taken here and
> nothing below is implemented.

> **Last verified:** 2026-08-21

## 1. Summary

Langfuse is wired as a trace sink and nothing more.
Traces arrive, sessions and users are attached, and eval scores are written back, but every layer
above raw tracing is unused: no prompt registry, no cost, no tags, no environments, no datasets,
no release correlation, no masking.

Two of the reported symptoms have verified root causes in this repository rather than in Langfuse
configuration, and one of them is a bug that no amount of Langfuse dashboard work would fix.

| # | Finding | Severity | Root cause is |
|---|---|---|---|
| F1 | Streamed turns report zero token usage, so cost can never be inferred | High | Code |
| F2 | `deepseek-v4-flash` has no Langfuse model price definition | High | Config |
| F3 | Prompts live only in `config/prompts.yaml`; no prompt is registered or linked | High | Code and process |
| F4 | No tags and no environment, so eval traffic and production traffic are one undifferentiated stream | High | Code |
| F5 | Root traces carry a generic framework name and no trace-level input or output | Medium | Code |
| F6 | `last_trace_id` is read from a process-wide shared handler, so `trace_url` can point at another user's turn | Medium | Code |
| F7 | Eval runs write scores onto isolated traces, never onto a Langfuse dataset run | Medium | Code |
| F8 | No `release` or `version`, so a regression cannot be attributed to a deploy | Medium | Code |
| F9 | User free text and job rows reach Langfuse Cloud unmasked | Medium | Code and policy |
| F10 | Per-request blocking `flush()` on the request path, and no `shutdown()` at process exit | Low | Code |
| F11 | Langfuse credentials are mandatory to boot although tracing is nominally optional | Low | Code |
| F12 | `get_client()` never returns `None`, so every `if client is not None` guard is dead | Low | Code |
| F13 | The nested `generate_sql` call lands as a sibling of the tool span, not a child | Low | Code |

Sections 3 to 15 give one finding each: evidence, what good practice is, and the smallest change
that reaches it.
Section 16 proposes a sequence.
Section 17 lists what a maintainer has to decide before any of it becomes a ticket.

---

## 2. What is wired today

Verified by reading the code on 2026-08-21 against the installed `langfuse 4.6.1`.

| Capability | State | Where |
|---|---|---|
| LangChain callback handler | Wired, process-wide singleton | `src/agents/tracing/langfuse.py:21` |
| Session id on traces | Wired via `langfuse_session_id` metadata | `src/agents/tracing/langfuse.py:36-58` |
| User id on traces | Wired via `langfuse_user_id` metadata | same |
| Trace id and URL returned to the client | Wired, with the race in F6 | `src/agents/runtime/react_agent.py:32-41` |
| Eval score writeback | Wired, per trace | `evals/writeback.py` |
| Tracing kill switch | Wired via `LANGFUSE_ENABLED` | `src/agents/tracing/langfuse.py:15` |
| Token usage and cost | Absent on the streaming path, unpriced everywhere | F1, F2 |
| Prompt management | Absent | F3 |
| Tags | Absent | F4 |
| Environments | Absent | F4 |
| Trace naming and trace IO | Absent | F5 |
| Datasets and dataset runs | Absent | F7 |
| Release and version | Absent | F8 |
| Masking | Absent | F9 |
| Sampling | Absent | F15 |
| Startup credential check | Absent | F15 |

The SDK is v4, which matters: v4 replaced `update_current_trace()` with the `propagate_attributes()`
context manager, unified `start_span` and `start_generation` into `start_observation(as_type=...)`,
and capped propagated metadata values at 200 characters.
Most Langfuse blog material still shows v2 or v3 syntax, so recipes copied from search results will
not run here.

---

## 3. F1: streamed turns report zero token usage

**Severity: high. This is the reason cost is missing, not the model price list.**

`agent.react.streaming` is `true` (`config/settings.yaml:32`) and `/api/v1/agent/chat/stream` is the
demo's primary path, so almost every real turn is a streamed one.

`ChatDeepSeek` inherits `stream_usage` from `BaseChatOpenAI`, whose default is `None`.
`langchain_openai` only promotes that `None` to `True` when the model is built against OpenAI's own
base URL:

```python
# .venv/Lib/site-packages/langchain_openai/chat_models/base.py:1231-1250
if all(getattr(self, key, None) is None for key in ("stream_usage", "openai_proxy", "client", ...)) \
   and (_base_url_from_gateway or (self.openai_api_base is None and "OPENAI_BASE_URL" not in os.environ)):
    self.stream_usage = True
```

`ChatDeepSeek` always sets `api_base` to DeepSeek's endpoint, so `openai_api_base` is never `None`,
so `stream_usage` stays `None`, so `_should_stream_usage()` falls through to
`self.stream_usage or False` and returns `False`.
The request therefore goes out without `stream_options={"include_usage": true}`, DeepSeek sends no
usage chunk, LangChain attaches no `usage_metadata`, and the Langfuse callback has nothing to record.

Consequence: streamed generations show no input or output tokens in Langfuse.
Adding a model price definition (F2) fixes nothing for them, because a price multiplied by absent
usage is still absent.
Non-streamed `ainvoke` turns and the `sql_generation` profile (`streaming: false`) do carry usage,
which is why the gap looks intermittent rather than total.

**Target practice.** Any OpenAI-compatible provider that is not OpenAI needs streaming usage turned
on explicitly.

**Smallest change.** Set `stream_usage=True` in the DeepSeek branch of
`src/agents/runtime/provider.py`, ideally read from a `stream_usage` key in the profile config so a
provider that rejects `stream_options` can turn it off.
`ChatGroq` has no `stream_usage` field and reports usage through its own `x_groq` payload, so the
Groq branch must not receive the same kwarg.

**Verification.** One streamed turn, then confirm the generation in Langfuse shows non-zero input and
output tokens.

---

## 4. F2: `deepseek-v4-flash` has no price definition

**Severity: high.**

Langfuse ships price definitions for OpenAI, Anthropic, and Google models only.
Cost for anything else is either ingested directly on the observation or inferred from a
user-defined model definition, and user-defined models take priority over Langfuse-maintained ones.
Neither exists for `deepseek-v4-flash` or for the Groq arm's `qwen/qwen3.6-27b`, so even the
non-streamed turns that do carry usage show tokens with no money attached.

**Target practice.** Define the model in **Project Settings > Models** with a match pattern such as
`(?i)^deepseek-v4-flash$`, and prices keyed to the same usage buckets the SDK emits (`input`,
`output`, and `input_cached_tokens` if DeepSeek's cache discount is to be tracked).
Usage types are mutually exclusive buckets: cached input tokens belong in their own key, never
subtracted from `input`.

**Two mistakes to avoid.**
Do not define one model per provider arm with an overly broad regex, because the Groq arm is meant
to stay one edit away and a loose pattern will silently misprice it.
Do not treat the Langfuse UI as the source of truth: the definition should be created by a small
idempotent script under `scripts/` so a fresh Langfuse project can be rebuilt, and so the prices sit
in git next to the pricing evidence already captured in
[DeepSeek as an agent provider](deepseek-provider-evaluation.md).

**Verification.** A turn produces a non-zero cost figure whose value matches the published per-token
price times the recorded tokens.

**Sequencing.** F1 must land first, or this change appears to do nothing on the streaming path.

---

## 5. F3: prompts are not registered or linked

**Severity: high.**

Today `config/prompts.yaml` holds three prompt strings plus a hand-bumped `prompt_version: v4`, read
by `src/agents/runtime/prompts.py` and stamped into the eval driver manifest.
Nothing about a prompt reaches Langfuse.
The practical cost is that a trace cannot answer "which prompt produced this", and Langfuse's
per-prompt-version metric views stay empty, which is exactly the view a prompt-refinement milestone
needs.

**Two credible designs.**

*Design A, Langfuse as the editing surface.*
Prompts are authored in the Langfuse UI, fetched at runtime with
`langfuse.get_prompt(name, label="production")`, and the SDK's cache plus a `fallback` argument
covers an outage.
This buys hot prompt edits without a deploy and full version history in the UI.
It costs the repository its single source of truth: `config/prompts.yaml` stops being authoritative,
eval reproducibility now depends on an external service's version history, and a prompt change
becomes invisible to code review.

*Design B, git as the source of truth with Langfuse as the registry.*
`config/prompts.yaml` stays authoritative.
A deploy-time or CI step calls
`create_prompt(name=..., prompt=..., labels=[environment], commit_message=<git sha>)`, which appends
a new version only when the content actually changed.
Runtime keeps loading from YAML and separately attaches the fetched prompt object for linking.

**Recommendation: Design B.**
It preserves review, reproducibility, and the existing eval manifest hash, and it still populates
every Langfuse prompt view.
Design A's one real advantage, editing without a deploy, is worth little on a service that
auto-deploys from `main` and whose prompt changes are gated by a 29-scenario eval.

**Linking is the harder half.**
Langfuse links a prompt to a generation through the `langfuse_prompt` metadata key, and the
documented path sets that key **on a LangChain `PromptTemplate`, not on the LLM call**.
This repository uses neither: `factory.py` passes a plain `SystemMessage` to `create_agent`, and
`generate_sql` builds a bare `HumanMessage`.
There are open Langfuse discussions about exactly this gap for LangGraph, so treat prompt linking
inside the ReAct agent as an unsolved integration question rather than a configuration flip.

The `sql_generation` call is the tractable one, because it is a single direct `model.ainvoke` that
can be wrapped:

```python
with langfuse.start_as_current_observation(
    as_type="generation", name="generate_sql", prompt=langfuse_prompt
):
    response = await model.ainvoke(...)
```

**Recommended scope split.** Register all three prompts (Design B), link `sql_generation` with the
low-level API, and in the same change put `prompt_version` into trace metadata and tags so the
react prompt is at least sliceable even while true prompt linking is unavailable for it.
Say plainly in the ticket that the react system prompt is registered but not linked, and why.

---

## 6. F4: no tags and no environment

**Severity: high. This is the reported "cannot tell eval traffic from real traffic".**

`build_langfuse_config` sets only `langfuse_session_id` and `langfuse_user_id`.
No tag is set anywhere in `src/` or `evals/`.
The eval driver's answer to the same problem is to switch tracing off entirely
(`evals/driver.py:81`, where `LANGFUSE_ENABLED` defaults to `false` for captures), which is a real
cost: the comment in that file records that forcing it off made every captured `trace_id` `None` and
left the viewer's trace field structurally dead.

Langfuse offers two separate mechanisms and the difference matters.

**Environments** are the coarse, hard partition.
`LANGFUSE_TRACING_ENVIRONMENT` (values matching `^(?!langfuse)[a-z0-9-_]+$`, 40 characters max) is
set per process, filters the entire UI from the nav bar, and lets prompts and datasets stay shared
while operational data does not mix.
This is the correct home for `production`, `local`, and `evaluation`.

**Tags** are the fine, per-trace label, set through `langfuse_tags` in metadata or `tags=[...]` on
`propagate_attributes()`.
This is the correct home for facts that vary turn to turn.

**Proposed taxonomy.**

| Axis | Mechanism | Values |
|---|---|---|
| Deployment context | environment | `production`, `local`, `evaluation` |
| Entry point | tag | `api:chat`, `api:chat-stream`, `eval:driver`, `eval:spike` |
| Prompt lineage | tag | `prompt:v4` |
| Provider arm | tag | `provider:deepseek`, `model:deepseek-v4-flash` |
| Scenario | tag, eval only | `scenario:<id>`, `repeat:2` |

Keep the tag set small and closed.
An unbounded tag vocabulary is the standard way these become unusable, so the list belongs in
`config/settings.yaml` or a module constant, not in ad-hoc call sites.

**Second-order benefit.** Once eval traces are partitioned by environment, the driver no longer
needs `LANGFUSE_ENABLED=false` as its isolation mechanism, and captured `trace_id` values become
real again, which unblocks the score writeback path for every capture rather than only for opt-in
runs.

---

## 7. F5: root traces are unnamed and carry no trace-level IO

**Severity: medium.**

With only a callback handler attached, the root trace takes its name from the LangGraph runnable, so
the Langfuse trace list is a wall of identical rows.
There is also no trace-level input or output, so the list view cannot show what the user asked or
what the agent answered without opening each trace.

**Target practice in v4:**

```python
from langfuse import propagate_attributes

with propagate_attributes(
    trace_name="agent-chat-stream",
    session_id=session_id,
    user_id=user_id,
    tags=[...],
    version=prompt_version,
):
    ...
```

`propagate_attributes()` also supersedes the current metadata-key approach for session and user, so
this is a consolidation rather than an addition.
Note the v4 constraint: propagated `metadata` is `dict[str, str]` with 200-character values, and
longer values are dropped with a warning, so do not try to push a whole query into it.

Trace IO is the other half.
`set_current_trace_io()` exists in v4 but is documented as deprecated legacy, so confirm the current
recommended path before building on it rather than assuming.

---

## 8. F6: `last_trace_id` is read from a shared handler

**Severity: medium. Correctness, not cosmetics.**

`src/agents/tracing/langfuse.py:21` creates exactly one `CallbackHandler` for the process, and both
`AgentRuntime.ainvoke` and `AgentRuntime.astream` read `handler.last_trace_id` after the run
(`react_agent.py:32`, `:75`).
`last_trace_id` is an instance attribute overwritten by every run that handler observes.
The Langfuse docs themselves warn that care is needed where a handler is reused concurrently.

The service is async FastAPI with a rate limit of 15 per minute per address and no per-request
handler, so two overlapping turns will write the same attribute.
The failure is silent and user-visible: the `trace_url` handed back in the response can belong to
another in-flight request's trace.

**Target practice.** Read the trace id from inside the run's own context with
`langfuse.get_current_trace_id()` under the `propagate_attributes()` scope from F5, or mint the id
up front with `create_trace_id()` and pass it via `CallbackHandler(trace_context=...)`.
Either removes the shared mutable read.
Constructing a fresh `CallbackHandler` per request is a third option but repeats the handler's setup
on every turn.

**Verification.** Two concurrent streamed requests with distinct session ids return distinct
`trace_url` values, each resolving to a trace whose input matches its own query.

---

## 9. F7: eval runs do not create dataset runs

**Severity: medium.**

`evals/writeback.py` does the right thing at the wrong granularity.
It writes each metric as a score onto one trace, keyed `f"{seam}/{metric}"`, with a deterministic
`score_id` so a re-run is idempotent.
What it never does is group a capture into a **dataset run**, so Langfuse has no notion that 29
scenarios belong to one evaluation, and the run-over-run comparison view stays empty.
All aggregate reasoning happens instead in the driver's JSON artifacts and the local viewer.

**What Langfuse offers.** `create_dataset` and `create_dataset_item`, then either
`dataset.run_experiment(name=..., task=..., evaluators=[...], run_evaluators=[...])` or the local
form `langfuse.run_experiment(data=[...], ...)`.
Run-level evaluators produce the aggregate metric, `metadata` on the run attaches configuration,
and the UI gains side-by-side run comparison.

**Honest tradeoff, and this one is not obvious.**
`evals/driver.py` already owns retry accounting, quota backoff, turn pacing, checkpoint and resume,
and a hashed manifest, and `run_experiment(max_concurrency=...)` owns concurrency in a way that
conflicts with all of it.
Migrating wholesale would trade a purpose-built harness for a general one and would probably lose
the resumability that made long captures survivable.

**Recommended shape: adopt the data model, not the runner.**
Mirror `evals/scenarios_v1.yaml` into a Langfuse dataset, keep the existing driver as the executor,
and have the driver create a dataset run per capture and pass its `dataset_run_id` to
`create_score`, which `create_score` already accepts as a first-class argument.
Add `metadata={"prompt_version": ..., "scorer_version": ..., "provider": ...}` on each score so a
score is self-describing.
Also define score configs in Langfuse for each metric name so ranges and data types are enforced
rather than conventional.

---

## 10. F8: no release or version attribute

**Severity: medium.**

The `Langfuse` constructor accepts `release=` and `propagate_attributes()` accepts `version=`, and
neither is used.
Without them there is no way to ask whether a quality change coincided with a deploy, which is the
first question anyone asks about a regression on a service that auto-deploys from `main` (D-027).

Render exposes the deployed commit as `RENDER_GIT_COMMIT`, so `release` costs one line.
`version` is the natural home for `prompt_version`, which pairs with F3 and F4.

---

## 11. F9: nothing is masked

**Severity: medium. Policy question, not only a code question.**

Every user query, every generated SQL string, every returned job row, and every model answer is sent
verbatim to Langfuse Cloud in Japan (D-029).
Users of a job-search assistant type salary expectations, employer names, and sometimes personal
details into free text.
There is no `mask=` function on the client, no redaction, and no documented retention position.

Note the asymmetry already present in the repo: `evals/sanitization.py` enforces a
`FORBIDDEN_CONTENT` pattern so eval artifacts cannot leak connection strings, API keys, or trace ids,
yet the request path applies no equivalent rule to what leaves the process.

**Target practice.** Pass `mask=` to the `Langfuse` constructor.
The function receives each input and output before export and returns the redacted form, which
makes it the single chokepoint for a redaction policy.
A reasonable first policy is to redact anything matching the existing `FORBIDDEN_CONTENT` pattern,
plus email addresses and phone numbers.

**Decide explicitly whether full user text should be stored at all.**
Storing it is what makes production evaluation (M29) possible, so the answer is probably yes with
redaction, but that should be a recorded decision rather than an accident of defaults.

---

## 12. F10: flush on the request path, no shutdown at exit

**Severity: low, but it is on the hot path.**

Both `ainvoke` and `astream` call `await asyncio.to_thread(client.flush)` before returning
(`react_agent.py:36`, `:79`).
`flush()` blocks until the export queue drains, so every turn pays a network round trip to Japan
before the user sees the final metadata event, on a free-tier service in Singapore.

The flush is not needed to build the URL: `get_trace_url()` is local string construction.
It is only needed so that a user clicking the link immediately does not hit a not-yet-ingested trace.
That is a real concern for the demo's "view the trace" affordance, so this is a genuine tradeoff
rather than a clear defect.

**Recommendation.** Keep the flush on the non-streaming `ainvoke` path if the demo needs it, and on
the streaming path move it after the metadata event is yielded, so it stops sitting between the last
token and the user.

The complementary gap is one-directional and clearly a defect: the FastAPI lifespan in
`src/api/app.py:44-56` closes the checkpointer pool but never calls `langfuse.shutdown()`, so
whatever is queued when Render restarts the container is lost.
Add it to the `finally` block.

---

## 13. F11 and F12: the enable and disable paths are inconsistent

**Severity: low.**

`Settings` declares `LANGFUSE_SECRET_KEY: str` and `LANGFUSE_PUBLIC_KEY: str` with no default
(`src/core/config.py:27-28`), so the process cannot boot without them, while
`src/agents/tracing/langfuse.py:16` carefully handles the case where they are missing and logs
"tracing disabled: missing Langfuse credentials".
That branch is unreachable in any process that got far enough to run it.
Either make the keys `str | None` and keep the graceful path, or drop the graceful path and state
that Langfuse credentials are a hard boot requirement.
The current pair says both.

Separately, `get_langfuse_client()` returns `get_client()`, which in v4 always returns a client
object, disabled or not.
So every `if client is not None` in `react_agent.py` is dead, and a misconfigured deployment
silently produces no traces with no error anywhere.
The v4 idiom is `tracing_enabled=False` on the constructor plus an explicit `auth_check()` at
startup.

---

## 14. F13: the SQL generation span is a sibling, not a child

**Severity: low. Already understood, not yet fixed.**

`evals/harness.py:211-234` documents the mechanism at length: LangChain's `@tool` machinery injects
the parent node's `RunnableConfig` verbatim rather than a child-scoped one, so the nested
`generate_sql` model call lands as a sibling of the `query_clean_jobs` tool span rather than
underneath it.
The harness works around it by matching on `parentUuid`.

The trace tree in the Langfuse UI is wrong in the same way, which makes a trace harder to read than
the actual control flow warrants.
Wrapping the call in an explicit `start_as_current_observation` inside `generate_sql` fixes the tree
and is the same wrapper F3 needs for prompt linking, so these two should ship together.

---

## 15. F15 and the remaining smaller items

- **No sampling.** `sample_rate` is unset. Fine at demo volume; it is the first knob to reach for if
  the Hobby plan's ingestion limits ever bind, and it should be config-driven before it is needed.
- **No startup credential check.** `auth_check()` at lifespan startup, logged and not raised, would
  turn a silent no-trace deployment into one line in the boot log. The `/api/v1/health` response is a
  hardcoded literal today and could report tracing state.
- **`LANGFUSE_BASE_URL` defaults to `http://localhost:3000`** in `config.py:29` while D-029 records
  Langfuse Cloud as the decision. A missing environment variable in production therefore fails
  toward a local address rather than loudly.
- **v4 span filtering is unverified here.** v4 exports only spans it considers LLM-relevant by
  default, configurable through `should_export_span`. Whether the LangGraph tool and node spans this
  project relies on survive that default has not been checked and should be, before any conclusion
  is drawn from a trace looking sparser than expected.
- **No user feedback scores.** Already scoped as T0029.1 in
  [production readiness plan](production-readiness-plan.md); listed here only so the picture is
  complete.

---

## 16. Proposed sequence

Ordered so that each step is verifiable on its own and no step depends on a later one.

| Step | Change | Unblocks |
|---|---|---|
| 1 | `stream_usage` for the DeepSeek branch (F1) | Any cost figure at all |
| 2 | Model price definitions via a script under `scripts/` (F2) | Cost in currency |
| 3 | Environment plus the closed tag taxonomy (F4), `release` and `version` (F8) | Separating eval from production; deploy correlation |
| 4 | `propagate_attributes()` consolidation: trace name, session, user, tags, version (F5), and trace id read from context (F6) | Correct `trace_url`; a readable trace list |
| 5 | Lifespan `shutdown()`, flush repositioning, `auth_check()` (F10, F15) | No lost traces on redeploy |
| 6 | Prompt registration from YAML plus the `generate_sql` observation wrapper (F3, F13) | Per-prompt-version metrics; a correct trace tree |
| 7 | Masking function and the retention decision it implies (F9) | Storing real user text defensibly |
| 8 | Dataset mirror and `dataset_run_id` on scores (F7) | Run-over-run comparison in Langfuse |

Steps 1 and 2 together are the whole of the reported cost problem and are the cheapest.
Step 3 is the whole of the reported tagging problem.
Step 6 is the reported prompt problem, minus the part that Langfuse and LangGraph have not solved
between them.

---

## 17. Open questions for the maintainer

1. **Prompt source of truth.** Design B (git authoritative, Langfuse as registry) is recommended in
   section 5. Confirm, because Design A changes what a pull request means for a prompt change.
2. **Retention and masking policy.** Should full user text be stored in Langfuse Cloud at all, and
   if so under what redaction rule? Section 11 cannot be scoped without this answer.
3. **Eval traces on or off.** Section 6 argues environments make `LANGFUSE_ENABLED=false` unnecessary
   for captures, and that turning them back on restores real `trace_id` values. This spends
   Hobby-plan ingestion quota on eval traffic; confirm that is acceptable.
4. **Dataset ownership.** If `evals/scenarios_v1.yaml` is mirrored into a Langfuse dataset, the YAML
   stays authoritative and the mirror is derived. Confirm that direction, and that a drifted mirror
   is a lint failure rather than a merge of the two.
5. **Cost as a gate.** The production readiness plan puts latency and cost gating explicitly out of
   scope until drift is observed. Nothing here changes that; F1 and F2 only make the baseline
   measurable.

---

## 18. Sources

Langfuse documentation, retrieved 2026-08-21:

- [Python SDK v3 to v4 upgrade path](https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4)
- [LangChain and LangGraph tracing](https://langfuse.com/integrations/frameworks/langchain)
- [Token and cost tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking)
- [Environments](https://langfuse.com/docs/observability/features/environments)
- [Tags](https://langfuse.com/docs/observability/features/tags)
- [Metadata](https://langfuse.com/docs/observability/features/metadata)
- [Prompt management, get started](https://langfuse.com/docs/prompt-management/get-started)
- [Linking prompts to traces](https://langfuse.com/docs/prompt-management/features/link-to-traces)
- [Experiments via the SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
- [Prompt management with LangChain, Python cookbook](https://langfuse.com/guides/cookbook/prompt_management_langchain)
- [Discussion 11825, linking prompts to traces with LangGraph](https://github.com/orgs/langfuse/discussions/11825)
- [Discussion 12190, linking prompts when invoking LangGraph nodes directly](https://github.com/orgs/langfuse/discussions/12190)

Local evidence, read on 2026-08-21: `langfuse 4.6.1` and `langchain-openai 1.5.0` as installed in
`.venv`, and the repository files cited inline.
