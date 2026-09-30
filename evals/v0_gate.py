"""The credential-free v0 acceptance gate.

It calls the governed query core directly, so there is no capture, no serving
model, and no judge in the loop. A case fails when the plan the core applied
differs from the reviewed intent, or when its result differs from the golden, the
answer state, or the required evidence labels.

Two things this module deliberately does **not** do:

- **Skip.** If the fixture database is unreachable, the gate fails with a message
  naming what to start. A gate that turns an unavailable database into a green
  run is the failure mode this track was opened to remove, so an infrastructure
  problem is a failed gate, never a pass.
- **Ask a model.** Nothing here reads a credential, so the same command produces
  the same result on a laptop and in CI. The judge metrics are run deliberately
  by a maintainer, and are not part of this gate.

The three cases whose contract state is not an answer carry no request at all,
because no supported request expresses them. Their correctness claim is
structural: the gate proves the capability does not exist, by checking the
vocabulary the core actually exposes. A prose claim that the agent should refuse
is not testable; the absence of a field for it is.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.report import group_by_metric

PLAN_METRIC = "plan_correctness"
RESULT_METRIC = "result_equivalence"

# The contract has four answer states and the core reports five: a zero-result
# answer is `EMPTY` in the core and `ANSWERED` in the contract, because the
# contract asks what the answer may claim, not whether rows came back. The
# mapping is one-directional and only where a case reviewed no rows.
ANSWERED_AS_EMPTY = {"empty"}
ROW_RETURNING_SHAPES = {"S1 LIST", "S7 DETAIL"}

PASS = 1.0
FAIL = 0.0


class GateUnavailable(RuntimeError):
    """The gate could not run, which is a failed gate and never a pass."""


def _dataset_request(case: dict[str, Any]) -> dict[str, Any] | None:
    request = case.get("expected_request")
    if request is None:
        return None
    if not isinstance(request, dict):
        raise ValueError(f"Case {case['id']} has an expected_request that is not a mapping")
    return request


def _bind_environment() -> None:
    from evals.env import bind_fixture_environment

    bind_fixture_environment()  # must happen before any src import


def _core():
    """The governed query core, with every session bound to the fixture database."""
    from sqlalchemy import create_engine

    from evals.fixtures.loader import (
        fixture_database_endpoint,
        fixture_database_reachable,
        fixture_database_url,
    )
    from src.services.query.execution import BoundedExecutor
    from src.services.query.service import JobQueryService

    if not fixture_database_reachable():
        host, port = fixture_database_endpoint()
        raise GateUnavailable(
            f"the evaluation fixture is not reachable at {host}:{port}; start it with "
            "`docker compose up -d postgres` and load it with `uv run python -m evals.fixtures.loader`. "
            "An unreachable database is a failed gate, not a pass."
        )
    engine = create_engine(fixture_database_url())
    return engine, JobQueryService(executor=BoundedExecutor(session_factory=engine.connect))


def _resolve(criteria: list[Any]) -> list[tuple[str | None, str, tuple[Any, ...]]]:
    return [(c.side, c.field.value, tuple(c.values)) for c in criteria]


def _grade_plan(case: dict[str, Any], result: Any) -> tuple[float, str]:
    """The applied criteria must be the ones the case was reviewed against."""
    expected = [
        (f.get("side"), f["field"], tuple(f["values"])) for f in (case.get("expected_filters") or [])
    ]
    observed = _resolve(result.applied)
    if observed != expected:
        return FAIL, f"applied {observed} does not match the reviewed plan {expected}"
    shape = result.shape.value
    requested = _dataset_request(case)
    if requested and requested["shape"] != shape:
        return FAIL, f"shape {shape} does not match the requested {requested['shape']}"
    return PASS, "the applied plan is the reviewed plan"


def _grade_result(case: dict[str, Any], result: Any) -> tuple[float, str]:
    """Row ids, aggregates, the total, the state, and the labels must all agree."""
    problems: list[str] = []

    expected_state = case["contract_state"].lower()
    observed_state = result.state.value
    if case.get("expected_row_ids") == [] and expected_state == "answered":
        expected_states = {"answered"} | ANSWERED_AS_EMPTY
    else:
        expected_states = {expected_state}
    if observed_state not in expected_states:
        problems.append(f"state {observed_state} is not the reviewed {expected_state}")

    # A case that returns rows grades its rows. A case whose shape returns no rows
    # records the set it is about for the reviewer and grades its count instead.
    if case.get("contract_shape") in ROW_RETURNING_SHAPES and case.get("expected_row_ids") is not None:
        if case["expected_row_ids"] == [] and result.rows:
            problems.append(f"expected no rows, got {len(result.rows)}")
        elif case["expected_row_ids"] and [row.get("id") for row in result.rows] != case["expected_row_ids"]:
            observed = [row.get("id") for row in result.rows]
            problems.append(f"rows {observed} are not the reviewed {case['expected_row_ids']}")

    if "expected_match_count" in case and result.match_total != case["expected_match_count"]:
        problems.append(f"match total {result.match_total} is not the reviewed {case['expected_match_count']}")

    aggregates = case.get("expected_aggregates") or {}
    if "count" in aggregates and result.count != aggregates["count"]:
        problems.append(f"count {result.count} is not the reviewed {aggregates['count']}")
    if "groups" in aggregates:
        observed = {g.value: g.count for g in result.groups}
        if observed != aggregates["groups"]:
            problems.append(f"groups {observed} are not the reviewed {aggregates['groups']}")
    if "compare" in aggregates:
        observed = {str(value) for value in (result.compare_sides or [])}
        expected = {str(value) for value in aggregates["compare"].values()}
        if observed != expected:
            problems.append(f"comparison {observed} is not the reviewed {expected}")
    if "share_numerator" in aggregates and result.share is not None:
        if (
            result.share.numerator != aggregates["share_numerator"]
            or result.share.denominator != aggregates["share_denominator"]
            or result.share.excluded_null_field != aggregates["share_excluded_null_field"]
        ):
            problems.append(
                f"share {result.share.numerator}/{result.share.denominator} "
                f"with {result.share.excluded_null_field} excluded is not the reviewed "
                f"{aggregates['share_numerator']}/{aggregates['share_denominator']} "
                f"with {aggregates['share_excluded_null_field']} excluded"
            )
    if "expected_figures" in case and result.aggregate:
        observed = {a.currency: a.value for a in result.aggregate}
        if observed != case["expected_figures"]:
            problems.append(
                f"salary figures {observed} are not the reviewed {case['expected_figures']}"
            )
    if "excluded_no_salary" in case and result.aggregate:
        excluded = {a.excluded_no_salary for a in result.aggregate}
        if excluded != {case["expected_aggregates"]["excluded_no_salary"]}:
            problems.append(
                f"excluded {excluded} is not the reviewed {case['expected_aggregates']['excluded_no_salary']}"
            )
    if "total" in aggregates and result.match_total != aggregates["total"]:
        problems.append(f"total {result.match_total} is not the reviewed {aggregates['total']}")
    if "excluded_null_field" in aggregates and result.share is not None:
        if result.share.excluded_null_field != aggregates["excluded_null_field"]:
            problems.append(f"excluded {result.share.excluded_null_field} is not the reviewed {aggregates['excluded_null_field']}")

    for fragment in case.get("expected_description_contains") or []:
        if not any(fragment in str(row.get("description") or "") for row in result.rows):
            problems.append(f"no returned description contains {fragment!r}")

    missing = [label for label in (case.get("required_labels") or []) if label not in result.caveats]
    if missing:
        problems.append(f"missing evidence labels {missing}")

    return (FAIL, "; ".join(problems)) if problems else (PASS, "the result is the reviewed result")


def _grade_absent_capability(case: dict[str, Any]) -> tuple[float, str]:
    """The capability the contract refuses must not exist in the vocabulary.

    A refusal that rests on prose cannot be gated. These cases are gated on the
    absence of a field, a column, or a shape, which is a fact about the code.
    """
    from src.api.schema_guard import EXPECTED_COLUMNS
    from src.services.query.compiler import VISIBLE_COLUMNS
    from src.services.query.plan import FilterField, QueryShape

    visible = set(VISIBLE_COLUMNS)
    for claim in case.get("absent_capability") or []:
        kind, value = claim["kind"], claim["value"]
        if kind == "no_visible_column_matching":
            if [column for column in visible if value in column]:
                return FAIL, f"a visible column matches {value!r}"
        elif kind == "no_filter_field_matching":
            if [f.value for f in FilterField if value in f.value]:
                return FAIL, f"a filter field matches {value!r}"
        elif kind == "no_shape_matching":
            if [s.value for s in QueryShape if value in s.value]:
                return FAIL, f"a shape matches {value!r}"
        elif kind == "no_filter_field_named":
            if hasattr(FilterField, str(value).upper()):
                return FAIL, f"filter field {value} exists"
        elif kind == "no_column_in_schema":
            if value not in EXPECTED_COLUMNS:
                return FAIL, f"{value} is not even a column, so the claim is not what it says"
        else:
            return FAIL, f"unknown capability claim {kind!r}"
    return PASS, "the capability the contract refuses does not exist"


def run_v0_gate(spec, *, ids: list[str] | None = None) -> dict[str, Any]:
    """Run every selected case through the core and grade it.

    Raises :class:`GateUnavailable` when the run cannot happen, so an absent
    database is a failed gate rather than a quiet pass.
    """
    _bind_environment()
    from src.services.query.plan import JobQueryRequest

    engine, service = _core()
    cases = spec.scenarios()
    if ids:
        wanted = set(ids)
        cases = [case for case in cases if case["id"] in wanted]
        missing = wanted - {case["id"] for case in cases}
        if missing:
            raise ValueError(f"Unknown dataset ids: {sorted(missing)}")

    results: list[dict[str, Any]] = []
    try:
        for case in cases:
            request = _dataset_request(case)
            if request is None:
                plan_score, plan_reason = _grade_absent_capability(case)
                result_score, result_reason = _grade_absent_capability(case)
            else:
                answer = service.answer(JobQueryRequest(**request))
                plan_score, plan_reason = _grade_plan(case, answer)
                result_score, result_reason = _grade_result(case, answer)
            results.append(
                {
                    "scenario_id": case["id"],
                    "metric": PLAN_METRIC,
                    "score": plan_score,
                    "reason": plan_reason,
                    "contract_state": case["contract_state"],
                }
            )
            results.append(
                {
                    "scenario_id": case["id"],
                    "metric": RESULT_METRIC,
                    "score": result_score,
                    "reason": result_reason,
                    "contract_state": case["contract_state"],
                }
            )
    finally:
        engine.dispose()

    return {
        "dataset": str(spec.path),
        "mode": "deterministic",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": [PLAN_METRIC, RESULT_METRIC],
        "cases": [case["id"] for case in cases],
        "by_metric": group_by_metric(results),
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def failed_cases(report: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Every failing row as (scenario id, metric, reason)."""
    return [
        (row["scenario_id"], row["metric"], row["reason"])
        for rows in report["by_metric"].values()
        for row in rows
        if row["score"] != PASS
    ]
