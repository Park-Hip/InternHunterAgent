# Documentation Hygiene Review - T0016 Security Posture

> Status: review notes. Cleanup pass applied 2026-07-13; kept as audit trail.
>
> Reviewed branch: `feature/t0016.4-docs-headers`
>
> Review base: `feature/t0016.1-cors-middleware` / `8ffd8980fd48c4c785a54f0f23a3bc62ea091ef0`
>
> Review priority: documentation/code drift, stale decisions, unclear headers, and doc hygiene.

## Summary

The T0016.2-T0016.4 implementation is documented in the new completion entries, manual verification guide, and bottom-of-file branch updates, but several older docs still describe the pre-T0016 world. The highest-priority cleanup is to make each document's ownership clear:

- `Repo_Current_State.md` should describe the current branch at the top, not only in appended historical blockquotes.
- `Tickets.md` should name the actual config-driven switches now implemented.
- Research docs should either be updated with dated "superseded by T0016" notes or explicitly labelled as historical pre-design evidence.
- Old review/backlog notes should be marked resolved or carried forward intentionally so they do not look like current findings.

## Cleanup Status

Applied on 2026-07-13:

- Updated `Repo_Current_State.md` with a current T0016.4 branch snapshot and labelled older roadmap content as historical.
- Updated `Tickets.md` T0016.4 to name `api.docs_enabled: false` as the locked-down switch.
- Added supersession notes to `research/pre-deploy-refinement-plan.md` and `research/deployment-research-plan.md`.
- Updated stale deployment examples for `src.api.app:app`, `POST /api/v1/agent/chat`, and `/api/v1/health`.
- Marked the old CORS and max-length review bullets in `Code_Review_Notes.md` as resolved by T0016.
- Added a T0016.1 correction note in `Completion_Reports.md` for the superseded T0016.5 reference.
- Promoted T0016 manual checklist labels to headings and clarified the static input-cap mirror.

Deliberate non-code choice: this cleanup pass did not change `src/api/schemas.py`; the request length cap remains a static schema constant mirrored by `api.max_query_chars`.

## Findings

### [P1] `Repo_Current_State.md` top snapshot contradicts the active branch

Evidence:
- `docs/Repo_Current_State.md:1-7` still says the current branch is `fix/known-issues-hardening`, the active work is T0014, and the branch's work is only in T0014.
- `docs/Repo_Current_State.md:346-349` later appends T0016.2, T0016.3, and T0016.4 updates, including `feature/t0016.4-docs-headers`.
- Actual git status reports `feature/t0016.4-docs-headers`.

Why it matters:
- `Repo_Current_State.md` is the doc meant to tell the next developer where the repo stands now. A reader who starts at the top will follow the wrong branch/ticket context.

Suggested fix:
- Rewrite the top `Current branch` and `In progress / next` sections for `feature/t0016.4-docs-headers`.
- Move the older T0014 branch-topology text into a clearly labelled historical note if it is still useful.
- Keep the T0016.1-T0016.4 blockquotes only as ticket history, not as the primary current-state record.

### [P2] `api.max_query_chars` is documented as config, but the code enforces a separate constant

Evidence:
- `config/settings.yaml:4` sets `api.max_query_chars: 2000`.
- `src/api/schemas.py:3-6` enforces `DEFAULT_MAX_QUERY_CHARS = 2000` directly in `Field(..., max_length=...)`.
- `docs/Tickets.md:917` says to surface the cap value from `config/settings.yaml` where practical, otherwise use a documented module constant.
- `docs/Repo_Current_State.md:348` says config sets `api.max_query_chars: 2000` and the schema constrains with a matching constant.
- `docs/Completion_Reports.md:81` does disclose the risk, but the main state docs still make the YAML value look like the effective knob.

Why it matters:
- If a maintainer changes `api.max_query_chars`, the API behavior will not change. That is a config/code drift trap.

Suggested fix:
- Pick one ownership model:
  - make the schema validation load from a typed config path, or
  - remove/rename the YAML value and document `DEFAULT_MAX_QUERY_CHARS` as intentionally static.
- If keeping the static constant, make `Repo_Current_State.md` and the manual checklist say "operator-visible mirror" rather than implying runtime configurability.

### [P2] Research still says T0016 security posture is unimplemented

Evidence:
- `research/pre-deploy-refinement-plan.md:388-395` says security posture is unimplemented and lists no rate limiting, no CORS, undecided `/docs`, and no security headers.
- Current branch implements CORS from T0016.1, rate limiting from T0016.2, input cap from T0016.3, and the `/docs` exposure decision from T0016.4.

Why it matters:
- `docs/Tickets.md` cross-references this research as the grounding for T0016, so the source research now reads like the branch did not close the very items it claims to close.

Suggested fix:
- Add a dated note under `research/pre-deploy-refinement-plan.md` section 6b saying the original gap list was superseded by T0016.1-T0016.4.
- Split the remaining open items from closed items:
  - closed: CORS, rate limit, friendly 429, input cap, `/docs` decision.
  - still open/deferred: DB readiness probe, deploy topology, data-shipping decision, CI gate, any UI-specific headers.

### [P2] `deployment-research-plan.md` section 11 still carries stale deploy examples and old recommendations

Evidence:
- `research/deployment-research-plan.md:114` shows `CMD ["uvicorn", "src.main:app", ...]`, but the app entrypoint is `src.api.app:app` and `main.py` was deleted earlier.
- `research/deployment-research-plan.md:735` recommends "No exposed `/docs` in prod" via `FastAPI(docs_url=None, redoc_url=None)`, while T0016.4 chooses `api.docs_enabled: true` by default with `api.docs_enabled: false` as the locked-down switch.
- `research/deployment-research-plan.md:747-749` uses an example `@app.get("/query")`, while the real public route is `POST /api/v1/agent/chat`.
- `research/deployment-research-plan.md:737` says health endpoints should not be rate-limited as `/health`, while the implemented route is `/api/v1/health`.

Why it matters:
- This file is still cross-referenced as deploy research. If it remains stale, the future deploy pass may re-open already-decided items or copy broken commands.

Suggested fix:
- Add a dated T0016 decision note to section 11.
- Update code snippets to `src.api.app:app`, `POST /api/v1/agent/chat`, and `/api/v1/health`.
- Replace the old `/docs` recommendation with the actual decision: keep docs enabled for the portfolio demo by default, and disable all three docs endpoints with `api.docs_enabled: false` if the deploy is locked down.

### [P2] Old code-review notes still list fixed T0016 issues as current improvement backlog

Evidence:
- `docs/Code_Review_Notes.md:91-93` still says there is no CORS middleware.
- `docs/Code_Review_Notes.md:98-100` still says `QueryRequest.query` has no `max_length`.
- T0016.1 adds CORS; T0016.3 adds the Pydantic max length.

Why it matters:
- This document is a review backlog. Leaving fixed items unmarked makes later reviewers chase already-closed work.

Suggested fix:
- Strike or annotate the CORS and max-length bullets as resolved by T0016.1 and T0016.3.
- If the static-config caveat from the max-length implementation remains, replace the old "no max_length" note with the more precise config/constant drift risk.

### [P3] `Tickets.md` describes the locked-down docs alternative with the old implementation mechanism

Evidence:
- `docs/Tickets.md:928` says the locked-down alternative is `FastAPI(..., docs_url=None, redoc_url=None)`.
- `src/api/app.py:89-91` now controls `docs_url`, `redoc_url`, and `openapi_url` through `docs_enabled`.
- `docs/Manual_Verification_Guide.md:871-876` correctly tells the reader to set `api.docs_enabled: false` and verify `/docs`, `/redoc`, and `/openapi.json`.

Why it matters:
- The ticket text is now the outlier. It tells future implementers to edit code instead of flipping the config switch this branch added.

Suggested fix:
- Change the locked-down alternative in `docs/Tickets.md` to `api.docs_enabled: false`.
- Mention that this disables `/docs`, `/redoc`, and `/openapi.json` together.

### [P3] `Completion_Reports.md` T0016.1 follow-ups mention a nonexistent or superseded T0016.5

Evidence:
- `docs/Completion_Reports.md:79` lists `T0016.5 Langfuse secrets hygiene` as a follow-up and says T0016.5 was not implemented.
- `docs/Tickets.md:879-954` now defines T0016 as security posture, says Langfuse secrets are moot because deploy uses Langfuse Cloud Hobby, and has no T0016.5.

Why it matters:
- Completion reports are append-only, but unresolved follow-up labels should not point readers to a ticket that no longer exists.

Suggested fix:
- Add a short corrective note after the T0016.1 entry: "The earlier T0016.5 follow-up was superseded when Langfuse secrets became moot under the Langfuse Cloud Hobby decision; no T0016.5 exists in the current T0016 scope."
- Avoid editing historical wording unless the repo policy allows it; an appended correction is enough.

### [P3] Manual verification T0016 entries are not Markdown headings

Evidence:
- `docs/archive/Manual_Verification_Archive.md:826`, `841`, and `858` introduce T0016.2-T0016.4 as plain text labels, not headings.

Why it matters:
- The manual guide is long. Plain labels are harder to navigate, link, and scan, especially when future tickets refer to "Manual_Verification_Guide -> T0016.4".

Suggested fix:
- Convert T0016 labels to consistent headings such as `## T0016.4: /docs exposure decision + minimal security headers` or the local heading level used by nearby entries.
- Apply the same pattern to T0016.1 if it is also a plain label.

### [P3] Research and ticket docs use different `/docs` security framing

Evidence:
- `research/deployment-research-plan.md:735-736` frames hidden docs and security headers as minimum production checklist items.
- `docs/Tickets.md:925-932` frames public docs as the chosen portfolio-demo default and skips headers until a same-origin HTML UI exists.
- `docs/Repo_Current_State.md:349` follows the ticket framing.

Why it matters:
- The decision may be correct, but the docs currently present two different security policies.

Suggested fix:
- Add a dated "decision delta" in the research plan: the original generic production checklist was narrowed for this API-only portfolio demo, so public docs are intentionally kept and frame-protection headers are deferred until FastAPI serves HTML.

## Non-Issues / Acceptable Notes

- `docs/Completion_Reports.md:81` explicitly records the static input-cap risk. That is good hygiene; the problem is that other docs do not carry the same caveat.
- `docs/archive/Manual_Verification_Archive.md:858-878` gives a clear T0016.4 manual checklist and correctly covers `/openapi.json`.
- `tests/api/test_docs_exposure.py` covers both docs-on and docs-off behavior; no doc finding is needed there.

## Verification Performed During Review

- Ran `git diff --stat 8ffd8980fd48c4c785a54f0f23a3bc62ea091ef0`.
- Ran drift searches across `docs/`, `research/`, `config/`, `src/`, and `tests/`.
- Ran `uv run pytest -q tests/api/test_docs_exposure.py tests/api/test_query.py tests/api/test_rate_limit.py`.
- Result: `17 passed`.

## Suggested Cleanup Order

1. Fix `Repo_Current_State.md` top-level current branch/in-progress snapshot.
2. Resolve or clarify the `api.max_query_chars` config-vs-constant contract.
3. Add dated superseded-by-T0016 notes to `research/pre-deploy-refinement-plan.md` and `research/deployment-research-plan.md`.
4. Update `Tickets.md` T0016.4 to name `api.docs_enabled: false`.
5. Mark fixed T0016 items in `Code_Review_Notes.md`.
6. Add a corrective note for the old T0016.5 completion-report follow-up.
7. Normalize T0016 headings in `Manual_Verification_Archive.md`.
