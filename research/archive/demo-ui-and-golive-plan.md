# Demo UI & Go-Live Plan: Decision Record (archived)

> Archived 2026-08-11. M18 shipped. Outcome owned by
> `docs/MVP_Technical_Design.md` section 11 and D-002, D-003, and D-004.
> Preserved for the reasoning and rejected alternatives; not implementation guidance.

## Decisions taken

- D-002: Browser SSE over POST uses fetch and ReadableStream.
- D-003: The demo UI is static and same-origin with FastAPI.
- D-004: The demo is an editorial vanilla front end.

## 0a. Decisions locked (2026-07-14, with the user)

| Decision | Locked choice | Rationale |
|---|---|---|
| **Visual direction** | **Editorial** | portfolio piece; keeps focus on the agent's answer |
| **UI location (the fork)** | **Same-origin static via FastAPI** | no CORS exercised; one deploy unit |
| **Authoring style** | **Vanilla** HTML/JS/CSS (no build step) | single page; "polish" is ~95% CSS |
| **SSE consumption** | **`fetch()` + `ReadableStream`** + tiny in-app parser | POST+body; no auto-reconnect footgun; zero dependency |
| **Topology + ceiling** | **Render + Neon + Langfuse Cloud Hobby**, **$10/mo** hard ceiling | deployment research points here |

## 2. The UI-location fork (the decision T0018's stub said to settle first)

The stub names the fork: **FastAPI `StaticFiles` same-origin vs. a separate Vite SPA.**
It determines whether CORS is exercised, the serving model, and the UI sub-ticket shape.

| Axis | (A) Same-origin static via FastAPI | (B) Separate SPA |
|---|---|---|
| CORS | **Never exercised** - same origin. `allowed_origins: []` stays empty. | **Exercised** - must fill `allowed_origins` with the SPA's exact origin. |
| Deploy units | **One** (the FastAPI container serves API + UI) | **Two** (API host + static host) + a cross-origin config to keep in sync |
| Cold-start story | One cold start (the API) | Two independent cold-start/uptime surfaces to reason about |

The same-origin choice keeps `allowed_origins` empty and serves the API and UI from one deployed
container.
A separate SPA adds deployment coordination, exact-origin configuration, and another cold-start
surface without improving the demo's core experience.

## 3. Browser SSE consumption - the `EventSource`-vs-`POST` problem

**Why option 2 fits perfectly:** our event contract already did the hard part.
The stream is **self-terminating** (`done` is mandatory and always sent) and **errors are
in-band** (`event: error`, not an HTTP status, because 200 is already sent).
A `fetch()` reader that stops on `done` and renders `error` as a bubble needs no reconnection
logic at all.
The auto-reconnect that makes `EventSource` convenient is precisely the behavior that would hurt
us, so giving it up is a *feature*.

The parser reads SSE blocks separated by a blank line, dispatches `event:` and `data:`, pins the
first returned session, appends token text, shows a trace link on metadata, renders errors as an
error bubble, and stops on `done`.

> **Decision to record:** consume the stream with **`fetch()` + `ReadableStream`** and a small
> in-app SSE parser. No native `EventSource`, no GET variant, no `fetch-event-source`
> dependency.

## 4. The UI itself - "not too boring," no mandatory build step

**Authoring style - recommendation: single-file vanilla, upgrade to framework only if wanted.**

- A hand-written `index.html` + one `app.js` + one `styles.css` (or all inlined) delivers
  everything the demo needs: streaming bubbles, a header, a disclaimer line, canned-prompt
  chips, an error state, a "view trace" link.
  Modern CSS makes "polished" easy with no framework.
- If a framework is preferred for the resume signal, build-to-static (Vite -> `dist/`) and
  serve it the same way (section 2).
  This is a *taste* call, not an architecture one - both land as static files behind FastAPI.

The UI has streaming answer, conversation continuity, view-trace, mid-stream failure,
pre-stream failure, and data-provenance states.
Canned prompts demonstrate freshness caveats, negotiable salaries, clean refusal behavior, and a
grounded happy path.

## 5. Go-live blockers folded in (the small glue T0017 punted to T0018)

### 5.3 DB readiness probe (ops hygiene - do it)

`src/api/routes/health.py` does not touch the DB.
Add a readiness path that runs `SELECT 1` against Postgres so the platform health check catches a
*dead DB*, not just a live process.

### 5.1 Server-issued session IDs (correctness - do it)

`session_id` is client-supplied and optional, and the service already mints one when it is absent
and returns it.
The gap is that a client can still supply an arbitrary id and it is used directly as the LangGraph
checkpointer thread key.
The UI omits `session_id` on the first turn and reuses the server-issued one thereafter.
The server mints an unguessable id and treats a client-supplied one as advisory only for the demo.

### 5.2 Data disclaimer (provenance - do it, trivial)

The corpus is scraped real listings with real company names and salaries.
An always-visible note states: "Demo data: a snapshot from {date} of public job listings; may be
inaccurate or out of date."
The date is the snapshot date of the shipped corpus.

The disclaimer makes provenance and possible staleness visible without making the agent invent a
freshness answer.
It is deliberately static in the initial demo because the corpus is a static snapshot.

### 5.5 Topology + first deploy (blocking the "clickable" part)

API on Render (or Cloud Run), Postgres on Neon, tracing on Langfuse Cloud Hobby ($0),
target $0-$10/mo.
Ingestion cron (GitHub Actions) is a **separate later milestone** - the v1 demo ships a
**static corpus snapshot**, so no cron is needed to go live.

### 5.4 CORS origins (moot under the recommended fork)

T0016.1 left `allowed_origins: []`.
If same-origin is selected, leave it empty - CORS is never exercised.
Only fill it if the separate-SPA fork is chosen against the recommendation.

## 6. Proposed sub-ticket split

**Recommended split: three sub-tickets** - T0018.1 go-live glue, T0018.2 the static chat UI,
T0018.3 deploy topology + first deploy, with the CORS-origins decision absorbed by whichever way
the fork lands.

- **T0018.1:** server-issued sessions, the data disclaimer, and a DB readiness probe.
- **T0018.2:** same-origin static serving and the editorial streaming chat UI.
- **T0018.3:** topology confirmation, environment variables, and the first public deploy.

The first ticket is independent of the visible design work and is unit-testable.
The static serving ticket establishes route precedence before the UI is rendered.
The final deployment ticket verifies the same-origin production topology and its environment
variables without placing secrets in the image or repository.

## Rejected alternatives

- A separate SPA adds a second deploy and a live CORS surface without reviewer value.
- Native `EventSource` is GET-only and auto-reconnects, which could repeat an agent run.
- `fetch-event-source` adds a dependency and retry behavior the demo does not need.

The chosen product remains a single hand-written page with a restrained editorial visual system.
Its purpose is to make the streaming, honesty, memory, and tracing capabilities legible to a
reviewer without adding a client build toolchain.

The core visible features are token-by-token rendering, prompt chips, the data disclaimer, a
friendly busy/error state, a trace link, and multi-turn memory through the issued session id.
Fine visual details such as typography, spacing, color, and motion are build-time choices rather
than architecture decisions.

The final page is mounted after API routes so `/api/v1/*` and `/docs` retain their existing
route precedence.
The public deployment uses the same container image as local testing and configuration remains in
environment variables.

## Sources

- `docs/MVP_Technical_Design.md` section 11.
- `research/archive/streaming-implementation-plan.md` sections 4 through 6.
- `research/archive/deployment-research-plan.md`.

## Live-checked facts

- The stream endpoint accepts POST with a JSON body.
- Native `EventSource` is GET-only and reconnects automatically.
- The FastAPI static-file mount can serve the single-page demo at the same origin.

## Preserved implementation boundaries

- FastAPI routes translate HTTP and SSE wire format only.
- The application service owns session minting and stream adaptation.
- The runtime owns LangChain event extraction and the answer-only filter.
- The browser owns POST fetch, SSE parsing, rendering, and the stored session id.
- Tracing metadata is displayed only after it becomes available at stream completion.
