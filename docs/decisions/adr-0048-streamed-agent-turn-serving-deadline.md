# Each streamed agent turn has an end-to-end serving deadline

> **Status:** Active · **Decided:** 2026-08-27

## Decision

Each SSE agent turn is bounded by `agent.stream_turn_timeout_seconds`, set to 120 seconds by
default. The application-service stream owns the deadline, rather than the FastAPI route or an
individual provider. This bounds the complete runtime turn, including agent orchestration and tool
work, while keeping the HTTP layer independent of how the agent is built.

When the deadline expires, the service cancels the in-flight runtime event without waiting for
its generator cleanup to finish. This keeps delayed cancellation cleanup from extending the serving
deadline. A connected client receives exactly one safe in-band `error` event followed by `done`; it
does not receive provider details or an abruptly incomplete protocol. Missing, non-integer, boolean,
or non-positive configuration values deterministically use the 120-second fallback, preserving the
bound during configuration drift.

## Consequences

The deadline is a serving availability limit, not a provider timeout or retry policy. A later
provider-specific tuning change must remain inside the bounded turn. Operators may lower the value
for a controlled non-production stall check; after expiry, a subsequent request must be accepted by
the single web worker. Reverting this decision means removing the application-service deadline and
its configuration setting together.
