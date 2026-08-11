# InternHunterAgent — MVP Specification

> This document defines **what the MVP must be able to do and why** — the product expectation, not
> the implementation. Technical mechanism and ticket sequencing live elsewhere (see §7). If a line
> here starts describing *how* something is built, it belongs in another doc.

## 1. Purpose & Vision

InternHunterAgent helps a job seeker find and understand **AI/Data job opportunities — internships
and full roles alike** — by **talking to an agent** instead of scrolling listings. The user asks
about postings in plain language, refines the question naturally, and gets answers they can trust
because every answer is grounded in real posting data — not the model's imagination.

The MVP exists to prove one thing well: **a trustworthy, conversational front door to real AI/Data
job-posting data** (internships included). Everything richer — resumes, recommendations, charts,
live job feeds — builds on that foundation and comes later.

## 2. What the MVP Must Be Able to Do

These are the capabilities that define the MVP. They are written as things a user can observe,
independent of how they are built.

- **Answer real job questions.** The agent answers questions about AI/Data job postings (titles,
  companies, tech stacks, descriptions, counts, filters — including whether a posting is an
  internship) using actual stored data. It never fabricates a posting or a detail.
- **Hold a conversation.** A user can ask an initial question and then refine it naturally — "only
  the Python ones," "which of those are remote," "who posted the first one" — without restating
  earlier context. The agent follows the thread.
- **Remember within a session.** Each conversation is remembered while it is happening, and
  conversations persist across service restarts and continue working even when the service runs more
  than one instance. A user who returns to a session continues where they left off.
- **Stay safe and read-only.** The agent only reads data. It never modifies anything, and it clearly
  refuses requests it cannot or should not fulfil rather than guessing or doing something unsafe.
- **Be observable.** Every interaction is captured as a trace that can be followed end to end, so
  any answer can be inspected and explained after the fact.

## 3. Expectation / Quality Bar

This is what "good" should *feel* like when the MVP is used — the bar each capability is held to.

- **Trustworthy over impressive.** If the agent can ground an answer in the data, it answers; if it
  cannot, it says so plainly. A clear "I can't answer that from the available data" is a success,
  not a failure. Confident guessing is the worst outcome.
- **Coherent across turns.** Refinement genuinely works. The agent tracks the conversation so far,
  so follow-ups feel like a continuing dialogue, not a series of disconnected one-shot questions.
- **Resilient under imperfection.** A vague question, a brand-new conversation with no prior
  context, or a temporary backend problem produces a clean, understandable response — never a crash
  and never a leaked internal error.

## 4. Definition of Done

The MVP is done when all of the following are observably true:

- A user can ask a job-data question and receive an answer grounded in real posting data.
- A user can refine that question at least twice within one conversation and get consistent,
  context-aware answers.
- Two separate conversations stay independent — neither sees the other's history.
- A user who starts a conversation without providing a session identity is given one and can use it
  to continue the conversation.
- A conversation's memory survives a restart of the service.
- The agent refuses an unsafe or unanswerable request with a clear message instead of failing or
  guessing.
- Every interaction appears as a trace that maps cleanly back to the request.
- The application starts cleanly with a single, documented command.

## 5. Scope — What's In and What's Deliberately Not

**In scope (this MVP):** the five capabilities in §2, held to the bar in §3.

**Out of scope for now** — deferred on purpose, each mapped to a future phase so "not yet" never
reads as "forgotten":

- **Visual or structured output** (tables, charts) → answers are conversational text for this MVP;
  charting is a future phase.
- **Resume understanding and personalised matching** → future phase.
- **Similarity / semantic search over postings** → future phase.
- **Accounts, authentication, and multi-user management** → future phase.
- **Live or large-scale job data** → the MVP runs on a small, fixed sample dataset; larger and live
  data are future phases.

**Known limitations we accept for the MVP:**

- Answers are **text-only** — no tables, charts, or downloadable results yet.
- The dataset is a **small fixed sample**, sufficient to prove the experience, not to be
  comprehensive.

## 6. Future Direction

Intent, not commitment — the direction the product grows once the MVP is solid. Ordered roughly by
priority within each track.

- **Product experience:** resume upload → retrieval of similar postings via embeddings → charting
  and visual answers from the underlying data.
- **Data:** replace the sample dataset with a larger one → real-time ingestion of current AI/Data
  job postings.
- **Platform & operations:** evaluation harness for answer quality → a user-facing UI → managed
  deployment environments → ongoing prompt refinement.

## 7. Where the Details Live

This document stays at the level of *what* and *why*. The supporting detail lives elsewhere:

- **How it is built** (layers, runtime, memory mechanism, data flow) → `Full_Design_Document.md` and
  `MVP_Technical_Design.md`.
- **What gets built in what order** (tickets, sequencing, acceptance tests) → `Tickets.md`.
- **Current state of the repository** (branch, completed work, known issues) →
  `Repo_Current_State.md`.

For the full index of project docs and what each one owns, see the [documentation map](README.md).
