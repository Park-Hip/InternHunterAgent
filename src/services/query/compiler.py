"""Compile a validated plan into parameterized PostgreSQL.

Every SQL fragment in this module is written here, from an allowlisted template,
with the user's value in a bound parameter. Nothing that reaches this module
from the model can change a column name, a function name, an operator, or a
clause boundary, because none of those are ever taken from input.

The three properties the execution tests hold this to:

- **Parameterised values.** Every value is bound. The only user-derived text in
  a statement is inside a parameter, including free text with its ``%`` and
  ``_`` escaped.
- **Allowlisted identifiers and functions.** The visible columns below are the
  16 the agent may reach. The six hidden columns are not in the map, so no
  statement can name them. The functions below are the only ones emitted.
- **The display cap is never an aggregate input.** A list carries the full
  matching total in a window function computed before the limit, and every
  aggregate counts the full eligible set.
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from src.services.query.plan import (
    FilterField,
    GroupField,
    MatchMode,
    Metric,
    NormalizedFilter,
    QueryPlan,
    QueryRequestError,
    QueryShape,
    SortField,
)

TABLE: Final = "clean_jobs"

# The 16 agent-visible columns, and nothing else. A field outside this map is a
# column the agent may not reach; the map is the enforcement, not a filter.
VISIBLE_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "title",
        "company",
        "role",
        "description",
        "tech_stack",
        "job_level",
        "location",
        "source_url",
        "listing_expires_on",
        "created_on",
        "is_internship",
        "salary_min",
        "salary_max",
        "salary_currency",
        "is_salary_negotiable",
    }
)

# The only functions this module emits. Checked by the compiler tests against
# the statements it produced, so a new function cannot be added unnoticed.
ALLOWED_FUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        "avg",
        "btrim",
        "coalesce",
        "count",
        "percentile_cont",
        "regexp_split_to_table",
    }
)

LIST_PROJECTION: Final = ("id", "title", "company", "location", "source_url")
DETAIL_PROJECTION: Final = (
    "id",
    "title",
    "company",
    "role",
    "description",
    "location",
    "job_level",
    "tech_stack",
    "salary_min",
    "salary_max",
    "salary_currency",
    "is_salary_negotiable",
    "is_internship",
    "source_url",
    "listing_expires_on",
    "created_on",
)

_GROUP_COLUMNS: Final[dict[GroupField, str]] = {
    GroupField.ROLE: "role",
    GroupField.LOCATION: "location",
    GroupField.JOB_LEVEL: "job_level",
    GroupField.COMPANY: "company",
    GroupField.SALARY_CURRENCY: "salary_currency",
    GroupField.IS_INTERNSHIP: "is_internship",
}

# The split pattern for the technology list. POSIX classes, never a backslash
# escape, so the pattern cannot change meaning between a Python string and a
# PostgreSQL regular expression.
_TECH_SPLIT: Final = "[[:space:]]*,[[:space:]]*"

_SORT_COLUMNS: Final[dict[SortField, str]] = {
    SortField.SALARY_MIN: "salary_min",
    SortField.SALARY_MAX: "salary_max",
    SortField.CREATED_ON: "created_on",
    SortField.LISTING_EXPIRES_ON: "listing_expires_on",
    SortField.POSTING_ID: "id",
}


class Statement(BaseModel):
    """One read-only statement and its bound parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sql: str
    params: dict[str, Any] = Field(default_factory=dict)
    # A stable name so the service knows which result slot this fills.
    role: str = "main"


class CompiledQuery(BaseModel):
    """Every statement one plan needs, in order, plus what it is about."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shape: QueryShape
    statements: tuple[Statement, ...]
    display_cap: int
    # The currency scope of a salary aggregate, when the request pinned one.
    salary_currency: str | None = None


class CompiledPredicate(BaseModel):
    """A SQL fragment and its bound values, built from a template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sql: str
    params: dict[str, Any]


def _bind(name: str, value: Any) -> CompiledPredicate:
    return CompiledPredicate(sql=f":{name}", params={name: value})


def _like_value(text: str) -> str:
    """Escape the wildcards a user typed so a search is literal apart from ours."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def compile_predicate(predicate: NormalizedFilter, index: int) -> CompiledPredicate:
    """Build one allowlisted predicate fragment for a normalized filter."""
    field = predicate.field
    values = predicate.values

    if field is FilterField.FREE_TEXT:
        # The role fallback promises the title as well as the description.
        return _free_text_predicate(
            values, index, include_title=predicate.basis == "fallback"
        )
    if field is FilterField.TECHNOLOGY:
        return _technology_predicate(values, predicate.mode, index)
    if field is FilterField.HAS_LINK:
        return _presence_predicate("source_url", bool(values[0]), index)
    if field in (FilterField.SALARY_MIN, FilterField.SALARY_MAX):
        return _threshold_predicate(field, float(values[0]), index)
    if field is FilterField.IS_INTERNSHIP:
        return CompiledPredicate(
            sql="is_internship = :p{0}".format(index), params={f"p{index}": bool(values[0])}
        )
    if field in (FilterField.COMPANY, FilterField.TITLE):
        return _substring_predicate(field.value, [str(v) for v in values], index)
    return _equality_predicate(field, [str(v) for v in values], index)


def _equality_predicate(field: FilterField, values: list[str], index: int) -> CompiledPredicate:
    column = field.value
    if column not in VISIBLE_COLUMNS:
        raise QueryRequestError(f"'{column}' is not an agent-visible column")
    names = [f"e{index}_{position}" for position in range(len(values))]
    clause = " OR ".join(f"{column} = :{name}" for name in names)
    return CompiledPredicate(
        sql=f"({clause})",
        params={name: value for name, value in zip(names, values, strict=True)},
    )


def _substring_predicate(column: str, values: list[str], index: int) -> CompiledPredicate:
    if column not in VISIBLE_COLUMNS:
        raise QueryRequestError(f"'{column}' is not an agent-visible column")
    names = [f"s{index}_{position}" for position in range(len(values))]
    clause = " OR ".join(f"{column} ILIKE :{name}" for name in names)
    return CompiledPredicate(
        sql=f"({clause})",
        params={name: _like_value(value) for name, value in zip(names, values, strict=True)},
    )


def _threshold_predicate(field: FilterField, value: float, index: int) -> CompiledPredicate:
    column = field.value
    if column not in VISIBLE_COLUMNS:
        raise QueryRequestError(f"'{column}' is not an agent-visible column")
    return CompiledPredicate(sql=f"{column} >= :n{index}", params={f"n{index}": value})


def _presence_predicate(column: str, present: bool, index: int) -> CompiledPredicate:
    """Match whether a nullable column records a value.

    ``present=True`` means "has a value", which is `IS NOT NULL`. The two are not
    interchangeable, and a filter that asked the opposite question would look
    like it worked: it would return the rows the user did not ask about.
    """
    if column not in VISIBLE_COLUMNS:
        raise QueryRequestError(f"'{column}' is not an agent-visible column")
    return CompiledPredicate(
        sql=f"{column} IS {'NOT ' if present else ''}NULL",
        params={},
    )


def _technology_predicate(values: tuple[Any, ...], mode: MatchMode, index: int) -> CompiledPredicate:
    """Match a whole token of the recorded technology list, never a substring.

    A token match is the only thing standing between a request for
    ``Machine Learning`` and the two postings whose only similar token is
    ``MLOps`` or ``MLflow``.
    """
    fragments: list[str] = []
    params: dict[str, Any] = {}
    for position, value in enumerate(values):
        name = f"t{index}_{position}"
        params[name] = value
        fragments.append(
            "EXISTS (SELECT 1 FROM regexp_split_to_table(COALESCE(tech_stack, ''), "
            f"'{_TECH_SPLIT}') AS tech WHERE btrim(tech) = :{name})"
        )
    joiner = " AND " if mode is MatchMode.ALL else " OR "
    return CompiledPredicate(sql="(" + joiner.join(fragments) + ")", params=params)


def _free_text_predicate(
    values: tuple[Any, ...], index: int, *, include_title: bool = False
) -> CompiledPredicate:
    """Search posting prose, and the title too when the contract promises it.

    A free-text filter is a search of the description, because that is where the
    posting writes its prose. The role fallback is different: the contract says a
    role with no canonical category falls back onto the title *and* the
    description, so it searches both. Telling the model it searched a column it
    did not search would be a reporting lie, which is the one class of error the
    evidence labels exist to prevent.
    """
    terms: list[str] = []
    params: dict[str, Any] = {}
    for position, value in enumerate(values):
        name = f"f{index}_{position}"
        params[name] = _like_value(str(value))
        legs = [f"description ILIKE :{name}"]
        if include_title:
            title_name = f"ft{index}_{position}"
            params[title_name] = params[name]
            legs.append(f"title ILIKE :{title_name}")
        # One term is satisfied by either column; separate terms are all required.
        terms.append("(" + " OR ".join(legs) + ")")
    return CompiledPredicate(sql="(" + " AND ".join(terms) + ")", params=params)


def _where(predicates: tuple[CompiledPredicate, ...]) -> str:
    if not predicates:
        return ""
    return " WHERE " + " AND ".join(predicate.sql for predicate in predicates)


def _projection(columns: tuple[str, ...]) -> str:
    for column in columns:
        if column not in VISIBLE_COLUMNS:
            raise QueryRequestError(f"'{column}' is not an agent-visible column")
    return ", ".join(columns)


def compile_plan(plan: QueryPlan, limits: dict[str, int]) -> CompiledQuery:
    """Compile a validated plan into its statements."""
    if plan.shape is QueryShape.DETAIL:
        return _compile_detail(plan, limits)
    if plan.shape is QueryShape.COMPARE:
        return _compile_compare(plan, limits)
    if plan.shape is QueryShape.LIST:
        return _compile_list(plan, limits)
    if plan.shape is QueryShape.COUNT:
        return _compile_count(plan)
    if plan.shape is QueryShape.GROUP_COUNT:
        return _compile_group_count(plan, limits)
    if plan.shape is QueryShape.TOP_N:
        return _compile_top_n(plan, limits)
    return _compile_aggregate(plan, limits)


def _compile_detail(plan: QueryPlan, limits: dict[str, int]) -> CompiledQuery:
    sql = (
        f"SELECT {_projection(DETAIL_PROJECTION)}, count(*) OVER () AS match_total "
        f"FROM {TABLE} WHERE id = ANY(:ids) ORDER BY id"
    )
    return CompiledQuery(
        shape=plan.shape,
        statements=(Statement(sql=sql, params={"ids": list(plan.ids)}, role="rows"),),
        display_cap=limits["max_detail_rows"],
    )


def _compile_list(plan: QueryPlan, limits: dict[str, int]) -> CompiledQuery:
    where, params = _compile_filters(plan.filters)
    # The window count is computed over the full matching set before the limit,
    # so a truncated list still knows how many rows exist.
    sql = (
        f"SELECT {_projection(LIST_PROJECTION)}, count(*) OVER () AS match_total "
        f"FROM {TABLE}{where} ORDER BY id LIMIT :display_cap"
    )
    return CompiledQuery(
        shape=plan.shape,
        statements=(
            Statement(
                sql=sql,
                params={**params, "display_cap": limits["max_rows"] + 1},
                role="rows",
            ),
        ),
        display_cap=limits["max_rows"],
    )


def _compile_count(plan: QueryPlan) -> CompiledQuery:
    where, params = _compile_filters(plan.filters)
    sql = f"SELECT count(*) AS count FROM {TABLE}{where}"
    return CompiledQuery(shape=plan.shape, statements=(Statement(sql=sql, params=params, role="count"),), display_cap=0)


def _compile_group_count(plan: QueryPlan, limits: dict[str, int]) -> CompiledQuery:
    assert plan.group_by is not None  # guaranteed by the request model
    where, params = _compile_filters(plan.filters)
    if plan.group_by is GroupField.TECHNOLOGY:
        raise QueryRequestError(
            "grouping by technology is not a single column: use one technology per request, "
            "or a free-text question about the description"
        )
    column = _GROUP_COLUMNS[plan.group_by]
    groups = (
        f"SELECT COALESCE({column}, '(not recorded)') AS value, count(*) AS n "
        f"FROM {TABLE}{where} GROUP BY 1 ORDER BY n DESC, value ASC LIMIT :group_cap"
    )
    total = f"SELECT count(*) AS count FROM {TABLE}{where}"
    return CompiledQuery(
        shape=plan.shape,
        statements=(
            Statement(sql=groups, params={**params, "group_cap": limits["max_group_values"]}, role="groups"),
            Statement(sql=total, params=params, role="total"),
        ),
        display_cap=limits["max_group_values"],
    )


def _compile_top_n(plan: QueryPlan, limits: dict[str, int]) -> CompiledQuery:
    assert plan.top is not None  # guaranteed by the request model
    where, params = _compile_filters(plan.filters)
    column = _SORT_COLUMNS[plan.top.order_by]
    direction = "DESC" if plan.top.descending else "ASC"
    rows = (
        f"SELECT {_projection(LIST_PROJECTION)}, count(*) OVER () AS match_total "
        f"FROM {TABLE}{where} ORDER BY {column} {direction} NULLS LAST, id ASC LIMIT :top_n"
    )
    # A row with no value for the ranked attribute is not ranked, so the count
    # of those rows is reported rather than silently dropped.
    skipped = f"SELECT count(*) AS skipped FROM {TABLE}{_with(where, f'{column} IS NULL')}"
    return CompiledQuery(
        shape=plan.shape,
        statements=(
            Statement(sql=rows, params={**params, "top_n": plan.top.n}, role="rows"),
            Statement(sql=skipped, params=params, role="skipped"),
        ),
        display_cap=plan.top.n,
        salary_currency=_pinned_currency(plan.filters),
    )


def _compile_aggregate(plan: QueryPlan, limits: dict[str, int]) -> CompiledQuery:
    if plan.metric is Metric.SHARE:
        return _compile_share(plan)
    if plan.metric in (Metric.AVERAGE_SALARY, Metric.MEDIAN_SALARY):
        return _compile_salary_aggregate(plan, limits)
    return _compile_count(plan)


def _compile_share(plan: QueryPlan) -> CompiledQuery:
    assert plan.share is not None  # guaranteed by the request model
    base_where, base_params = _compile_filters(plan.filters)
    test = compile_predicate(plan.share, 900)
    # One statement, one pass: the denominator is the base set including rows
    # whose tested field is null, and the excluded count is reported with it.
    sql = (
        "SELECT count(*) AS denominator, "
        f"count(*) FILTER (WHERE {test.sql}) AS numerator, "
        "count(*) FILTER (WHERE " + _null_test(plan.share.field) + ") AS excluded_null_field "
        f"FROM {TABLE}{base_where}"
    )
    return CompiledQuery(
        shape=plan.shape,
        statements=(Statement(sql=sql, params={**base_params, **test.params}, role="share"),),
        display_cap=0,
    )


def _compile_salary_aggregate(plan: QueryPlan, limits: dict[str, int]) -> CompiledQuery:
    currency = _pinned_currency(plan.filters)
    where, params = _compile_filters(plan.filters)
    measure = "avg(salary_min)" if plan.metric is Metric.AVERAGE_SALARY else (
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY salary_min)"
    )
    if currency is not None:
        grouped = (
            "SELECT :currency AS currency, count(*) AS rows, count(salary_min) AS with_salary_min, "
            f"{measure} AS value FROM {TABLE}{_with(where, 'salary_currency = :currency')}"
        )
    else:
        # No currency was named, so the figure is reported per currency. A
        # single number across currencies is never produced.
        grouped = (
            "SELECT COALESCE(salary_currency, '(not disclosed)') AS currency, count(*) AS rows, "
            f"count(salary_min) AS with_salary_min, {measure} AS value "
            f"FROM {TABLE}{where} GROUP BY 1 ORDER BY currency ASC LIMIT :group_cap"
        )
    # The excluded count has to describe the same set as the figure beside it. When
    # the request pinned one currency, the figure is that currency's, so the count
    # has to be scoped the same way or the answer reads a per-currency number that
    # is actually global.
    excluded_scope = "salary_min IS NULL"
    if currency is not None:
        excluded_scope = _with("salary_currency = :currency", excluded_scope)
    excluded = f"SELECT count(*) AS excluded FROM {TABLE}{_with(where, excluded_scope)}"
    statements = [
        Statement(
            sql=grouped,
            params={**params, **({"currency": currency} if currency else {"group_cap": limits["max_group_values"]})},
            role="aggregate",
        ),
        Statement(sql=excluded, params=params, role="excluded"),
    ]
    return CompiledQuery(
        shape=plan.shape,
        statements=tuple(statements),
        display_cap=0,
        salary_currency=currency,
    )


def _compile_compare(plan: QueryPlan, limits: dict[str, int]) -> CompiledQuery:
    if plan.metric in (Metric.AVERAGE_SALARY, Metric.MEDIAN_SALARY):
        raise QueryRequestError(
            "comparing salary aggregates is not supported: scope both sides to one currency and "
            "compare the two counts instead"
        )
    if plan.metric is Metric.SHARE:
        raise QueryRequestError(
            "comparing shares is not supported at v0: compare the two counts, which share one definition"
        )
    statements: list[Statement] = []
    display_cap = 0
    for side, filters in enumerate(plan.sides):
        where, params = _compile_filters(filters)
        statements.append(
            Statement(
                sql=f"SELECT count(*) AS count FROM {TABLE}{where}",
                params=params,
                role=f"side{side}",
            )
        )
    return CompiledQuery(shape=plan.shape, statements=tuple(statements), display_cap=display_cap)


def _compile_filters(filters: tuple[NormalizedFilter, ...]) -> tuple[str, dict[str, Any]]:
    compiled = [compile_predicate(predicate, index) for index, predicate in enumerate(filters)]
    params: dict[str, Any] = {}
    for predicate in compiled:
        params.update(predicate.params)
    return _where(tuple(compiled)), params


def _pinned_currency(filters: tuple[NormalizedFilter, ...]) -> str | None:
    for predicate in filters:
        if predicate.field is FilterField.SALARY_CURRENCY:
            return str(predicate.values[0])
    return None


def _null_test(field: FilterField) -> str:
    """The test for "this row does not record the tested field".

    ``has_link`` is derived from a nullable column rather than stored, so a row
    that records no link is the row whose link cannot be decided, and the
    excluded count is exactly that. ``is_internship`` is not null by schema, so
    its excluded count is always zero, which the answer still reports.
    """
    if field is FilterField.TECHNOLOGY:
        return "NOT (tech_stack IS NOT NULL AND btrim(tech_stack) <> '')"
    if field is FilterField.FREE_TEXT:
        return "description IS NULL"
    if field is FilterField.HAS_LINK:
        return "source_url IS NULL"
    return f"{field.value} IS NULL"


def _with(where: str, clause: str) -> str:
    """Add one condition to a WHERE clause that may be empty.

    Concatenating ``AND`` onto an absent clause produced a statement no database
    accepts, so the join is done in one place rather than at each call site.
    """
    return f"{where} AND {clause}" if where else f" WHERE {clause}"
