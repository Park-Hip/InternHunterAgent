# Streamed generation stops when its client disconnects

> **Status:** Active · **Decided:** 2026-08-27

## Decision

The SSE route polls the request disconnect state while awaiting each service-stream event. On a
disconnect it cancels and closes the service generator; that cleanup propagates cancellation to the
runtime producer and closes its tracing scope before flushing. The route emits one
`stream.client_disconnected` operational log and sends no further SSE event.

## Consequences

Connected clients retain the pinned `session`, token, metadata, `done` sequence. A disconnected
turn has no resume, replay, or partial-response persistence. This is independent of the serving
deadline: disconnect cleanup is client-driven, while the deadline remains the availability bound for
connected turns. Reverting this decision removes the route disconnect watcher and its cancellation
cleanup while leaving the stream contract unchanged for connected clients.
