"""Pure tests for the governed query core: no database, no agent, no provider.

The three layers are tested separately because each owns a different promise:

- The vocabulary resolves a user term to a stored value and refuses to guess.
- The planner refuses a request that v0 cannot serve, before any SQL exists.
- The compiler emits parameterized statements from an allowlist, and the
  emitted SQL is asserted structurally: bound values, visible columns only, and
  the full matching total computed before any display limit.
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from src.services.query import vocabulary
from src.services.query.compiler import (
    ALLOWED_FUNCTIONS,
    LIST_PROJECTION,
    VISIBLE_COLUMNS,
    compile_plan,
)
from src.services.query.plan import (
    JobQueryRequest,
    QueryRequestError,
    QueryShape,
    UnsupportedQueryError,
    query_limits,
)
from src.services.query.planner import build_plan
from src.services.query.results import QueryResult, QueryState

HIDDEN_COLUMNS = frozenset(
    {"source", "external_id", "posted_date", "is_active", "first_seen_at", "last_seen_at"}
)


def compiled(**kwargs):
    request = JobQueryRequest(**kwargs)
    return compile_plan(build_plan(request), query_limits())


def all_sql(query) -> str:
    return "\n".join(statement.sql for statement in query.statements)


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class TestVocabulary:
    def test_city_aliases_cover_both_spellings(self) -> None:
        for term in ("Hà Nội", "ha noi", "HANOI", "Hanoi"):
            assert vocabulary.normalize_city(term) == "Hanoi"

    def test_city_synonyms_from_the_query_config(self) -> None:
        for term in ("Saigon", "sài gòn", "Sai Gon", "sg", "tp hcm"):
            assert vocabulary.normalize_city(term) == "Ho Chi Minh City"

    def test_unknown_city_is_not_guessed(self) -> None:
        assert vocabulary.normalize_city("Đà Lạt") is None
        assert vocabulary.normalize_city("") is None

    def test_canonical_cities_are_sorted_and_deduplicated(self) -> None:
        cities = vocabulary.canonical_cities()
        assert cities == sorted(set(cities))
        assert "Ho Chi Minh City" in cities

    def test_role_aliases_include_vietnamese_phrases(self) -> None:
        assert vocabulary.normalize_role("AI Engineer") == "AI Engineer"
        assert vocabulary.normalize_role("kỹ sư ai") == "AI Engineer"
        assert vocabulary.normalize_role("phân tích dữ liệu") == "Data Analyst"
        assert vocabulary.normalize_role("thực tập") is None

    def test_technology_expansion_uses_the_extraction_vocabulary(self) -> None:
        assert vocabulary.expand_technology("ML") == "Machine Learning"
        assert vocabulary.expand_technology("nlp") == "Natural Language Processing"
        assert vocabulary.expand_technology("LLM") == "Large Language Models"
        assert vocabulary.expand_technology("Python") == "Python"

    def test_unknown_technology_is_kept_verbatim_not_dropped(self) -> None:
        # An absent vocabulary entry is not evidence the technology is absent.
        assert vocabulary.expand_technology("Befunge") == "Befunge"
        assert vocabulary.expand_technology("  Befunge  ") == "Befunge"
        assert vocabulary.expand_technology("") is None

    def test_a_known_term_resolves_even_with_odd_casing(self) -> None:
        assert vocabulary.expand_technology("zIg") == "zig"
        assert vocabulary.expand_technology("python") == "Python"

    def test_denylisted_terms_never_expand(self) -> None:
        for term in ("Data Analyst", "Teamwork", "Problem Solving"):
            assert vocabulary.expand_technology(term) not in vocabulary.technology_aliases().values()


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class TestRequestModel:
    def test_unknown_field_is_rejected_by_the_allowlist(self) -> None:
        with pytest.raises(ValidationError):
            JobQueryRequest(shape="count", filters=[{"field": "is_active", "values": [True]}])

    def test_unknown_shape_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JobQueryRequest(shape="sql")

    def test_shape_requires_its_own_field(self) -> None:
        with pytest.raises(ValidationError, match="group_by"):
            JobQueryRequest(shape="group_count")
        with pytest.raises(ValidationError, match="top"):
            JobQueryRequest(shape="top_n")
        with pytest.raises(ValidationError, match="metric"):
            JobQueryRequest(shape="aggregate")
        with pytest.raises(ValidationError, match="compare"):
            JobQueryRequest(shape="compare")
        with pytest.raises(ValidationError, match="ids"):
            JobQueryRequest(shape="detail")

    def test_ids_only_belong_to_detail(self) -> None:
        with pytest.raises(ValidationError, match="ids belong to"):
            JobQueryRequest(shape="list", ids=[1])

    def test_ids_are_sorted_and_deduplicated(self) -> None:
        assert JobQueryRequest(shape="detail", ids=[3, 1, 3]).ids == [1, 3]

    def test_a_null_filter_value_is_not_expressible(self) -> None:
        with pytest.raises(ValidationError):
            JobQueryRequest(shape="count", filters=[{"field": "company", "values": [None]}])

    def test_share_needs_a_field_and_a_value(self) -> None:
        with pytest.raises(ValidationError, match="share"):
            JobQueryRequest(shape="aggregate", metric="share")
        with pytest.raises(ValidationError, match="free text"):
            JobQueryRequest(
                shape="aggregate", metric="share", share={"field": "free_text", "values": ["x"]}
            )

    def test_there_is_no_negation_filter(self) -> None:
        # Not a runtime check: the model has no way to ask for one.
        fields = set(JobQueryRequest.model_fields["filters"].annotation.__args__[0].model_fields["field"].annotation)
        assert "not" not in fields
        assert "exclude" not in fields
        assert "has_salary" not in fields


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class TestPlanner:
    def test_budget_rejects_too_many_filters(self) -> None:
        filters = [{"field": "company", "values": [f"c{i}"]} for i in range(9)]
        with pytest.raises(QueryRequestError, match="at most"):
            build_plan(JobQueryRequest(shape="count", filters=filters))

    def test_budget_rejects_too_many_values(self) -> None:
        with pytest.raises(QueryRequestError, match="at most"):
            build_plan(
                JobQueryRequest(shape="count", filters=[{"field": "company", "values": [f"c{i}" for i in range(9)]}])
            )

    def test_budget_rejects_an_oversized_top_n(self) -> None:
        with pytest.raises(QueryRequestError, match="at most"):
            build_plan(JobQueryRequest(shape="top_n", top={"n": 99, "order_by": "salary_min"}))

    def test_budget_rejects_too_many_detail_ids(self) -> None:
        with pytest.raises(QueryRequestError, match="at most"):
            build_plan(JobQueryRequest(shape="detail", ids=list(range(1, 30))))

    def test_repeating_a_field_asks_for_a_merge_not_a_second_filter(self) -> None:
        with pytest.raises(QueryRequestError, match="repeats field"):
            build_plan(
                JobQueryRequest(
                    shape="count",
                    filters=[{"field": "role", "values": ["AI Engineer"]}, {"field": "role", "values": ["ML Engineer"]}],
                )
            )

    def test_all_mode_is_technology_only(self) -> None:
        with pytest.raises(QueryRequestError, match="only combine values"):
            build_plan(
                JobQueryRequest(
                    shape="count",
                    filters=[{"field": "role", "values": ["AI Engineer", "ML Engineer"], "mode": "all"}],
                )
            )
        plan = build_plan(
            JobQueryRequest(
                shape="count",
                filters=[{"field": "technology", "values": ["Python", "PyTorch"], "mode": "all"}],
            )
        )
        assert plan.filters[0].mode.value == "all"

    def test_unknown_city_is_unsupported_not_empty(self) -> None:
        with pytest.raises(UnsupportedQueryError, match="not a city this data holds"):
            build_plan(JobQueryRequest(shape="count", filters=[{"field": "location", "values": ["Đà Lạt"]}]))

    def test_unknown_role_becomes_a_disclosed_free_text_fallback(self) -> None:
        plan = build_plan(
            JobQueryRequest(shape="list", filters=[{"field": "role", "values": ["Rustacean"]}])
        )
        assert plan.filters[0].basis == "fallback"
        assert plan.filters[0].field.value == "free_text"
        # The caveat has one owner, the service, so the plan carries none. Two
        # owners would print the same line twice.
        assert "ROLE_FALLBACK" not in plan.caveats
        service = service_with({"rows": []})
        result = service.answer(
            JobQueryRequest(shape="list", filters=[{"field": "role", "values": ["Rustacean"]}])
        )
        assert result.caveats.count("ROLE_FALLBACK") == 1

    def test_technology_is_expanded_before_matching(self) -> None:
        plan = build_plan(JobQueryRequest(shape="count", filters=[{"field": "technology", "values": ["ML"]}]))
        assert plan.filters[0].values == ("Machine Learning",)
        assert plan.filters[0].basis == "technology_token"

    def test_share_on_a_field_the_base_restricts_is_refused(self) -> None:
        with pytest.raises(QueryRequestError, match="always be 100 percent"):
            build_plan(
                JobQueryRequest(
                    shape="aggregate",
                    metric="share",
                    filters=[{"field": "role", "values": ["AI Engineer"]}],
                    share={"field": "role", "values": ["AI Engineer"]},
                )
            )

    def test_a_share_may_be_measured_over_a_two_value_field(self) -> None:
        for field, value in (("has_link", True), ("is_internship", True)):
            plan = build_plan(
                JobQueryRequest(
                    shape="aggregate", metric="share", share={"field": field, "values": [value]}
                )
            )
            assert plan.share is not None
            assert plan.share.field.value == field
            assert plan.share.values == (value,)

    def test_share_on_a_threshold_is_refused(self) -> None:
        with pytest.raises(QueryRequestError, match="cannot carry a share"):
            build_plan(
                JobQueryRequest(
                    shape="aggregate",
                    metric="share",
                    share={"field": "salary_min", "values": [1000]},
                )
            )

    def test_salary_comparison_and_share_comparison_are_refused(self) -> None:
        sides = [{"filters": []}, {"filters": []}]
        for metric in ("average_salary", "median_salary", "share"):
            with pytest.raises(QueryRequestError):
                compiled(shape="compare", metric=metric, compare=sides)

    def test_grouping_by_technology_is_refused(self) -> None:
        with pytest.raises(QueryRequestError, match="not a single column"):
            compiled(shape="group_count", group_by="technology")


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


class TestCompiledSql:
    def test_every_statement_reads_one_allowlisted_table(self) -> None:
        query = compiled(shape="list", filters=[{"field": "role", "values": ["AI Engineer"]}])
        for statement in query.statements:
            tables = re.findall(r"\bfrom\s+([a-z_]+)", statement.sql, re.IGNORECASE)
            assert tables == ["clean_jobs"]

    def test_no_statement_can_mention_a_hidden_column(self) -> None:
        queries = [
            compiled(shape="list"),
            compiled(shape="count"),
            compiled(shape="group_count", group_by="job_level"),
            compiled(shape="top_n", top={"n": 3, "order_by": "created_on"}),
            compiled(shape="aggregate", metric="average_salary"),
            compiled(shape="aggregate", metric="share", share={"field": "technology", "values": ["Python"]}),
            compiled(shape="compare", compare=[{"filters": []}, {"filters": []}]),
            compiled(shape="detail", ids=[1]),
        ]
        for query in queries:
            sql = all_sql(query)
            for column in HIDDEN_COLUMNS:
                assert not re.search(rf"\b{column}\b", sql), column

    def test_every_projected_column_is_agent_visible(self) -> None:
        for column in LIST_PROJECTION:
            assert column in VISIBLE_COLUMNS
        assert len(VISIBLE_COLUMNS) == 16

    def test_only_allowlisted_functions_are_emitted(self) -> None:
        queries = [
            compiled(shape="count"),
            compiled(shape="aggregate", metric="average_salary"),
            compiled(shape="aggregate", metric="median_salary"),
            compiled(shape="list", filters=[{"field": "technology", "values": ["Python"]}]),
        ]
        for query in queries:
            called = {
                name.casefold()
                for name in re.findall(r"\b([a-z_]+)\s*\(", all_sql(query))
                if name.casefold() not in {"select", "coalesce"}
            }
            assert called <= ALLOWED_FUNCTIONS, called

    def test_user_values_are_bound_never_interpolated(self) -> None:
        query = compiled(
            shape="count",
            filters=[{"field": "company", "values": ["Robert'); DROP TABLE clean_jobs; --"]}],
        )
        sql = all_sql(query)
        assert "DROP" not in sql.upper()
        assert "Robert" not in sql
        assert any(
            "DROP TABLE" in str(value) for value in query.statements[0].params.values()
        ), "the value must still be delivered, as a bound parameter"

    def test_free_text_wildcards_the_user_typed_are_escaped(self) -> None:
        query = compiled(shape="count", filters=[{"field": "free_text", "values": ["100%_off"]}])
        assert query.statements[0].params["f0_0"] == "%100\\%\\_off%"

    def test_technology_matches_a_whole_token(self) -> None:
        query = compiled(shape="count", filters=[{"field": "technology", "values": ["ML"]}])
        sql = all_sql(query)
        assert "btrim(tech) = :t0_0" in sql
        assert "ilike" not in sql.casefold()
        assert query.statements[0].params["t0_0"] == "Machine Learning"

    def test_multi_technology_any_and_all_differ_in_the_joiner(self) -> None:
        values = ["Python", "PyTorch"]
        any_sql = all_sql(compiled(shape="count", filters=[{"field": "technology", "values": values}]))
        all_sql_form = all_sql(
            compiled(shape="count", filters=[{"field": "technology", "values": values, "mode": "all"}])
        )
        assert " OR " in any_sql
        assert " AND " in all_sql_form
        assert " AND " not in any_sql

    def test_list_carries_the_full_total_before_the_display_limit(self) -> None:
        query = compiled(shape="list")
        sql = query.statements[0].sql
        assert "count(*) OVER () AS match_total" in sql
        assert sql.index("count(*) OVER ()") < sql.index("LIMIT")
        assert query.statements[0].params["display_cap"] == query.display_cap + 1

    def test_count_is_never_bounded_by_the_display_cap(self) -> None:
        query = compiled(shape="count")
        assert "LIMIT" not in all_sql(query).upper()
        assert query.display_cap == 0

    def test_share_computes_numerator_denominator_and_exclusions_together(self) -> None:
        query = compiled(
            shape="aggregate",
            metric="share",
            filters=[{"field": "role", "values": ["AI Engineer"]}],
            share={"field": "technology", "values": ["Python"]},
        )
        sql = query.statements[0].sql
        assert "count(*) AS denominator" in sql
        assert "AS numerator" in sql
        assert "AS excluded_null_field" in sql
        assert "FILTER (WHERE tech_stack" not in sql  # technology nullness is its own test

    def test_salary_aggregate_groups_by_currency_when_none_is_named(self) -> None:
        sql = all_sql(compiled(shape="aggregate", metric="average_salary"))
        assert "GROUP BY 1" in sql
        assert "salary_currency = :currency" not in sql

    def test_salary_aggregate_pins_the_currency_when_the_request_names_one(self) -> None:
        query = compiled(
            shape="aggregate",
            metric="average_salary",
            filters=[{"field": "salary_currency", "values": ["USD"]}],
        )
        assert "GROUP BY 1" not in all_sql(query)
        assert query.salary_currency == "USD"
        assert "salary_currency = :currency" in all_sql(query)

    def test_median_uses_percentile_not_a_guessed_middle(self) -> None:
        sql = all_sql(compiled(shape="aggregate", metric="median_salary"))
        assert "percentile_cont(0.5) WITHIN GROUP (ORDER BY salary_min)" in sql

    def test_top_n_orders_by_one_allowlisted_column_and_reports_skipped_rows(self) -> None:
        query = compiled(shape="top_n", top={"n": 3, "order_by": "created_on"})
        sql = all_sql(query)
        assert "ORDER BY created_on DESC NULLS LAST, id ASC" in sql
        assert "AS skipped" in sql
        assert query.statements[0].params["top_n"] == 3

    def test_top_n_ranking_is_reproducible_for_a_tie(self) -> None:
        sql = all_sql(compiled(shape="top_n", top={"n": 2, "order_by": "salary_min"}))
        assert sql.count("id ASC") == 1

    def test_a_statement_without_a_where_clause_stays_valid(self) -> None:
        # An empty base plus an added condition used to emit "FROM clean_jobs AND ..."
        for kwargs in (
            {"shape": "top_n", "top": {"n": 2, "order_by": "created_on"}},
            {"shape": "aggregate", "metric": "average_salary"},
        ):
            sql = all_sql(compiled(**kwargs))
            assert "clean_jobs AND" not in sql
            assert " WHERE " in sql

    def test_group_count_keeps_a_null_value_as_its_own_group(self) -> None:
        sql = all_sql(compiled(shape="group_count", group_by="location"))
        assert "COALESCE(location, '(not recorded)')" in sql

    def test_no_statement_is_a_write(self) -> None:
        for kwargs in (
            {"shape": "list"},
            {"shape": "count"},
            {"shape": "aggregate", "metric": "average_salary"},
            {"shape": "detail", "ids": [1]},
        ):
            sql = all_sql(compiled(**kwargs)).upper()
            for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "CREATE", "GRANT"):
                assert not re.search(rf"\b{verb}\b", sql), verb
            assert sql.startswith("SELECT")

    def test_limit_is_always_a_bound_parameter(self) -> None:
        for query in (
            compiled(shape="list"),
            compiled(shape="group_count", group_by="location"),
            compiled(shape="top_n", top={"n": 3, "order_by": "salary_min"}),
        ):
            for statement in query.statements:
                for match in re.findall(r"LIMIT\s+(\S+)", statement.sql, re.IGNORECASE):
                    assert match.startswith(":"), match
                    assert match.lstrip(":") in statement.params


# ---------------------------------------------------------------------------
# Service result assembly, with a stub executor
# ---------------------------------------------------------------------------


class StubExecutor:
    """Returns canned rows per statement role, so assembly is tested alone."""

    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows
        self.calls: list = []

    def run(self, compiled_query):
        self.calls.append(compiled_query)
        return self.rows


def service_with(rows: dict[str, list[dict]]):
    from src.services.query.service import JobQueryService

    return JobQueryService(executor=StubExecutor(rows))


class TestServiceAssembly:
    def test_a_list_reports_the_total_not_the_displayed_rows(self) -> None:
        service = service_with(
            {"rows": [{"id": 1, "title": "a", "match_total": 23}]}
        )
        result = service.answer(JobQueryRequest(shape="list"))
        assert result.state is QueryState.ANSWERED
        assert result.match_total == 23
        assert result.displayed_count == 1
        assert result.truncated is True
        assert "TRUNCATION" in result.caveats
        assert "match_total" not in result.rows[0]

    def test_an_empty_result_is_a_data_state_not_an_error(self) -> None:
        service = service_with({"rows": []})
        result = service.answer(JobQueryRequest(shape="list"))
        assert result.state is QueryState.EMPTY
        assert result.match_total == 0

    def test_a_share_keeps_its_denominator_and_exclusions(self) -> None:
        service = service_with(
            {"share": [{"denominator": 5, "numerator": 5, "excluded_null_field": 0}]}
        )
        result = service.answer(
            JobQueryRequest(
                shape="aggregate",
                metric="share",
                filters=[{"field": "role", "values": ["AI Engineer"]}],
                share={"field": "technology", "values": ["Python"]},
            )
        )
        assert result.share is not None
        assert (result.share.numerator, result.share.denominator) == (5, 5)
        assert result.share.percent == 100.0
        assert "DENOMINATOR_STATED" in result.caveats

    def test_a_share_of_nothing_reports_no_percent(self) -> None:
        service = service_with({"share": [{"denominator": 0, "numerator": 0, "excluded_null_field": 0}]})
        result = service.answer(
            JobQueryRequest(
                shape="aggregate", metric="share", share={"field": "technology", "values": ["Rust"]}
            )
        )
        assert result.state is QueryState.EMPTY
        assert result.share is not None and result.share.percent is None

    def test_a_salary_figure_always_carries_the_period_and_currency_caveats(self) -> None:
        service = service_with(
            {
                "aggregate": [
                    {"currency": "USD", "rows": 1, "with_salary_min": 1, "value": 2500.0}
                ],
                "excluded": [{"excluded": 1}],
            }
        )
        result = service.answer(JobQueryRequest(shape="aggregate", metric="average_salary"))
        assert result.aggregate[0].currency == "USD"
        assert result.aggregate[0].excluded_no_salary == 1
        assert {"CURRENCY_SCOPED", "PERIOD_UNKNOWN", "DENOMINATOR_STATED"} <= set(result.caveats)

    def test_a_comparison_reports_each_side(self) -> None:
        service = service_with({"side0": [{"count": 7}], "side1": [{"count": 3}]})
        result = service.answer(
            JobQueryRequest(
                shape="compare",
                compare=[
                    {"filters": [{"field": "location", "values": ["Hanoi"]}]},
                    {"filters": [{"field": "location", "values": ["Ho Chi Minh City"]}]},
                ],
            )
        )
        assert result.compare_sides == [7, 3]
        assert [c.side for c in result.applied] == [0, 1]

    def test_an_execution_failure_is_an_error_state_not_a_traceback(self) -> None:
        from src.services.query.execution import QueryExecutionError

        class Failing:
            def run(self, compiled_query):
                raise QueryExecutionError("The database could not answer that question.")

        from src.services.query.service import JobQueryService

        result = JobQueryService(executor=Failing()).answer(JobQueryRequest(shape="count"))
        assert result.state is QueryState.ERROR
        assert "could not answer" in (result.message or "")

    def test_a_malformed_request_never_reaches_the_executor(self) -> None:
        executor = StubExecutor({"rows": []})
        from src.services.query.service import JobQueryService

        result = JobQueryService(executor=executor).answer(
            JobQueryRequest(shape="count", filters=[{"field": "location", "values": ["Đà Lạt"]}])
        )
        assert result.state is QueryState.UNSUPPORTED
        assert executor.calls == []

    def test_any_applied_filter_attaches_the_match_basis(self) -> None:
        service = service_with({"rows": [{"id": 1, "match_total": 1}]})
        result = service.answer(
            JobQueryRequest(shape="list", filters=[{"field": "location", "values": ["Hanoi"]}])
        )
        assert "MATCH_BASIS" in result.caveats

    def test_no_filter_means_no_match_basis(self) -> None:
        service = service_with({"rows": [{"id": 1, "match_total": 1}]})
        result = service.answer(JobQueryRequest(shape="list"))
        assert "MATCH_BASIS" not in result.caveats

    def test_a_currency_filter_attaches_the_currency_scope(self) -> None:
        service = service_with(
            {
                "rows": [{"id": 1, "match_total": 1}],
                "skipped": [{"skipped": 0}],
            }
        )
        result = service.answer(
            JobQueryRequest(
                shape="top_n",
                top={"n": 1, "order_by": "salary_min"},
                filters=[{"field": "salary_currency", "values": ["USD"]}],
            )
        )
        assert "CURRENCY_SCOPED" in result.caveats

    def test_a_grouping_over_a_nullable_field_states_its_coverage(self) -> None:
        service = service_with({"groups": [{"value": "Manager", "n": 1}], "total": [{"count": 1}]})
        result = service.answer(JobQueryRequest(shape="group_count", group_by="job_level"))
        assert "COVERAGE_STATED" in result.caveats

    def test_a_caveat_is_never_repeated(self) -> None:
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
        assert len(result.caveats) == len(set(result.caveats))
        assert result.caveats.count("CURRENCY_SCOPED") == 1

    def test_every_result_state_is_reachable_through_answer(self) -> None:
        states = {
            QueryState.ANSWERED,
            QueryState.EMPTY,
            QueryState.UNSUPPORTED,
            QueryState.AMBIGUOUS,
            QueryState.ERROR,
        }
        assert states == set(QueryState)
        assert QueryResult(state=QueryState.ANSWERED, shape=QueryShape.LIST).is_data_answer
        assert not QueryResult(state=QueryState.ERROR, shape=QueryShape.LIST).is_data_answer


class TestSalaryThresholdIsNotASetMembership:
    """A `>=` bound is one number. Two bounds cannot both be the minimum.

    The compiler binds a single threshold parameter, so a plan carrying two values
    reported two applied criteria while one predicate ran, and the model was told
    about a filter that did not exist.
    """

    @staticmethod
    def plan_with(field: str, values: list):
        return JobQueryRequest.model_validate({"shape": "list", "filters": [{"field": field, "values": values}]})

    def test_two_salary_minimums_are_ambiguous_rather_than_silently_collapsed(self) -> None:
        from src.services.query.plan import AmbiguousQueryError

        with pytest.raises(AmbiguousQueryError) as caught:
            build_plan(self.plan_with("salary_min", [1000, 2000]))
        assert "salary_min" in caught.value.question

    def test_two_salary_maximums_are_ambiguous(self) -> None:
        from src.services.query.plan import AmbiguousQueryError

        with pytest.raises(AmbiguousQueryError):
            build_plan(self.plan_with("salary_max", [2000, 1000]))

    def test_a_single_bound_is_unchanged(self) -> None:
        assert build_plan(self.plan_with("salary_min", [1000])).filters[0].values == (1000.0,)

    def test_repeating_the_same_bound_is_not_ambiguity(self) -> None:
        """A model restating one number is not a second, conflicting number."""
        assert build_plan(self.plan_with("salary_min", [1000, 1000])).filters[0].values == (1000.0,)

    def test_ambiguity_surfaces_as_a_question_not_an_error_state(self) -> None:
        result = service_with({}).answer(self.plan_with("salary_min", [1000, 2000]))
        assert result.state is QueryState.AMBIGUOUS
        assert "salary_min" in result.message

    def test_the_applied_criterion_matches_the_bound_that_ran(self) -> None:
        """The reported criterion and the executed predicate must agree."""
        plan = build_plan(self.plan_with("salary_min", [1000]))
        compiled = compile_plan(plan, {"max_rows": 50, "group_cap": 20, "max_detail_ids": 10, "max_top_n": 5})
        statements = getattr(compiled, "statements", None) or [compiled]
        bound = {
            value
            for statement in statements
            for key, value in (getattr(statement, "params", None) or {}).items()
            if key.startswith("n")
        }
        assert bound == set(plan.filters[0].values)


class TestGroupTruncationIsDisclosed:
    """A total over a bounded group list must say the list was bounded.

    `match_total` counts matching postings, not groups, so it cannot detect a
    dropped group the way LIST and TOP_N detect a dropped row. Before this, a
    saturated group list rendered `TOTAL: 5000` above twenty groups with no
    caveat at all.
    """

    @staticmethod
    def group_rows(count: int, n: int = 3) -> list[dict]:
        return [{"value": f"g{index}", "n": n} for index in range(count)]

    def test_a_saturated_group_list_is_marked_truncated(self) -> None:
        result = service_with({"groups": self.group_rows(20), "total": [{"count": 5000}]}).answer(
            JobQueryRequest.model_validate({"shape": "group_count", "group_by": "location"})
        )
        assert result.truncated is True
        assert result.displayed_count == 20

    def test_a_saturated_group_list_states_the_caveat(self) -> None:
        result = service_with({"groups": self.group_rows(20), "total": [{"count": 5000}]}).answer(
            JobQueryRequest.model_validate({"shape": "group_count", "group_by": "location"})
        )
        assert "TRUNCATION" in result.caveats
        assert result.caveats.count("TRUNCATION") == 1

    def test_the_total_still_reports_the_full_matching_set(self) -> None:
        """Truncating the disclosure must not shrink the stated total."""
        result = service_with({"groups": self.group_rows(20), "total": [{"count": 5000}]}).answer(
            JobQueryRequest.model_validate({"shape": "group_count", "group_by": "location"})
        )
        assert result.match_total == 5000
        assert sum(g.count for g in result.groups) != result.match_total

    def test_an_unbounded_group_list_is_not_marked_truncated(self) -> None:
        result = service_with({"groups": self.group_rows(4), "total": [{"count": 12}]}).answer(
            JobQueryRequest.model_validate({"shape": "group_count", "group_by": "location"})
        )
        assert result.truncated is False
        assert "TRUNCATION" not in result.caveats

    def test_list_and_top_n_agree_on_the_caveat_name(self) -> None:
        """One disclosure vocabulary across shapes, or the model has to guess."""
        from src.agents.tools.v0_query_jobs import CAVEAT_TEXT
        from src.services.query.service import CAVEAT_TRUNCATION

        assert CAVEAT_TRUNCATION == "TRUNCATION"
        assert "TRUNCATION" in CAVEAT_TEXT
