"""The reporting defects the post-merge review found, held shut.

Each of these is a case where the answer described something the query layer did not do: a
criterion that never ran, a column that was never searched, an excluded count scoped to a
different set than the figure beside it, and a bounded group list with no disclosure. That is
the class the evidence labels exist to prevent, so each fix is asserted on the emitted SQL and
on the assembled result rather than on a comment.
"""

from __future__ import annotations

import pytest

from src.services.query.compiler import compile_plan
from src.services.query.plan import (
    AmbiguousQueryError,
    Filter,
    JobQueryRequest,
    QueryShape,
    query_limits,
)
from src.services.query.planner import build_plan
from src.services.query.results import QueryState
from src.services.query.service import JobQueryService


class StubExecutor:
    """Records what was compiled and returns canned rows."""

    def __init__(self, rows: dict[str, list[dict]] | None = None) -> None:
        self.rows = rows or {}
        self.compiled = None

    def run(self, compiled):
        self.compiled = compiled
        return self.rows


def service_with(rows: dict[str, list[dict]] | None = None) -> JobQueryService:
    return JobQueryService(executor=StubExecutor(rows))


def compiled(**request):
    return compile_plan(build_plan(JobQueryRequest(**request)), query_limits())


def sql_of(query) -> str:
    return "\n".join(statement.sql for statement in query.statements)


# --- #532 a threshold carries one bound --------------------------------------


class TestASalaryThresholdCarriesOneBound:
    def test_two_bounds_are_a_question_rather_than_a_silent_drop(self) -> None:
        with pytest.raises(AmbiguousQueryError):
            build_plan(
                JobQueryRequest(
                    shape="count", filters=[{"field": "salary_min", "values": [1000, 2000]}]
                )
            )

    def test_the_guard_holds_however_the_filter_arrives(self) -> None:
        with pytest.raises(AmbiguousQueryError):
            build_plan(
                JobQueryRequest(
                    shape="count", filters=[Filter(field="salary_min", values=[1000, 2000])]
                )
            )

    def test_one_bound_compiles_to_one_predicate_and_reports_one_value(self) -> None:
        executor = StubExecutor({"count": [{"count": 24}]})
        result = JobQueryService(executor=executor).answer(
            JobQueryRequest(
                shape="count", filters=[{"field": "salary_min", "values": [1000]}]
            )
        )
        assert "salary_min >= :n0" in sql_of(executor.compiled)
        assert result.applied[0].values == (1000.0,)

    def test_a_rejected_threshold_never_reaches_the_database(self) -> None:
        executor = StubExecutor()
        result = JobQueryService(executor=executor).answer(
            JobQueryRequest(
                shape="count", filters=[{"field": "salary_min", "values": [1000, 2000]}]
            )
        )
        assert result.state is QueryState.AMBIGUOUS
        assert executor.compiled is None


# --- #540 the role fallback searches what it says it searches -----------------


class TestTheRoleFallbackSearchesTheTitleToo:
    def test_the_fallback_predicate_reads_both_columns(self) -> None:
        query = compiled(shape="list", filters=[{"field": "role", "values": ["Rustacean"]}])
        sql = sql_of(query)
        assert "clean_jobs" in sql
        assert "description ILIKE :f0_0" in sql
        assert "title ILIKE :ft0_0" in sql
        assert " OR " in sql

    def test_a_plain_free_text_filter_still_searches_only_the_description(self) -> None:
        query = compiled(shape="count", filters=[{"field": "free_text", "values": ["remote"]}])
        sql = sql_of(query)
        assert "description ILIKE :f0_0" in sql
        assert "title ILIKE" not in sql

    def test_the_caveat_names_the_title_because_the_query_now_does(self) -> None:
        from src.agents.tools.v0_query_jobs import CAVEAT_TEXT

        assert "tiêu đề" in CAVEAT_TEXT["ROLE_FALLBACK"]

    def test_the_fallback_is_still_reported_as_a_fallback(self) -> None:
        result = service_with({"rows": []}).answer(
            JobQueryRequest(shape="list", filters=[{"field": "role", "values": ["Rustacean"]}])
        )
        assert result.applied[0].basis == "fallback"
        assert result.applied[0].field.value == "free_text"


# --- #534 a saturated group list is disclosed --------------------------------


class TestASaturatedGroupListIsDisclosed:
    def _result(self, groups: int, total: int = 5000):
        cap = query_limits()["max_group_values"]
        rows = {
            "groups": [{"value": f"city-{index}", "n": 40} for index in range(groups)],
            "total": [{"count": total}],
        }
        return JobQueryService(executor=StubExecutor(rows)).answer(
            JobQueryRequest(shape="group_count", group_by="location")
        ), cap

    def test_a_group_list_at_the_cap_reports_truncation(self) -> None:
        cap = query_limits()["max_group_values"]
        result, _ = self._result(groups=cap)
        assert result.displayed_count == cap
        assert result.truncated is True
        assert "TRUNCATION" in result.caveats

    def test_a_short_group_list_reports_no_truncation(self) -> None:
        result, _ = self._result(groups=3)
        assert result.truncated is False
        assert "TRUNCATION" not in result.caveats

    def test_the_total_is_matching_posts_and_is_not_a_saturation_signal(self) -> None:
        """20 groups routinely cover hundreds of postings, so counts cannot compare."""
        result, _ = self._result(groups=3, total=5000)
        assert result.match_total == 5000
        assert result.displayed_count == 3
        assert result.truncated is False


# --- #536 the excluded count describes the figure's set ----------------------


class TestTheExcludedCountSharesTheFiguresScope:
    def test_a_pinned_currency_scopes_both_statements(self) -> None:
        query = compiled(
            shape="aggregate",
            metric="average_salary",
            filters=[
                {"field": "role", "values": ["Data Scientist"]},
                {"field": "salary_currency", "values": ["USD"]},
            ],
        )
        aggregate_sql, excluded_sql = (statement.sql for statement in query.statements)
        assert "salary_currency = :currency" in aggregate_sql
        assert "salary_currency = :currency" in excluded_sql
        assert "salary_min IS NULL" in excluded_sql

    def test_with_no_pinned_currency_the_excluded_count_spans_the_base(self) -> None:
        query = compiled(
            shape="aggregate",
            metric="average_salary",
            filters=[{"field": "role", "values": ["Data Scientist"]}],
        )
        aggregate_sql, excluded_sql = (statement.sql for statement in query.statements)
        assert "GROUP BY 1" in aggregate_sql
        assert "salary_currency" not in excluded_sql

    def test_the_reported_exclusion_is_the_one_its_scope_produced(self) -> None:
        service = service_with(
            {
                "aggregate": [{"currency": "USD", "rows": 1, "with_salary_min": 1, "value": 2500.0}],
                "excluded": [{"excluded": 0}],
            }
        )
        result = service.answer(
            JobQueryRequest(
                shape="aggregate",
                metric="average_salary",
                filters=[{"field": "salary_currency", "values": ["USD"]}],
            )
        )
        assert result.excluded_no_salary == 0


# --- #584 the excluded-no-salary count is one total, not one per currency ---


class TestTheExcludedCountIsOneTotalNotOnePerCurrency:
    """One global exclusion count copied into every bucket read as N exclusions for
    one excluded row. The count is a total over the matched set, so it belongs on the
    result, is rendered once, and the gate can no longer be satisfied by a number that
    is merely present on every bucket.
    """

    THREE_BUCKETS_ONE_EXCLUDED = {
        "aggregate": [
            {"currency": "(not disclosed)", "rows": 1, "with_salary_min": 0, "value": None},
            {"currency": "USD", "rows": 1, "with_salary_min": 1, "value": 2500.0},
            {"currency": "VND", "rows": 3, "with_salary_min": 3, "value": 23333333.3},
        ],
        "excluded": [{"excluded": 1}],
    }

    def test_the_count_is_carried_once_on_the_result(self) -> None:
        result = service_with(self.THREE_BUCKETS_ONE_EXCLUDED).answer(
            JobQueryRequest(shape="aggregate", metric="average_salary")
        )
        assert len(result.aggregate) == 3
        assert result.excluded_no_salary == 1

    def test_no_bucket_carries_its_own_exclusion_count(self) -> None:
        """The per-bucket field is gone, so nothing can restate the total per currency."""
        result = service_with(self.THREE_BUCKETS_ONE_EXCLUDED).answer(
            JobQueryRequest(shape="aggregate", metric="average_salary")
        )
        for bucket in result.aggregate:
            assert "excluded_no_salary" not in type(bucket).model_fields

    def test_the_renderer_states_the_total_once_not_once_per_currency(self) -> None:
        from src.agents.tools.v0_query_jobs import render_result

        result = service_with(self.THREE_BUCKETS_ONE_EXCLUDED).answer(
            JobQueryRequest(shape="aggregate", metric="average_salary")
        )
        rendered = render_result(result, {"shape": "aggregate", "metric": "average_salary"})
        assert rendered.count("ROWS WITH NO SALARY (excluded, total): 1") == 1, rendered
        # The per-bucket spelling is what made three buckets read as three exclusions.
        assert "excluded_no_salary=" not in rendered, rendered

    def test_a_zero_exclusion_is_still_stated(self) -> None:
        """A zero is a statement about the set, not the absence of one."""
        from src.agents.tools.v0_query_jobs import render_result

        result = service_with(
            {"aggregate": [{"currency": "USD", "rows": 1, "with_salary_min": 1, "value": 2500.0}],
             "excluded": [{"excluded": 0}]}
        ).answer(JobQueryRequest(shape="aggregate", metric="average_salary"))
        rendered = render_result(result, {"shape": "aggregate", "metric": "average_salary"})
        assert "ROWS WITH NO SALARY (excluded, total): 0" in rendered

    def test_a_result_that_is_not_a_salary_aggregate_carries_no_count(self) -> None:
        result = service_with({"list": [{"id": 1}], "total": [{"count": 1}]}).answer(
            JobQueryRequest(shape="list")
        )
        assert result.excluded_no_salary is None


# --- #541 one owner per caveat, and a docstring that matches the code --------


class TestOneOwnerPerCaveat:
    def test_the_role_fallback_caveat_is_printed_once(self) -> None:
        result = service_with({"rows": []}).answer(
            JobQueryRequest(shape="list", filters=[{"field": "role", "values": ["Rustacean"]}])
        )
        assert result.caveats.count("ROLE_FALLBACK") == 1

    @pytest.mark.parametrize(
        "shape_request, rows",
        [
            ({"shape": "count"}, {"count": [{"count": 1}]}),
            (
                {"shape": "list", "filters": [{"field": "free_text", "values": ["remote"]}]},
                {"rows": []},
            ),
            (
                {"shape": "group_count", "group_by": "location"},
                {"groups": [{"value": "Hanoi", "n": 1}], "total": [{"count": 1}]},
            ),
        ],
    )
    def test_no_caveat_is_ever_emitted_twice(self, shape_request, rows) -> None:
        result = service_with(rows).answer(JobQueryRequest(**shape_request))
        assert len(result.caveats) == len(set(result.caveats)), shape_request

    def test_the_tool_docstring_does_not_claim_it_is_unregistered(self) -> None:
        import src.agents.tools.v0_query_jobs as tool_module

        docstring = (tool_module.__doc__ or "").casefold()
        assert "not registered on the serving mcp surface" not in docstring
        assert "served tool of the governed v0 bundle" in docstring


def test_the_served_bundle_still_registers_only_the_governed_tool() -> None:
    """The cutover is unchanged by these fixes: one tool, one prompt."""
    import asyncio

    from src.agents.mcp.job_server import V0_QUERY_TOOL, create_job_mcp_server

    tools = {tool.name for tool in asyncio.run(create_job_mcp_server()._list_tools())}
    assert tools == {V0_QUERY_TOOL}
    assert QueryShape.DETAIL.value == "detail"