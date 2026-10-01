"""Turn a model-proposed request into a validated plan.

Validation and vocabulary resolution happen here, once, before any SQL exists.
The compiler downstream can trust a ``QueryPlan``: every value in it is a
canonical stored value or a whole technology token, and every filter is inside
its budget.

The rules that are not obvious from the contract text, and why they are here
rather than in the prompt:

- An unresolvable city is ``UNSUPPORTED`` with the canonical city list, never a
  silent empty result. A user who types a city the data does not hold has been
  answered correctly by "no" and answered wrongly by "I found nothing".
- A role with no canonical category becomes a disclosed fallback onto title and
  description. Dropping the request would be less honest than searching the
  posting text and saying so.
- A technology is always matched as a whole token, after alias expansion, so
  ``ML`` can never reach ``MLOps``.
- A salary threshold without a currency is allowed; a salary *disclosure* test
  is not expressible, because the field is not in the allowlist.
"""

from __future__ import annotations

from typing import Any

from src.services.query import vocabulary
from src.services.query.plan import (
    AmbiguousQueryError,
    Filter,
    FilterField,
    JobQueryRequest,
    MatchMode,
    Metric,
    NormalizedFilter,
    QueryPlan,
    QueryRequestError,
    QueryShape,
    ShareSpec,
    UnsupportedQueryError,
    query_limits,
)

# Fields whose values are canonical stored values compared with equality.
_EXACT_FIELDS = frozenset(
    {FilterField.ROLE, FilterField.LOCATION, FilterField.JOB_LEVEL, FilterField.SALARY_CURRENCY}
)
_NUMERIC_FIELDS = frozenset({FilterField.SALARY_MIN, FilterField.SALARY_MAX})
_BOOLEAN_FIELDS = frozenset({FilterField.IS_INTERNSHIP, FilterField.HAS_LINK})
_TEXT_FIELDS = frozenset({FilterField.COMPANY, FilterField.TITLE})
# A share is measured on a recorded value, so it needs a field that stores one.
# The two boolean properties count too: "what share of postings have a source
# link" and "what share are internships" are ordinary questions about this
# corpus, and refusing them was a gap the v0 gate found rather than a decision.
_SHAREABLE_FIELDS = frozenset(
    {
        FilterField.ROLE,
        FilterField.LOCATION,
        FilterField.JOB_LEVEL,
        FilterField.TECHNOLOGY,
        FilterField.COMPANY,
        FilterField.IS_INTERNSHIP,
        FilterField.HAS_LINK,
    }
)


def build_plan(request: JobQueryRequest) -> QueryPlan:
    """Validate the budget, resolve the vocabulary, and return the plan."""
    limits = query_limits()
    caveats: list[str] = []

    if request.shape is QueryShape.DETAIL:
        if len(request.ids) > limits["max_detail_rows"]:
            raise QueryRequestError(
                f"A detail request may name at most {limits['max_detail_rows']} ids, got {len(request.ids)}"
            )
        return QueryPlan(shape=request.shape, ids=tuple(request.ids))

    if request.shape is QueryShape.TOP_N and request.top is not None:
        if request.top.n > limits["max_top_n"]:
            raise QueryRequestError(
                f"top_n may request at most {limits['max_top_n']} rows, got {request.top.n}"
            )

    filters = _normalize_filters(request.filters, limits)
    # The role fallback caveat is added by the service from the criterion's basis,
    # so there is one owner and the answer cannot print it twice.

    if request.shape is QueryShape.COMPARE:
        sides = tuple(
            tuple(_normalize_filters(side.filters, limits, prefix=f"compare[{index}].filters"))
            for index, side in enumerate(request.compare)
        )
        return QueryPlan(shape=request.shape, metric=request.metric or Metric.COUNT, sides=sides, caveats=tuple(caveats))

    share = None
    if request.shape is QueryShape.AGGREGATE and request.metric is Metric.SHARE:
        assert request.share is not None  # guaranteed by the request model
        share = _normalize_share(request.share, filters, limits)

    return QueryPlan(
        shape=request.shape,
        filters=filters,
        group_by=request.group_by,
        metric=request.metric,
        share=share,
        top=request.top,
        caveats=tuple(caveats),
    )


# ---------------------------------------------------------------------------
# Filter normalization
# ---------------------------------------------------------------------------


def _normalize_filters(
    raw: list[Filter], limits: dict[str, int], *, prefix: str = "filters"
) -> tuple[NormalizedFilter, ...]:
    if len(raw) > limits["max_filters"]:
        raise QueryRequestError(
            f"{prefix} may hold at most {limits['max_filters']} filters, got {len(raw)}"
        )
    seen: set[FilterField] = set()
    normalized: list[NormalizedFilter] = []
    for index, item in enumerate(raw):
        label = f"{prefix}[{index}]"
        if item.field in seen:
            raise QueryRequestError(f"{label} repeats field '{item.field.value}'; combine its values instead")
        seen.add(item.field)
        if item.mode is MatchMode.ALL and item.field is not FilterField.TECHNOLOGY:
            raise QueryRequestError(
                f"{label} may only combine values with mode 'all' for a technology filter, not "
                f"'{item.field.value}'"
            )
        if len(item.values) > limits["max_values_per_filter"]:
            raise QueryRequestError(
                f"{label} may hold at most {limits['max_values_per_filter']} values, got {len(item.values)}"
            )
        normalized.append(_normalize_one(item, label))
    return tuple(normalized)


def _normalize_one(item: Filter, label: str) -> NormalizedFilter:
    field = item.field
    requested = tuple(item.values)

    if field is FilterField.FREE_TEXT:
        return _normalize_free_text(item, label)
    if field is FilterField.TECHNOLOGY:
        values = []
        for value in item.values:
            token = vocabulary.expand_technology(_as_text(value))
            if token is None:
                raise QueryRequestError(f"{label} has an empty technology value")
            values.append(token)
        return NormalizedFilter(
            field=field,
            values=tuple(dict.fromkeys(values)),
            mode=item.mode,
            basis="technology_token",
            requested=requested,
        )
    if field in _EXACT_FIELDS:
        return _normalize_exact(item, label)
    if field in _NUMERIC_FIELDS:
        return _normalize_numeric(item, label)
    if field in _BOOLEAN_FIELDS:
        return _normalize_boolean(item, label)
    if field in _TEXT_FIELDS:
        return _normalize_text(item, label)
    raise QueryRequestError(f"{label} uses unsupported field '{field.value}'")


def _normalize_exact(item: Filter, label: str) -> NormalizedFilter:
    field = item.field
    values: list[str] = []
    for value in item.values:
        text = _as_text(value)
        if field is FilterField.LOCATION:
            canonical = vocabulary.normalize_city(text)
            if canonical is None:
                raise UnsupportedQueryError(
                    f"'{text}' is not a city this data holds. The cities are: "
                    f"{', '.join(vocabulary.canonical_cities())}"
                )
            values.append(canonical)
        elif field is FilterField.ROLE:
            canonical = vocabulary.normalize_role(text)
            if canonical is None:
                # No canonical category: search the posting text and disclose it.
                return NormalizedFilter(
                    field=FilterField.FREE_TEXT,
                    values=(text,),
                    mode=MatchMode.ANY,
                    basis="fallback",
                    requested=tuple(item.values),
                )
            values.append(canonical)
        else:
            values.append(text)
    return NormalizedFilter(
        field=field,
        values=tuple(dict.fromkeys(values)),
        mode=MatchMode.ANY,
        basis="column",
        requested=tuple(item.values),
    )


def _normalize_numeric(item: Filter, label: str) -> NormalizedFilter:
    """A threshold carries one bound.

    A threshold is not a set membership test, so several values cannot be honoured:
    `>= 1000 OR >= 2000` collapses to the weaker `>= 1000`, which is almost never
    what was meant. Compiling the first value and reporting the rest as applied
    criteria would tell the model about a filter that never ran, so a second
    *distinct* value is a question instead, exactly as a boolean filter carrying both
    values is.

    Repeating the same bound is not a second bound. A query that says `>= 1000` twice
    names one threshold, so it is normalised rather than questioned - and the
    question would be unanswerable, because there is nothing to choose between.
    """
    distinct = tuple(dict.fromkeys(item.values))
    if len(distinct) > 1:
        raise AmbiguousQueryError(
            f"Bạn muốn lọc theo ngưỡng nào cho '{item.field.value}'? Hãy nêu một con số."
        )
    values: list[float] = []
    for value in item.values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise QueryRequestError(f"{label} takes a number for '{item.field.value}', got {value!r}")
        values.append(float(value))
    if len(set(values)) > 1:
        # A threshold is not a set membership test. Two bounds cannot both be the
        # minimum, and the compiler binds one, so keeping both here would report
        # criteria that never ran. Ask which one is meant.
        raise AmbiguousQueryError(
            f"Bạn muốn lọc '{item.field.value}' từ mức nào? Hãy nói rõ một mức."
        )
    return NormalizedFilter(
        field=item.field,
        values=(values[0],),
        mode=MatchMode.ANY,
        basis="column",
        requested=tuple(item.values),
    )


def _normalize_boolean(item: Filter, label: str) -> NormalizedFilter:
    values: list[bool] = []
    for value in item.values:
        if not isinstance(value, bool):
            raise QueryRequestError(f"{label} takes true or false for '{item.field.value}', got {value!r}")
        values.append(value)
    if len(set(values)) > 1:
        raise AmbiguousQueryError(
            f"Bạn muốn lọc '{item.field.value}' có hay không? Hãy nói rõ giá trị."
        )
    return NormalizedFilter(
        field=item.field,
        values=(values[0],),
        mode=MatchMode.ANY,
        basis="column",
        requested=tuple(item.values),
    )


def _normalize_text(item: Filter, label: str) -> NormalizedFilter:
    values = []
    for value in item.values:
        text = _as_text(value)
        if not text:
            raise QueryRequestError(f"{label} has an empty '{item.field.value}' value")
        values.append(text)
    return NormalizedFilter(
        field=item.field,
        values=tuple(dict.fromkeys(values)),
        mode=MatchMode.ANY,
        basis="column",
        requested=tuple(item.values),
    )


def _normalize_free_text(item: Filter, label: str) -> NormalizedFilter:
    limit = vocabulary.max_free_text_terms()
    if len(item.values) > limit:
        raise QueryRequestError(f"{label} may hold at most {limit} free-text terms, got {len(item.values)}")
    values = []
    for value in item.values:
        text = _as_text(value)
        if not text:
            raise QueryRequestError(f"{label} has an empty free-text term")
        values.append(text)
    return NormalizedFilter(
        field=FilterField.FREE_TEXT,
        values=tuple(dict.fromkeys(values)),
        mode=MatchMode.ANY,
        basis="free_text",
        requested=tuple(item.values),
    )


def _normalize_share(
    share: ShareSpec, filters: tuple[NormalizedFilter, ...], limits: dict[str, int]
) -> NormalizedFilter:
    """Resolve the tested value of a share, outside the base filters.

    A share on a field the base already restricts would always be 100 percent,
    so the request is refused rather than answered with a meaningless number.
    """
    if share.field not in _SHAREABLE_FIELDS:
        raise QueryRequestError(
            f"share.field '{share.field.value}' cannot carry a share; a share is measured on a recorded "
            f"value, one of: {', '.join(sorted(field.value for field in _SHAREABLE_FIELDS))}"
        )
    if any(existing.field is share.field for existing in filters):
        raise QueryRequestError(
            f"the base filters already restrict '{share.field.value}', so a share on it would always be "
            "100 percent; move that filter out of the base"
        )
    if len(share.values) > limits["max_values_per_filter"]:
        raise QueryRequestError(
            f"share may hold at most {limits['max_values_per_filter']} values, got {len(share.values)}"
        )
    return _normalize_one(Filter(field=share.field, values=share.values), "share")


def _as_text(value: Any) -> str:
    if isinstance(value, bool):
        raise QueryRequestError(f"Expected text, got the boolean {value!r}")
    return " ".join(str(value).split()).strip()
