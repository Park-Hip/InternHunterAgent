# User-facing copy at the public boundary is server-owned Vietnamese

> **Status:** Active · **Decided:** 2026-10-17

## Context

The demo is a Vietnamese-language product: the page, the client's own failure copy, and the agent's
prompt all speak Vietnamese.
Three failure-path strings were still English: the empty-answer fallback (`FALLBACK_ANSWER`), the
provider-pressure and deadline message (`BUSY_MESSAGE`), and the unclassified-failure message
(`GENERIC_ERROR_MESSAGE`).
The web client renders `error.message` verbatim as the agent's reply, and the one-shot routes and
the rate limiter return the same text in HTTP `detail`, so an English sentence reached the reader
(documented in the runtime guide, section 6).

The fallback is the deciding case.
It is sent as an ordinary `token`, not an `error`, so it carries no `code` for a client to map from;
the server must own its wording whatever happens to the error messages.
The client additionally has to recognise it to show the designed no-answer card, today by exact
text, a silent-breakage contract pinned only by `tests/api/test_static_serving.py`.

## Decision

The server owns the user-visible copy at the public boundary and sends Vietnamese for all three
messages.
`FALLBACK_ANSWER` in `src/agents/service.py` and `BUSY_MESSAGE` and `GENERIC_ERROR_MESSAGE` in
`src/core/errors.py` are Vietnamese literals, and every surfacing path (`token`, SSE
`error.message`, HTTP `detail` on 400/429/500/503) carries them unchanged.
The web client stays a pure consumer of the public contract: it renders `message` verbatim and
mirrors the fallback text only to recognise the empty-answer outcome.
The machine-readable interface is unchanged: `type`, `code`, `retryable`, and HTTP status codes
remain the stable way to handle a failure, and `message` remains a free-text string.
No i18n framework, no `Accept-Language` negotiation, and no client-owned copy table are introduced;
the product is Vietnamese-only.

## Consequences

Copy changes in one place, the server, and the stream contract keeps its exact shape.
An external API client that asserted the old English text must re-read `message`; programmatic
handling was never meant to key on it, and no such client is known.
The client's exact-text mirror of the fallback remains the one brittle seam until the empty-answer
outcome gets a stable stream signal, which is a public contract change tracked with the typed-event
work (#679).
Reverting the three literals restores the previous English copy without touching schema,
configuration, or stored state.
