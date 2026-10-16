# Active refactor backlog

> **Last verified:** 2026-10-16
>
> **Eviction:** An item leaves this list when its focused issue is completed, declined, or superseded
> by an approved decision.

This is an ordered decision and migration backlog, not a replacement inventory.
Only the first item is the candidate next vertical slice.
Each item requires its own approved implementation issue before code changes begin.

| Order | Candidate boundary | Evidence | Required decision and evidence before implementation | Explicitly out of scope |
| --- | --- | --- | --- | --- |
| 1 | Replace the application's concrete tracing dependency | D-427-03 identifies `StreamLatency` imported by `src/agents/service.py`. | Define observation ownership and the streaming completion contract. Characterize success, error, timeout, and cancellation telemetry. | Changing Langfuse configuration, hosted traces, or stream semantics. |
| 2 | Separate command configuration from serving configuration | D-427-04 identifies the ingestion path's dummy `AGENT_DATABASE_URL`. | Inventory required settings for each command and approve command-specific configuration contracts. | Ingestion activation, data collection, database topology, or deployment changes. |
| 3 | Centralize model construction policy | D-427-10 identifies model construction in runtime and query-tool paths. | Define model and tool contracts, then measure quality, latency, cost, privacy, and provider failure behavior. | Provider selection, credential, prompt, or runtime behavior changes. |

The evidence identifiers refer to the preserved
[debt register](../discovery/current-state-debt-register.md).
Unknown production behavior remains unknown and must not be inferred from static source evidence.

## Closed parallel exception: the agent-v0 track

Approved by the maintainer on 2026-09-29 against
[#472](https://github.com/Park-Hip/InternHunterAgent/issues/472), and closed on 2026-10-16.

The agent-v0 track ran in parallel with this list for documentation, dataset, and additive tool
work, and on 2026-09-30 the maintainer extended it to one serving-path change: the paired prompt and
tool cutover in [#486](https://github.com/Park-Hip/InternHunterAgent/issues/486), gated by the
single `agent.agent_v0` switch.

[ADR-0060](../decisions/adr-0060-retire-the-agent-v0-bundle.md) reverses that serving-path decision
and retires the switch, so this exception no longer authorizes anything and its track is closed. Its
six `docs/refactor/agent-v0-*` records are retired with it. The v0 contract's guarantee - no false
success, no false refusal - is not carried forward; ADR-0060 records the false-success risks the
remaining SQL path accepts and names the evaluation gate that must replace the retired v0 gate.

#447's separation of command from serving configuration is still outstanding and still blocks any
other serving-path work.
Any interaction between a future query-path change and the tracing replacement (item 1) is resolved
by the maintainer before item 1 starts, because both reach the same serving composition.
