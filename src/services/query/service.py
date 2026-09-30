"""The governed query service.

One entry point, ``JobQueryService.answer``, that takes a typed request and
returns a typed result. It is the whole surface the agent needs for search and
analytics, and it is the same surface for both, which is what stops a percentage
and a list from disagreeing about the data they looked at.

The service depends on no framework: not on FastAPI, not on LangChain, not on
tracing. The only import that reaches outward is the agent session factory, so
it can be pointed at a fixture database in a test without anything else in the
process being redirected.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.services.query.compiler import CompiledQuery, compile_plan
from src.services.query.execution import BoundedExecutor, QueryExecutionError
from src.services.query.plan import (
    AmbiguousQueryError,
    FilterField,
    GroupField,
    JobQueryRequest,
    Metric,
    NormalizedFilter,
    QueryPlan,
    QueryRequestError,
    QueryShape,
    UnsupportedQueryError,
    query_limits,
)
from src.services.query.planner import build_plan
from src.services.query.results import (
    AppliedCriterion,
    GroupRow,
    QueryResult,
    QueryState,
    SalaryAggregate,
    ShareResult,
)

CAVEAT_ROLE_FALLBACK = "ROLE_FALLBACK"
CAVEAT_FREE_TEXT = "FREE_TEXT_HEDGE"
CAVEAT_CURRENCY_SCOPED = "CURRENCY_SCOPED"
CAVEAT_PERIOD_UNKNOWN = "PERIOD_UNKNOWN"
CAVEAT_DENOMINATOR = "DENOMINATOR_STATED"
CAVEAT_MATCH_BASIS = "MATCH_BASIS"
CAVEAT_TRUNCATION = "TRUNCATION"
CAVEAT_COVERAGE_STATED = "COVERAGE_STATED"


class JobQueryService:
    """Validate, compile, execute, and report one request."""

    def __init__(self, executor: BoundedExecutor | None = None) -> None:
        self._executor = executor or BoundedExecutor()

    def answer(self, request: JobQueryRequest) -> QueryResult:
        """Return a result for a well-formed request, never an exception.

        A request the service cannot serve becomes a state, not a traceback: a
        model must be able to read ``UNSUPPORTED`` and re-ask, and a user must
        never see a stack trace because a field name was wrong.
        """
        try:
            plan = build_plan(request)
            compiled = compile_plan(plan, query_limits())
        except UnsupportedQueryError as exc:
            return QueryResult(state=QueryState.UNSUPPORTED, shape=request.shape, message=str(exc))
        except AmbiguousQueryError as exc:
            return QueryResult(state=QueryState.AMBIGUOUS, shape=request.shape, message=exc.question)
        except QueryRequestError as exc:
            # A malformed request is the caller's to repair, not a data answer.
            return QueryResult(
                state=QueryState.ERROR,
                shape=request.shape,
                repairable=True,
                message=str(exc),
            )

        try:
            rows = self._executor.run(compiled)
        except QueryExecutionError as exc:
            return QueryResult(state=QueryState.ERROR, shape=request.shape, message=str(exc))
        return self._assemble(plan, compiled, rows)

    # -- assembly ----------------------------------------------------------

    def _assemble(
        self, plan: QueryPlan, compiled: CompiledQuery, rows: dict[str, list[dict[str, Any]]]
    ) -> QueryResult:
        applied = _applied(plan)
        caveats = list(plan.caveats)
        # The contract attaches MATCH_BASIS whenever a filter was applied, not only
        # for a technology token match, so each of these three checks was narrower
        # than the contract until the v0 gate found it. Every one is a fact about
        # the shape, and every one is appended at most once.
        if applied:
            _add(caveats, CAVEAT_MATCH_BASIS)
        if any(criterion.basis == "free_text" for criterion in applied):
            _add(caveats, CAVEAT_FREE_TEXT)
        if any(criterion.basis == "fallback" for criterion in applied):
            _add(caveats, CAVEAT_ROLE_FALLBACK)
        if any(criterion.field is FilterField.SALARY_CURRENCY for criterion in applied):
            _add(caveats, CAVEAT_CURRENCY_SCOPED)
        # A grouping over a nullable recorded field states its coverage, because a
        # group missing a value is a group the answer has to name.
        if plan.group_by in (GroupField.JOB_LEVEL, GroupField.SALARY_CURRENCY):
            _add(caveats, CAVEAT_COVERAGE_STATED)

        if plan.shape is QueryShape.DETAIL:
            return self._detail(applied, caveats, rows)
        if plan.shape is QueryShape.LIST:
            return self._listing(applied, caveats, rows, compiled.display_cap)
        if plan.shape is QueryShape.COUNT:
            return self._count(applied, caveats, rows)
        if plan.shape is QueryShape.GROUP_COUNT:
            return self._groups(applied, caveats, rows)
        if plan.shape is QueryShape.TOP_N:
            return self._top_n(applied, caveats, rows, compiled.display_cap)
        if plan.shape is QueryShape.COMPARE:
            return self._compare(applied, caveats, rows)
        return self._aggregate(applied, caveats, rows, plan, compiled)

    def _detail(
        self, applied: list[AppliedCriterion], caveats: list[str], rows: dict[str, list[dict[str, Any]]]
    ) -> QueryResult:
        found = _strip_total(rows.get("rows", []))
        return QueryResult(
            state=QueryState.ANSWERED if found else QueryState.EMPTY,
            shape=QueryShape.DETAIL,
            applied=applied,
            caveats=caveats,
            match_total=len(found),
            displayed_count=len(found),
            columns=list(found[0].keys()) if found else [],
            rows=found,
        )

    def _listing(
        self,
        applied: list[AppliedCriterion],
        caveats: list[str],
        rows: dict[str, list[dict[str, Any]]],
        display_cap: int,
    ) -> QueryResult:
        fetched = rows.get("rows", [])
        match_total = _int_or_none(fetched[0].get("match_total")) if fetched else 0
        shown = _strip_total(fetched)[:display_cap]
        truncated = match_total is not None and match_total > len(shown)
        if truncated:
            _add(caveats, CAVEAT_TRUNCATION)
        return QueryResult(
            state=QueryState.ANSWERED if shown else QueryState.EMPTY,
            shape=QueryShape.LIST,
            applied=applied,
            caveats=caveats,
            match_total=match_total or 0,
            displayed_count=len(shown),
            truncated=truncated,
            columns=list(shown[0].keys()) if shown else [],
            rows=shown,
        )

    def _count(
        self, applied: list[AppliedCriterion], caveats: list[str], rows: dict[str, list[dict[str, Any]]]
    ) -> QueryResult:
        count = int(rows.get("count", [{}])[0].get("count", 0))
        return QueryResult(
            state=QueryState.ANSWERED if count else QueryState.EMPTY,
            shape=QueryShape.COUNT,
            applied=applied,
            caveats=caveats,
            match_total=count,
            displayed_count=0,
            count=count,
        )

    def _groups(
        self, applied: list[AppliedCriterion], caveats: list[str], rows: dict[str, list[dict[str, Any]]]
    ) -> QueryResult:
        groups = [GroupRow(value=str(row["value"]), count=int(row["n"])) for row in rows.get("groups", [])]
        total = int(rows.get("total", [{}])[0].get("count", 0)) if rows.get("total") else sum(g.count for g in groups)
        return QueryResult(
            state=QueryState.ANSWERED if groups else QueryState.EMPTY,
            shape=QueryShape.GROUP_COUNT,
            applied=applied,
            caveats=caveats,
            match_total=total,
            displayed_count=len(groups),
            groups=groups,
        )

    def _top_n(
        self,
        applied: list[AppliedCriterion],
        caveats: list[str],
        rows: dict[str, list[dict[str, Any]]],
        display_cap: int,
    ) -> QueryResult:
        fetched = rows.get("rows", [])
        match_total = _int_or_none(fetched[0].get("match_total")) if fetched else 0
        shown = _strip_total(fetched)[:display_cap]
        skipped = int(rows.get("skipped", [{}])[0].get("skipped", 0)) if rows.get("skipped") else 0
        if skipped:
            _add(caveats, CAVEAT_COVERAGE_STATED)
        return QueryResult(
            state=QueryState.ANSWERED if shown else QueryState.EMPTY,
            shape=QueryShape.TOP_N,
            applied=applied,
            caveats=caveats,
            match_total=match_total or 0,
            displayed_count=len(shown),
            truncated=match_total is not None and match_total > len(shown),
            columns=list(shown[0].keys()) if shown else [],
            rows=shown,
            skipped_unranked=skipped,
        )

    def _compare(
        self, applied: list[AppliedCriterion], caveats: list[str], rows: dict[str, list[dict[str, Any]]]
    ) -> QueryResult:
        sides = [int(rows.get(f"side{index}", [{}])[0].get("count", 0)) for index in range(2)]
        caveats.append(CAVEAT_DENOMINATOR)
        return QueryResult(
            state=QueryState.ANSWERED if any(sides) else QueryState.EMPTY,
            shape=QueryShape.COMPARE,
            applied=applied,
            caveats=caveats,
            match_total=sum(sides),
            displayed_count=2,
            compare_sides=sides,
        )

    def _aggregate(
        self,
        applied: list[AppliedCriterion],
        caveats: list[str],
        rows: dict[str, list[dict[str, Any]]],
        plan: QueryPlan,
        compiled: CompiledQuery,
    ) -> QueryResult:
        if plan.metric is Metric.SHARE:
            return self._share(applied, caveats, rows)
        return self._salary(applied, caveats, rows, compiled)

    def _share(
        self, applied: list[AppliedCriterion], caveats: list[str], rows: dict[str, list[dict[str, Any]]]
    ) -> QueryResult:
        row = rows.get("share", [{}])[0]
        denominator = int(row.get("denominator", 0))
        numerator = int(row.get("numerator", 0))
        excluded = int(row.get("excluded_null_field", 0))
        percent = round(numerator * 100.0 / denominator, 1) if denominator else None
        _add(caveats, CAVEAT_DENOMINATOR)
        return QueryResult(
            state=QueryState.ANSWERED if denominator else QueryState.EMPTY,
            shape=QueryShape.AGGREGATE,
            applied=applied,
            caveats=caveats,
            match_total=denominator,
            displayed_count=0,
            share=ShareResult(
                numerator=numerator,
                denominator=denominator,
                excluded_null_field=excluded,
                percent=percent,
            ),
        )

    def _salary(
        self,
        applied: list[AppliedCriterion],
        caveats: list[str],
        rows: dict[str, list[dict[str, Any]]],
        compiled: CompiledQuery,
    ) -> QueryResult:
        excluded = int(rows.get("excluded", [{}])[0].get("excluded", 0)) if rows.get("excluded") else 0
        aggregates = [
            SalaryAggregate(
                currency=str(row.get("currency")),
                rows=int(row.get("rows", 0)),
                with_salary_min=int(row.get("with_salary_min", 0)),
                value=_float_or_none(row.get("value")),
                excluded_no_salary=excluded,
            )
            for row in rows.get("aggregate", [])
        ]
        for label in (CAVEAT_CURRENCY_SCOPED, CAVEAT_PERIOD_UNKNOWN, CAVEAT_DENOMINATOR):
            _add(caveats, label)
        measured = [item for item in aggregates if item.value is not None]
        return QueryResult(
            state=QueryState.ANSWERED if measured else QueryState.EMPTY,
            shape=QueryShape.AGGREGATE,
            applied=applied,
            caveats=caveats,
            match_total=sum(item.rows for item in aggregates),
            displayed_count=len(aggregates),
            aggregate=aggregates,
        )


def _add(caveats: list[str], label: str) -> None:
    """Append a caveat once, so two rules for the same label cannot duplicate it."""
    if label not in caveats:
        caveats.append(label)


def _applied(plan: QueryPlan) -> list[AppliedCriterion]:
    """The criteria as applied, tagged with the side they belong to."""
    criteria: list[AppliedCriterion] = [_criterion(predicate, None) for predicate in plan.filters]
    for side_index, side in enumerate(plan.sides):
        criteria.extend(_criterion(predicate, side_index) for predicate in side)
    if plan.share is not None:
        criteria.append(_criterion(plan.share, None))
    return criteria


def _criterion(predicate: NormalizedFilter, side: int | None) -> AppliedCriterion:
    return AppliedCriterion(
        field=predicate.field,
        values=predicate.values,
        basis=predicate.basis,
        side=side,
    )


def _strip_total(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if key != "match_total"} for row in rows]


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return round(float(value), 1)
    return round(float(value), 1)
