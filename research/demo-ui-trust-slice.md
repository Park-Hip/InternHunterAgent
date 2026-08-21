# Demo UI trust slice: what to adopt from the external UI report

> **Status:** Research record. Reviews the external report in `demo_UI/` and fixes the adoption
> boundary for the next demo UI pass. No milestone is assigned and nothing below is implemented.

> **Eviction:** This record leaves when its adoption decisions are harvested into the decision log
> or the demo UI pass ships.

> **Last verified:** 2026-08-21

## 1. Summary

An external report, `demo_UI/Designing a Professional UI for InternHunter and Similar AI Agents.md`,
proposes rebuilding the demo as a three-pane "Agent Research Desk" with a workspace rail, saved
searches, an evidence drawer, and a twelve-event frontend contract.
It ships a React prototype at `demo_UI/internhunter-research-desk/`.

The report's interaction principles are sound and its diagnosis of the current demo is correct: the
UI hides the product's differentiator behind a single opaque prose block.
Its product model is not, because it assumes a multi-source retrieval agent.
This repository runs a text-to-SQL agent over one nightly snapshot of one source, so the report's
evidence model would require the UI to display provenance the data cannot support.

The adopted scope is a **trust slice**: make the run observable, make the retrieved rows visible,
make the run stoppable, and make freshness a header fact rather than a footnote.
Everything that presumes multiple sources, persistence, or authentication is out.

| # | Item | Verdict | Backing that already exists |
|---|---|---|---|
| A1 | Render the result table the tool already returns | Adopt | `QueryToolResult.table` |
| A2 | Observable run steps instead of one frozen spinner | Adopt | agent tool boundaries |
| A3 | Stop and retry controls | Adopt | none; this is a real gap |
| A4 | Freshness and coverage promoted to a header strip | Adopt | `GET /api/v1/ready` |
| A5 | Serif brand with a sans-serif face for data and controls | Adopt | current stylesheet |
| A6 | WCAG 2.2 as acceptance criteria, plus a designed state matrix | Adopt | partial |
| A7 | Obligations rendered as a visible partial-coverage marker | Adopt | `QueryToolResult.obligations` |
| R1 | AG-UI protocol adoption and a twelve-event contract | Reject | - |
| R2 | Per-listing source URL, excerpt, and retrieval timestamp evidence | Reject | not in the data |
| R3 | Clarification turns and approval checkpoints | Reject | no consequential actions |
| R4 | Source-health page and per-source retry | Reject | one source |
| D1 | Workspace rail, history, saved searches, alerts | Defer | needs persistence |
| D2 | Filters, sorting, comparison view over results | Defer | no backend contract |
| D3 | Structured feedback taxonomy UI | Defer | after the trust slice |

## 2. Where the report's model diverges from the built system

The report repeatedly designs for source plurality.
It specifies a `source.found` event per source, progress copy such as "Searching 4 public sources",
an evidence drawer holding "source name, canonical URL, publication date, retrieval timestamp, the
excerpt used", and a Sources/Data health rail entry.
Its prototype hardcodes listings attributed to TopDev, LinkedIn, and VietnamWorks, each stamped
with a per-listing retrieval time such as `Today, 09:42 ICT`.

The built system does none of this.

| Report assumption | Built reality | Evidence |
|---|---|---|
| Several live sources searched per run | One source, decided and gated | D-034, D-038 |
| Per-listing retrieval timestamp | One snapshot date for the whole corpus | `GET /api/v1/ready` |
| Retrieval over documents, excerpt-citable | Generated SQL over a cleaned table | `src/agents/tools/query_clean_jobs.py` |
| Evidence is a quoted passage | Evidence is the SQL and the rows it returned | `src/services/query/models.py` |
| English workspace with saved roles | Vietnamese-only surface, no accounts | M33, `src/api/static/index.html` |

Adopting R2 literally would mean inventing a per-listing provenance field, which is precisely the
failure mode the obligation seam exists to prevent.
The correct translation is not to drop the evidence idea but to bind it to the artifact this
architecture actually produces: the query and the rows it returned.

## 3. Adopted items

### A1. Render the result table

The strongest and cheapest item.
`QueryToolResult` already carries a typed `TableArtifact` of `columns`, `rows`, `row_count`, and
`truncated`, and the executor already bounds it.
Today that structure is flattened into prose by the model and only the prose reaches the browser,
so the UI shows a claim where it could show the rows behind the claim.

The change is one new stream event carrying the artifact and one table component that renders it,
including the `truncated` state so a bounded result never reads as a complete one.

**Decision taken:** the SQL is shown behind a collapsed disclosure beneath the table rather than
inline or hidden entirely.
For a portfolio demo the generated query is the most convincing proof that the answer came from the
data, and a disclosure keeps it out of the way of an ordinary reader.

### A2. Observable run steps

`src/api/static/app.js` sets one placeholder and leaves it frozen for the whole run regardless of
what the agent is doing.

The report's distinction between observable work and reasoning theater is right and transfers
cleanly.
The honest steps here are few and all correspond to real boundaries: generating the query, running
it, the row count that came back, and drafting the answer.
No internal reasoning is exposed, which also keeps the two-gate token filter of D-008 intact.

### A3. Stop and retry

There is currently no cancel path.
`setBusy(true)` disables the input, the send button, and every chip until a terminal event arrives,
so a slow or stuck run leaves the reader with no control at all.
This is a defect rather than a polish item, and it is listed here because the report surfaced it.

Retry belongs with it: an error bubble today is terminal and the reader must retype the question.

### A4. Freshness and coverage in the header

`loadDateline()` already reads `data_snapshot_date` and only trusts it when
`data_snapshot_date_provenance` is `measured`, falling back to a dateless sentence otherwise.
That discipline is correct and stays.
The change is placement and content: promote it from a footnote-weight dateline to a trust strip
carrying the snapshot date, the source, and the corpus size, with the unmeasured state still
explicit rather than blank.

### A5. Typography split

The report recommends keeping the serif for the brand and large headings while moving controls,
metadata, and dense data to a legible sans-serif.
This is correct on its own terms and becomes necessary once A1 lands, because editorial serif at
table density reads poorly.

### A6. Accessibility and the state matrix

Two process items worth keeping.

WCAG 2.2 keyboard operation, visible focus, accessible names, status messages, contrast, zoom, and
reflow are treated as acceptance criteria for the pass rather than a later cleanup.
The demo already has a skip link and `role="status"` regions, so this is a completion pass and not
a rebuild.

Separately, every state gets a designed outcome before implementation: idle, streaming, complete,
empty result, truncated result, obligation-bearing result, error, and cancelled.
The current UI has designed treatments for three of these.

### A7. Obligations as a visible marker

An unexpected fit.
The report asks for a partial-coverage treatment and assumes it must be inferred from source
failures; this repository already computes one deterministically as
`QueryToolResult.obligations`, produced by `detect_obligations`.
Rendering an obligation as a visible marker on the answer gives the report's partial-coverage state
a truthful backing field instead of a guessed one.

## 4. Rejected

- **R1, AG-UI and the twelve-event contract.** The stream already has typed terminal events under
  D-006 and a documented five-event vocabulary. The trust slice needs at most two additions. Taking
  a protocol to get them is unnecessary dependency weight against an MVP.
- **R2, excerpt-level evidence.** Not backed by the data, as established in section 2.
- **R3, clarification turns and approval checkpoints.** The agent takes no consequential action, so
  there is nothing to approve. The report itself concedes this and argues for building the state
  model early anyway; that is speculative work the operational rules exclude.
- **R4, source health.** One source. A health page over a single nightly job is a dashboard for a
  boolean.

The report also recommends moving the prompt-injection chip out of the user-facing surface and into
a developer mode.
Not adopted.
This is a portfolio demo whose thesis is the honesty boundary, and the chip that demonstrates that
boundary is the one worth keeping visible.
Relabelling it is in scope; hiding it is not.

## 5. Deferred

D1, D2, and D3 are coherent product ideas that fail the same test: they need state that does not
exist yet.
History, saved searches, and alerts need persistence and identity.
Filters and sorting need a query contract the agent surface does not expose.
The feedback taxonomy needs a place to send feedback and a review loop to consume it.

The report's own build order agrees, and its closing recommendation is the one to follow: the
highest-value release is a small trustworthy workspace, not a larger dashboard.

## 6. Open questions

| # | Question | Blocks |
|---|---|---|
| Q1 | Does the table event carry the artifact once at completion or stream per row? | A1 |
| Q2 | Are run steps derived in the service layer or inferred from existing tool spans? | A2 |
| Q3 | Does cancel abort the agent run server-side or only close the reader? | A3 |
| Q4 | What Vietnamese wording carries the truncated and obligation states? | A1, A7 |

Q3 matters most.
Closing the reader alone leaves the model generating and billing against a run nobody reads, which
interacts with the demo cost ceiling under D-025.

## 7. Source materials

- `demo_UI/Designing a Professional UI for InternHunter and Similar AI Agents.md`, the external
  report, dated 2026-08-21.
- `demo_UI/internhunter-research-desk/`, its React prototype. Static English mockup with fabricated
  multi-source data. Useful as a visual reference only; its data model is not ours.
