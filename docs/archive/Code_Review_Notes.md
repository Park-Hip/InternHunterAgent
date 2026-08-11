# Code Review Notes

Per-module logic review of every `src/` module, 2026-07-02 (post-T0009.11, on
`feature/t0009.11-job-detail-tool`).

## Bugs found (one-line index)

`Known_Issues.md` is the living source of truth for bug status.
These are pointers only; do not maintain fix-history here.

### Bug 1

~~[HIGH] SQL validator did not enforce a single table.~~ **Fixed by T0010.3**.

### Bug 2

~~[MED-HIGH] Blocking LLM call on the async event loop.~~ **Fixed by T0010.4**.

### Bug 3

~~[MED] Ingestion aborts inconsistently on one bad payload.~~ **Fixed**.

### Bug 4

~~[MED] Denylist matched keywords inside string literals.~~ **Fixed**.

### Bug 5

~~[MED] "Showing N of M" can understate the true match count.~~ **Fixed by T0010.5**.

### Bug 6

~~[MED] `normalize_location` only matches on an exact full-string lookup.~~ **Fixed by
T0010.6**.

### Bug 7

~~[LOW] Per-request `client.flush()` on the event loop.~~ **Fixed**.

### Bug 8

~~[LOW/latent] `replace_clean_jobs` would crash on intra-batch duplicate keys.~~ **Fixed**.

## Doc insights

### Doc insight 3

**T0010.1 is closed, with one residual gap.** `query.py` returns 400 for empty input
and re-raises `HTTPException`; `core/errors.py::InvalidQueryError` exists and is wired;
`service.py` coerces a `None`/empty runtime answer into `FALLBACK_ANSWER`.
However the coercion is currently unreachable in practice: `react_agent._extract_answer` *raises*
`ValueError` on empty/unreadable final content rather than returning it, so `runtime.ainvoke`
raises before the coercion runs and the exception falls through to the generic 500 in `query.py`.
Tracked as its own open item in `Known_Issues.md` (API layer) rather than reopening T0010.1.
