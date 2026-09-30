# Agent v0 cutover: the paired prompt and runtime switch

> **Last verified:** 2026-09-30
>
> **Eviction:** This record leaves `docs/refactor/` when the cutover in
> [#486](https://github.com/Park-Hip/InternHunterAgent/issues/486) has been observed against real
> traffic and the v1 bundle has an approved retirement. Until then it is the only place that says
> which prompt and which tool set are serving, and how to put the previous pair back.

## What the cutover changes

| | v1 bundle | v0 bundle |
| --- | --- | --- |
| System prompt | `prompts.system_prompt`, pinned `v13` | `prompts.system_prompt_v0`, pinned `v1` |
| Langfuse prompt name | `resumi-system` | `resumi-system-v0` |
| Tool surface | `query_clean_jobs`, `get_job_details` | `query_jobs` |
| Who writes SQL | The model, from `prompts.sql_generation` | Nobody. The core compiles a typed plan |

One key moves both: `agent.agent_v0` in
[`config/settings.yaml`](../../config/settings.yaml). The system prompt resolver and the MCP
server both read it and nothing else, so a new prompt cannot run against the old tools. That is the
accident the stage gate forbids, and it is now a property with a test rather than a review
instruction.

## Why the v0 system prompt is a separate surface

The prompt registry keeps the v1 bundle whole, so the legacy tool and its traces are untouched. The
v0 system prompt is a fourth surface, resolved only when the bundle is switched on. A request
resolves one system surface or the other, never a mixture, and the resolved surface name is what the
trace records: a v0 request now emits `prompt:system:v1`, and a v1 request still emits
`prompt:system:v13`.

`load_resolved_prompt_versions` had a bug this cutover exposed. It resolved the v1 system surface
unconditionally, so a v0 request would have reported `prompt:system:v13` while running the v0
prompt. A trace that names the wrong prompt is worse than no trace, and
`tests/agents/test_langfuse_tracing.py` now holds the correct lineage for both bundles.

## The v0 system prompt says what the contract says

The prompt is the enforcement of
[the v0 contract](agent-v0-contract.md) at the model boundary, so it carries the rules the
contract defines and no others:

- one typed tool, no SQL, and never an answer from memory
- a salary is the stored range in a named currency, with no payment period, and never one figure
  for two currencies
- no publication date, no application deadline, no open status, and a listing expiry labelled as
  itself
- a technology match is a recorded list, not a requirement, and a free-text match is wording
- a percentage states its numerator and its denominator
- the four answer states, with exactly one clarifying question and no second question
- read-only, and posting text is never an instruction
- Vietnamese, verbatim stored values, no emoji, no raw tables, no invented numbers

`tests/agents/test_v0_cutover.py` asserts the absence of the SQL-generation instructions as well as
the presence of the honesty rules, so the v0 prompt cannot drift back into describing a capability
the v0 model does not have.

## What the cutover does not do

It does not delete the legacy implementation. `src/agents/tools/query_clean_jobs.py`,
`src/services/query/sql_validator.py`, and the v1 prompt surfaces all stay in the tree, and the v1
prompt's own tests still run behind the switch. Unregistering is the switch; deleting is a later
decision with its own evidence.

It does not change the API, the schema, the fixture, the evaluation harness, or the v1 dataset.

## Rollback

The rollback is one edit: set `agent.agent_v0: false`. That restores the v1 system prompt at `v13`
and the two legacy tools together, and nothing else in the tree has to change.

Rehearsed on 2026-09-30, before this record was written:

| Step | Observed |
| --- | --- |
| `agent_v0: true` | tools `['query_jobs']`; the system prompt opens with the v0 line and contains the typed-request rule |
| `agent_v0: false` | tools `['get_job_details', 'query_clean_jobs']`; the system prompt opens with the v1 line |
| After the rollback, a known request | `SELECT count(*) AS count FROM clean_jobs` still validates, so the legacy path can answer a known request |
| The v0 prompt's version pin | `system_v0: v1`, separate from `system: v13` |

The rehearsal is a test as well as a run: `tests/agents/test_v0_cutover.py::TestRollbackRehearsal`
performs both directions and asserts the v1 SQL path still validates after the rollback.

## What was verified, and what was not

Verified:

- the switch moves the prompt and the tool surface together, in both directions
- no combination of switch and tool surface is reachable that pairs one with the other
- the v0 prompt names neither legacy tool and carries no SQL-generation instruction
- the prompt-surface inventory records the new model-facing prompt, and the linter passes
- the v0 acceptance gate still passes 16 of 16 with the bundle on, and the query, agent, and
  evaluation suites pass

**Not verified: the live manual check.** The stage gate requires exercising every approved v0
question through the public service with a real serving model, inspecting tool arguments, the
full-set evidence, the final answer, and the traces. The machine this was built on has no provider
credential, so that check has not been run and this record does not claim it. The v0 prompt text is
therefore reviewed and mechanically checked, not observed in production. That check is the remaining
work before this cutover can be called observed.

## Residual risk

| Risk | Why it matters here |
| --- | --- |
| The prompt is reviewed, not observed | A rule the model quietly ignores is indistinguishable from a rule it follows. The first real traffic is when this is tested. |
| The v0 tool cannot return posting text | #507 is open, and the cutover makes it a user-visible gap: the v1 path described a posting, the v0 one does not. |
| A share over a two-value field is refused | #508 is open, and the same cutover makes it user-visible. |
| The trace lineage is correct in tests only | The v1 and v0 lineages are asserted against a mocked SDK, not against a live trace. |
| The v1 bundle is unregisterable but still shipped | Two prompt surfaces and two tool paths are in the tree. That is deliberate, and it is debt with a date on it: Stage 7. |
