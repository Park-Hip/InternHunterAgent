# Each streamed agent turn has an end-to-end serving deadline

> **Status:** Active · **Decided:** 2026-08-27 · **Amended:** 2026-10-17

## Decision

Each SSE agent turn is bounded by `agent.stream_turn_timeout_seconds`, shipped as 120 seconds in
`config/settings.yaml`. The application-service stream owns the deadline, rather than the FastAPI route or an
individual provider. This bounds the complete runtime turn, including agent orchestration and tool
work, while keeping the HTTP layer independent of how the agent is built.
The non-streaming `POST /api/v1/agent/chat` turn is bounded by the same setting and the same
application-service layer (amended 2026-10-17 by #659): cancelling the runtime call the same way and
reporting expiry as an HTTP `503` retryable `provider_busy` response, rather than introducing a
second setting or a route-level timeout.

When the deadline expires, the service cancels the in-flight runtime event without waiting for
its generator cleanup to finish. This keeps delayed cancellation cleanup from extending the serving
deadline. A connected client receives exactly one safe in-band `error` event followed by `done`; it
does not receive provider details or an abruptly incomplete protocol. The value is validated once
when settings load, so a missing, non-integer, boolean, or non-positive value refuses boot instead
of falling back (amended 2026-10-17 by #656): the bound can only ever be a reviewed value, and
configuration drift fails loudly rather than silently resetting the deadline.

## Consequences

The deadline is a serving availability limit, not a provider timeout or retry policy. A later
provider-specific tuning change must remain inside the bounded turn. Operators may lower the value
for a controlled non-production stall check; after expiry, a subsequent request must be accepted by
the single web worker. Reverting this decision means removing the application-service deadline and
its configuration setting together.
