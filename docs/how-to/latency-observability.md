# Latency observability

> **Last verified:** 2026-09-02

> **Eviction:** This guide leaves when request telemetry is replaced by a reviewed, equivalent measurement contract.

The streamed chat request span (`agent-chat-stream`) carries application timing metadata. These are server-side measurements for diagnostic and later percentile analysis; they are not a public latency claim.

## Metric definitions

All application values are integer **milliseconds** and use a monotonic clock:

| Field | Definition |
|---|---|
| `server_e2e_ms` | From creation of the application stream iterator (after request validation) to the final emitted SSE `done` boundary for successful or error streams, or to cancellation on client disconnect. |
| `user_visible_ttft_ms` | From that same start to the first emitted SSE `token` event. Hidden/reasoning chunks and tool-call chunks are filtered before this point. The application fallback answer is a visible token and is included. |
| `stream_completion_ms` | From that same start to the final emitted SSE `done` boundary for successful or error streams, or to cancellation on client disconnect. It equals `server_e2e_ms` for this MVP. |

`latency_unit` is always `ms`. Do not mix these fields with Langfuse generation `timeToFirstToken` or provider streaming latency: those provider measurements can begin on a hidden/reasoning chunk and are intentionally separate from `user_visible_ttft_ms`.

## Dimensions and exclusions

Each measurement is attached to the active Langfuse request span with `outcome` (`success`, `error`, or `cancelled`), `environment`, and configured serving `model`. Existing Langfuse tags also retain provider and model attribution.

`cold_start` is deliberately narrow: `process-first-agent-request` is only the first streamed agent request observed by this Python process; later streamed requests are `warm`. It is **not** a claim that the Render container was cold or that upstream/database connections were cold. Process restarts and multi-worker deployments must be partitioned accordingly.

A stream that errors before emitting a visible token has `user_visible_ttft_ms: null`. No client network time, browser render time, request validation failure, provider-native TTFT, or Langfuse export/flush time is included. Client disconnects are recorded as `cancelled` when the runtime stream is closed.

## Percentile publication gate

Do not publish P90 or P95 from this telemetry until there is a sufficiently sized production sample (at least 100 successful, warm requests in one environment/model partition) and an independent validation has compared server timing with client-observed SSE timing. Exclude errors, cancellations, and process-first-agent-request observations from a normal warm-success percentile; report those partitions separately if they are ever analyzed.
