# Active refactor backlog

> **Last verified:** 2026-09-25
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
