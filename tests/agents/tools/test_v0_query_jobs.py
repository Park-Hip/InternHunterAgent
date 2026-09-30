"""The model-facing surface of the governed query core.

The tool is the only thing a model touches. These tests hold it to three
promises: a malformed request comes back as something the model can repair, a
refusal never looks like an answer, and the rendered evidence never contains
SQL, a hidden column, or an instruction the model could mistake for its own.
"""

from __future__ import annotations


from src.agents.tools.v0_query_jobs import (
    TOOL_DESCRIPTION,
    TOOL_NAME,
    render_result,
    run_query_jobs,
)
from src.services.query.plan import FilterField, JobQueryRequest, QueryShape
from src.services.query.results import (
    AppliedCriterion,
    GroupRow,
    QueryResult,
    QueryState,
    SalaryAggregate,
    ShareResult,
)


class StubService:
    def __init__(self, result: QueryResult | Exception) -> None:
        self.result = result
        self.requests: list[JobQueryRequest] = []

    def answer(self, request: JobQueryRequest) -> QueryResult:
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def answered(**overrides) -> QueryResult:
    base = {"state": QueryState.ANSWERED, "shape": QueryShape.LIST}
    base.update(overrides)
    return QueryResult(**base)


class TestToolContract:
    def test_the_name_and_description_state_the_contract(self) -> None:
        assert TOOL_NAME == "query_jobs"
        assert "no SQL" in TOOL_DESCRIPTION
        for shape in QueryShape:
            assert shape.value in TOOL_DESCRIPTION, shape
        for field in ("technology", "location", "job_level", "free_text", "salary_currency"):
            assert field in TOOL_DESCRIPTION, field

    def test_a_malformed_request_comes_back_repairable(self) -> None:
        service = StubService(answered())
        output = run_query_jobs({"shape": "sql"}, service=service)
        assert output.startswith("INVALID REQUEST")
        assert "Allowed shapes:" in output
        assert "list" in output
        assert "share" in output
        assert "technology" in output
        assert service.requests == []

    def test_an_empty_request_comes_back_repairable(self) -> None:
        output = run_query_jobs({}, service=StubService(answered()))
        assert output.startswith("INVALID REQUEST")

    def test_a_valid_request_is_parsed_into_the_typed_model(self) -> None:
        service = StubService(answered())
        run_query_jobs(
            {"shape": "count", "filters": [{"field": "role", "values": ["AI Engineer"]}]},
            service=service,
        )
        assert service.requests[0].shape is QueryShape.COUNT
        assert service.requests[0].filters[0].field is FilterField.ROLE

    def test_an_unknown_key_is_rejected_rather_than_ignored(self) -> None:
        output = run_query_jobs({"shape": "count", "sql": "SELECT 1"}, service=StubService(answered()))
        assert output.startswith("INVALID REQUEST")


class TestRefusalsAreNotAnswers:
    def test_unsupported_is_rendered_as_unsupported(self) -> None:
        result = QueryResult(
            state=QueryState.UNSUPPORTED,
            shape=QueryShape.COUNT,
            message="'Đà Lạt' is not a city this data holds.",
        )
        output = render_result(result)
        assert output.startswith("UNSUPPORTED")
        assert "not a city this data holds" in output
        assert "STATE:" not in output

    def test_ambiguous_carries_the_one_question(self) -> None:
        result = QueryResult(
            state=QueryState.AMBIGUOUS,
            shape=QueryShape.LIST,
            message="Bạn muốn lọc theo vai trò hay công nghệ?",
        )
        output = render_result(result)
        assert output.startswith("AMBIGUOUS")
        assert output.count("?") == 1

    def test_error_does_not_present_a_number(self) -> None:
        result = QueryResult(
            state=QueryState.ERROR,
            shape=QueryShape.COUNT,
            message="The database could not answer that question.",
        )
        output = render_result(result)
        assert output.startswith("ERROR")
        assert "COUNT:" not in output

    def test_a_repairable_rejection_is_rendered_as_a_repair(self) -> None:
        result = QueryResult(
            state=QueryState.ERROR,
            shape=QueryShape.COUNT,
            repairable=True,
            message="filters[0] may hold at most 4 values, got 6",
        )
        output = render_result(result)
        assert output.startswith("INVALID REQUEST")
        assert "at most 4 values" in output
        assert "Allowed shapes:" in output


class TestEvidenceRendering:
    def test_a_list_reports_the_total_and_the_rows(self) -> None:
        result = answered(
            match_total=24,
            displayed_count=20,
            truncated=True,
            caveats=["TRUNCATION"],
            columns=["id", "title"],
            rows=[{"id": 1, "title": "AI Engineer"}, {"id": 2, "title": "AI Engineer Intern"}],
        )
        output = render_result(result, {"shape": "list"})
        assert "MATCH TOTAL: 24" in output
        assert "DISPLAYED: 20" in output
        assert "id=1" in output
        assert "CAVEAT [TRUNCATION]" in output

    def test_a_count_states_the_number(self) -> None:
        result = answered(shape=QueryShape.COUNT, count=24, match_total=24)
        assert "COUNT: 24" in render_result(result, {"shape": "count"})

    def test_a_share_states_its_denominator_and_exclusions(self) -> None:
        result = answered(
            shape=QueryShape.AGGREGATE,
            match_total=5,
            caveats=["DENOMINATOR_STATED"],
            share=ShareResult(numerator=5, denominator=5, excluded_null_field=0, percent=100.0),
        )
        output = render_result(result, {"shape": "aggregate", "metric": "share"})
        assert "SHARE: 5 trên 5" in output
        assert "EXCLUDED" in output
        assert "PERCENT: 100.0" in output
        assert "CAVEAT [DENOMINATOR_STATED]" in output

    def test_a_salary_figure_names_its_currency_and_rows(self) -> None:
        result = answered(
            shape=QueryShape.AGGREGATE,
            caveats=["CURRENCY_SCOPED", "PERIOD_UNKNOWN"],
            aggregate=[
                SalaryAggregate(
                    currency="VND", rows=3, with_salary_min=3, value=23333333.3, excluded_no_salary=1
                )
            ],
        )
        output = render_result(result, {"shape": "aggregate", "metric": "average_salary"})
        assert "CURRENCY VND" in output
        assert "rows=3" in output
        assert "excluded_no_salary=1" in output
        assert "CAVEAT [PERIOD_UNKNOWN]" in output

    def test_a_group_names_the_field_and_every_value(self) -> None:
        result = answered(
            shape=QueryShape.GROUP_COUNT,
            match_total=24,
            groups=[GroupRow(value="Hanoi", count=11), GroupRow(value="Da Nang", count=4)],
        )
        output = render_result(result, {"shape": "group_count", "group_by": "location"})
        assert "GROUPS BY thành phố" in output
        assert "- Hanoi: 11" in output
        assert "- Da Nang: 4" in output

    def test_a_top_n_names_the_ranking_and_the_unranked_rows(self) -> None:
        result = answered(
            shape=QueryShape.TOP_N,
            match_total=6,
            displayed_count=5,
            skipped_unranked=0,
            rows=[{"id": 1, "title": "AI Engineer"}],
        )
        output = render_result(
            result, {"shape": "top_n", "top": {"n": 5, "order_by": "salary_min", "descending": True}}
        )
        assert "RANKED BY: mức lương tối thiểu (cao nhất)" in output
        assert "NOT RANKED (thiếu giá trị): 0" in output

    def test_a_comparison_labels_both_sides(self) -> None:
        result = answered(shape=QueryShape.COMPARE, compare_sides=[7, 3], caveats=["DENOMINATOR_STATED"])
        output = render_result(result, {"shape": "compare"})
        assert "SIDE 1: 7" in output
        assert "SIDE 2: 3" in output

    def test_the_applied_criteria_name_the_field_and_the_canonical_value(self) -> None:
        result = answered(
            applied=[AppliedCriterion(field=FilterField.LOCATION, values=("Hanoi",), basis="column")]
        )
        output = render_result(result, {"shape": "list"})
        assert "APPLIED CRITERIA:" in output
        assert "thành phố: Hanoi" in output

    def test_a_comparison_criterion_is_tagged_with_its_side(self) -> None:
        result = answered(
            shape=QueryShape.COMPARE,
            compare_sides=[7, 3],
            applied=[
                AppliedCriterion(field=FilterField.LOCATION, values=("Hanoi",), basis="column", side=0),
                AppliedCriterion(
                    field=FilterField.LOCATION, values=("Ho Chi Minh City",), basis="column", side=1
                ),
            ],
        )
        output = render_result(result, {"shape": "compare"})
        assert "(vế 1): Hanoi" in output
        assert "(vế 2): Ho Chi Minh City" in output

    def test_an_empty_result_says_so_in_vietnamese(self) -> None:
        result = answered(state=QueryState.EMPTY, match_total=0)
        output = render_result(result, {"shape": "list"})
        assert "STATE: empty" in output
        assert "không tìm thấy tin đăng nào" in output

    def test_a_missing_value_renders_as_not_present_not_as_none(self) -> None:
        result = answered(shape=QueryShape.DETAIL, rows=[{"id": 4, "salary_min": None, "title": "x"}])
        output = render_result(result, {"shape": "detail"})
        assert "salary_min=(không có)" in output
        assert "None" not in output

    def test_the_rendering_never_contains_sql(self) -> None:
        result = answered(
            shape=QueryShape.COUNT,
            count=24,
            match_total=24,
            applied=[AppliedCriterion(field=FilterField.TECHNOLOGY, values=("Python",), basis="technology_token")],
        )
        output = render_result(result, {"shape": "count"})
        for token in ("SELECT", "FROM", "clean_jobs", "ILIKE", "count(*)"):
            assert token not in output, token

    def test_the_rendering_never_names_a_hidden_column(self) -> None:
        result = answered(
            shape=QueryShape.DETAIL,
            rows=[{"id": 1, "title": "x", "company": "y"}],
            applied=[],
        )
        output = render_result(result, {"shape": "detail"})
        for column in ("source_url", "is_active", "first_seen_at", "last_seen_at", "external_id", "posted_date"):
            assert column not in output, column


class TestTheToolIsPairedWithThePrompt:
    """The v0 tool and the v0 system prompt are one bundle, never two.

    Stage 3 asserted the tool was not registered anywhere yet. The cutover
    registers it, and what still has to hold is that the served surface and the
    prompt move together, so a new prompt never runs against the old tools.
    """

    def test_the_v0_bundle_registers_the_governed_tool_and_no_legacy_tool(self) -> None:
        import asyncio

        from src.agents.mcp.job_server import (
            GET_JOB_DETAILS_TOOL,
            QUERY_CLEAN_JOBS_TOOL,
            V0_QUERY_TOOL,
            create_job_mcp_server,
        )
        from tests.agents.v0_switch import agent_v0

        with agent_v0(True):
            tools = {tool.name for tool in asyncio.run(create_job_mcp_server()._list_tools())}
        assert V0_QUERY_TOOL in tools
        assert QUERY_CLEAN_JOBS_TOOL not in tools
        assert GET_JOB_DETAILS_TOOL not in tools

    def test_the_v1_bundle_registers_only_the_legacy_tools(self) -> None:
        import asyncio

        from src.agents.mcp.job_server import V0_QUERY_TOOL, create_job_mcp_server
        from tests.agents.v0_switch import agent_v0

        with agent_v0(False):
            tools = {tool.name for tool in asyncio.run(create_job_mcp_server()._list_tools())}
        assert V0_QUERY_TOOL not in tools

    def test_the_v0_core_imports_no_framework(self) -> None:
        # A domain service that reaches for FastAPI, LangChain, or tracing has
        # taken on a boundary it does not own.
        import src.services.query.planner as planner
        import src.services.query.compiler as compiler
        import src.services.query.service as service
        import src.services.query.execution as execution

        forbidden = ("fastapi", "langchain", "langfuse", "src.api", "src.agents")
        for module in (planner, compiler, service, execution, planner):
            for name in dir(module):
                candidate = getattr(module, name, None)
                text = getattr(candidate, "__module__", "") or ""
                assert not any(text.startswith(prefix) for prefix in forbidden), f"{module.__name__}.{name}"
                source_file = getattr(candidate, "__file__", None)
                if source_file:
                    with open(source_file, encoding="utf-8") as handle:
                        head = handle.read(4000)
                    assert "import fastapi" not in head, f"{module.__name__}.{name}"
