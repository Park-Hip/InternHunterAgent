# SSE comments keep silent streams alive

> **Status:** Active · **Decided:** 2026-08-27

## Context

A streamed agent turn can be silent while the runtime performs tool work. Normal proxy idle windows
can close that otherwise healthy connection before the next token reaches the browser. The existing
POST/fetch stream deliberately does not reconnect: retrying a non-idempotent agent request could
run it again.

## Decision

The API route emits the protocol-valid SSE comment `: ping\n\n` whenever its upstream event iterator
has been idle for the positive finite, repository-configured `api.stream_heartbeat_seconds` interval.
The route continues to poll for client disconnects while the upstream stream is idle; a disconnect
cancels the pending receive and closes the service generator before any further comment or event is
emitted. Comments are not application events, so the existing `session`, `token`, `metadata`,
`error`, and `done` event vocabulary, payloads, order, and client behavior stay unchanged.

## Consequences

A temporarily silent stream remains active through normal proxy idle windows without a browser-side
ping, reconnect, replay, persistence, or SSE encoder change. The interval is operationally tunable
in `config/settings.yaml`; invalid values fail during settings load and application startup. Reverting
the iterator wrapper and its configuration restores the prior wire behavior without a migration or
client rollback.
