# Temporary AI-agent learning roadmap

> Working note. Local to this repository; do not move to Obsidian without explicit permission.

## Learning order

1. **System map** — Trace one request from user to response once, without trying to understand every detail.
2. **Agent contract** — Define what InternHunter may answer, must refuse, and returns publicly.
3. **Data and infrastructure** — Learn what makes a job-data answer authoritative and what data is missing or unreliable.
4. **Tools** — Inspect the agent's actual powers: query interfaces, validation, permissions, output bounds, and failures.
5. **Model and prompt** — Learn model selection, system-prompt ownership, and how behavior is specified.
6. **Context engineering** — Identify which messages and tool results reach each model call, and the limits that bound them.
7. **Runtime and orchestration** — Trace agent construction, middleware, tool calls, retry/deadline rules, and termination.
8. **Short-term memory** — Understand session/thread identity, checkpointing, recovery, and isolation.
9. **Prompt injection and safety** — Treat user text, job data, and tool output as untrusted; find each trust boundary.
10. **Streaming UX** — Learn SSE event shapes, token filtering, timeouts, cancellation, disconnects, and safe errors.
11. **Tracing and prompt lineage** — Diagnose a response from its trace/log evidence without exposing sensitive data.
12. **Evaluation** — Follow a behavior from scenario through deterministic checks, semantic judgment, and replay evidence.
13. **Long-term memory** — Only consider it after a real cross-thread use case, ownership, authorization, and retention policy exist.
14. **Delivery governance** — Learn how to propose, test, review, release, and roll back changes to these surfaces.

## InternHunterAgent starting route

The project’s core claim is grounded, honest answers about job postings. Begin here:

1. **Agent contract**
2. **Data and infrastructure**
3. **Tools**

Only then move to prompts, LangChain runtime details, tracing, and the evaluation system.

## First question

For the question, **“Which job was posted most recently?”**, trace where the system prevents a fabricated answer. Record the files, data fields, prompt/tool constraints, and tests involved. Mark anything not understood with `?`; that becomes the next study question.
