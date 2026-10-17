"""The credential-free SQL guard gate: the successor to the v0 acceptance gate.

The v0 gate graded a deterministic function: the typed core's plan and result.
The v1 path has no such function - the model writes the SQL - so this gate grades
what the guard itself decides. Each case carries a question, the reviewed SQL a
correct answer must be equivalent to on the pinned fixture, the reviewed
obligation set, and (where a mode can express it) the reviewed result. The gate
runs the reviewed SQL through the same pipeline the tool uses - ``validate_sql``
→ ``resolve_bounds`` → the fixture - and fails when:

- the validator verdict differs from the reviewed one, or a rejected case is
  rejected by a different rule than the one the case pins (the guard's floor:
  self-join, ``pg_sleep``, multi-table references, hidden columns);
- the obligation set the guard emits differs from the reviewed set, which is how
  the false-success class is graded: R05's reviewed set is non-empty, so the
  case fails until the cross-currency rule matches aggregates;
- the reviewed result is not what the reviewed SQL returns on the pinned
  fixture (compared with ``evals/sql_check.py``).

Accepted risks are cases too. The guard is lexical and cannot see a silent
definition (A01, A02) or a bare cross-currency threshold (A03); those cases pin
today's behaviour and name the risk, so a change that starts refusing them turns
the gate red and the risk table has to be updated rather than forgotten. They
are deliberately not blessed with a reviewed result.

Two things this module does **not** do, for the same reasons the v0 gate did
not: it never skips (an unreachable fixture raises, because an unavailable
database is a failed gate and never a pass), and it never asks a model (nothing
here reads a credential or traffic).

The obligation set graded here is the detector's output. Which detected caveats
are rendered is ``agent.query.obligations`` in ``config/settings.yaml``; the
gate pins the detection, and the config gate is covered by the unit suite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from evals._paths import EVALS_ROOT
from evals.report import group_by_metric

GUARD_METRIC = "guard_correctness"
OBLIGATION_METRIC = "obligation_correctness"
RESULT_METRIC = "result_equivalence"

SQL_GUARD_DATASET = EVALS_ROOT / "datasets" / "sql_guard.yaml"

CLASSES = frozenset({"reviewed", "hidden", "cost", "ambiguous", "injection"})
#: A reviewed or accepted-risk case must run; a hidden or cost case must not.
REJECTED_CLASSES = frozenset({"hidden", "cost"})
RESULT_MODES = frozenset({"ids_only", "aggregate_count", "zero_results", "rows_equal"})

_CASE_KEYS = frozenset(
    {
        "id",
        "class",
        "question",
        "reviewed_sql",
        "guard",
        "expected_obligations",
        "expected_reason_contains",
        "result",
        "risk",
        "note",
    }
)
_RESULT_KEYS = frozenset({"mode", "reference_sql", "expected_count", "display_limit"})

PASS = 1.0
FAIL = 0.0


class GateUnavailable(RuntimeError):
    """The gate could not run, which is a failed gate and never a pass."""


def _fail(field: str) -> ValueError:
    return ValueError(f"SQL guard case {field} is invalid")


class SqlGuardDataset:
    """The reviewed SQL guard cases, with the grammar this gate grades."""

    def __init__(self, path: Path = SQL_GUARD_DATASET) -> None:
        self.path = path

    def cases(self) -> list[dict[str, Any]]:
        payload = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
            raise _fail(f"{self.path}: the file must be a mapping with a `cases` list")

        seen: set[str] = set()
        for case in payload["cases"]:
            self._validate(case)
            if case["id"] in seen:
                raise _fail(f"{case['id']} is duplicated")
            seen.add(case["id"])
        return payload["cases"]

    def _validate(self, case: dict[str, Any]) -> None:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"]:
            raise _fail("every case needs a non-empty string id")
        sid = case["id"]

        unknown = set(case) - _CASE_KEYS
        if unknown:
            raise _fail(f"{sid} declares unread keys {sorted(unknown)}; expected one of {sorted(_CASE_KEYS)}")
        if case.get("class") not in CLASSES:
            raise _fail(f"{sid} has an unknown class {case.get('class')!r}")
        for field in ("question", "reviewed_sql"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise _fail(f"{sid} needs a non-empty {field}")

        guard = case.get("guard")
        if guard not in {"valid", "rejected"}:
            raise _fail(f"{sid} needs a guard verdict of `valid` or `rejected`")
        expected_rejected = case["class"] in REJECTED_CLASSES
        if (guard == "rejected") != expected_rejected:
            raise _fail(
                f"{sid} is classed {case['class']} but declares guard {guard!r}; "
                f"a {case['class']} case must be {'rejected' if expected_rejected else 'valid'}"
            )

        if guard == "rejected":
            reason = case.get("expected_reason_contains")
            if not isinstance(reason, str) or not reason.strip():
                raise _fail(f"{sid} is rejected and must pin the rule in expected_reason_contains")
            for forbidden in ("expected_obligations", "result"):
                if case.get(forbidden) is not None:
                    raise _fail(f"{sid} is rejected, so {forbidden} cannot be graded")
            return

        obligations = case.get("expected_obligations")
        if not isinstance(obligations, list) or not all(isinstance(token, str) for token in obligations):
            raise _fail(f"{sid} must declare its reviewed obligation set as a list of tokens")
        if case["class"] == "ambiguous" and not case.get("risk"):
            raise _fail(f"{sid} is an accepted risk and must name it in `risk`")
        result = case.get("result")
        if result is not None:
            self._validate_result(sid, result)

    def _validate_result(self, sid: str, result: dict[str, Any]) -> None:
        if not isinstance(result, dict):
            raise _fail(f"{sid} has a result that is not a mapping")
        unknown = set(result) - _RESULT_KEYS
        if unknown:
            raise _fail(
                f"{sid} declares unread result keys {sorted(unknown)}; "
                f"expected one of {sorted(_RESULT_KEYS)}"
            )
        if result.get("mode") not in RESULT_MODES:
            raise _fail(f"{sid} has an unknown result mode {result.get('mode')!r}")
        if not isinstance(result.get("reference_sql"), str) or not result["reference_sql"].strip():
            raise _fail(f"{sid} needs a reference_sql to compare its reviewed result against")
        expected_count = result.get("expected_count")
        if expected_count is not None and (
            isinstance(expected_count, bool) or not isinstance(expected_count, int) or expected_count < 0
        ):
            raise _fail(f"{sid} has a non-negative-integer expected_count rule")
        if expected_count is not None and result["mode"] != "aggregate_count":
            # The comparison ignores it elsewhere, so declaring it would be an
            # expectation the gate silently drops.
            raise _fail(f"{sid} declares expected_count outside aggregate_count mode")
        display_limit = result.get("display_limit")
        if display_limit is not None and (
            isinstance(display_limit, bool) or not isinstance(display_limit, int) or display_limit <= 0
        ):
            raise _fail(f"{sid} has a positive-integer display_limit rule")
        if display_limit is not None and result["mode"] != "ids_only":
            raise _fail(f"{sid} declares display_limit outside ids_only mode")


def _bind_environment() -> None:
    from evals.env import bind_fixture_environment

    bind_fixture_environment()  # must happen before any src import


def _require_fixture() -> None:
    from evals.fixtures.loader import fixture_database_endpoint, fixture_database_reachable

    if not fixture_database_reachable():
        host, port = fixture_database_endpoint()
        raise GateUnavailable(
            f"the evaluation fixture is not reachable at {host}:{port}; start it with "
            "`docker compose up -d postgres` and load it with `uv run python -m evals.fixtures.loader`. "
            "An unreachable database is a failed gate, not a pass."
        )


def _max_rows() -> int:
    from src.core.config import settings

    query = settings.config_yaml.get("agent", {}).get("query")
    value = query.get("max_rows") if isinstance(query, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("agent.query.max_rows must be a positive integer in config/settings.yaml")
    return value


def _grade_guard(case: dict[str, Any], verdict: Any) -> tuple[float, str]:
    if case["guard"] == "valid":
        if not verdict.valid:
            return FAIL, f"the reviewed SQL was rejected: {verdict.reason}"
        return PASS, "the reviewed SQL is accepted, as reviewed"
    if verdict.valid:
        return FAIL, "the reviewed SQL was not rejected"
    expected = case["expected_reason_contains"]
    if expected not in verdict.reason:
        return FAIL, f"rejected by {verdict.reason!r}, not by the reviewed rule {expected!r}"
    return PASS, f"rejected by the reviewed rule: {verdict.reason}"


def _grade_obligations(case: dict[str, Any]) -> tuple[float, str]:
    from evals.sql_check import execute_query
    from src.services.query.obligations import detect_obligations
    from src.services.query.row_bound import resolve_bounds
    from src.services.query.table_formatter import format_rows

    bounds = resolve_bounds(case["reviewed_sql"], _max_rows())
    table = format_rows(execute_query(bounds.sql), bounds.display_cap)
    observed = {obligation.glossary_token for obligation in detect_obligations(case["reviewed_sql"], table)}
    expected = set(case["expected_obligations"])
    if observed != expected:
        return FAIL, f"obligations {sorted(observed)} are not the reviewed {sorted(expected)}"
    return PASS, f"the reviewed obligation set is emitted: {sorted(expected)}"


def _grade_result(case: dict[str, Any]) -> tuple[float, str]:
    from evals.sql_check import compare_result_sets

    result = case["result"]
    try:
        comparison = compare_result_sets(
            case["reviewed_sql"],
            result["reference_sql"],
            mode=result["mode"],
            expected_count=result.get("expected_count"),
            display_limit=result.get("display_limit"),
        )
    except ValueError as exc:
        return FAIL, f"the reviewed result cannot be compared: {exc}"

    if comparison["status"] == "PASS":
        return PASS, "the reviewed result is what the reviewed SQL returns"
    if comparison["status"] == "INFRA":
        return FAIL, f"the comparison could not run: {comparison['error']}"
    detail = comparison.get("reason")
    if detail is None:
        detail = (
            f"missing ids {comparison.get('missing_ids')} / "
            f"unexpected ids {comparison.get('unexpected_ids')}"
        )
    return FAIL, f"the result is not the reviewed one: {detail}"


def _row(case: dict[str, Any], metric: str, score: float, reason: str) -> dict[str, Any]:
    return {
        "scenario_id": case["id"],
        "metric": metric,
        "score": score,
        "reason": reason,
        "class": case["class"],
    }


def run_sql_gate(spec: SqlGuardDataset, *, ids: list[str] | None = None) -> dict[str, Any]:
    """Run every selected case against the pinned fixture and grade it.

    Raises :class:`GateUnavailable` when the run cannot happen, so an absent
    database is a failed gate rather than a quiet pass.
    """
    _bind_environment()
    from src.services.query.sql_validator import validate_sql

    _require_fixture()
    cases = spec.cases()
    if ids:
        wanted = set(ids)
        cases = [case for case in cases if case["id"] in wanted]
        missing = wanted - {case["id"] for case in cases}
        if missing:
            raise ValueError(f"Unknown dataset ids: {sorted(missing)}")

    results: list[dict[str, Any]] = []
    for case in cases:
        verdict = validate_sql(case["reviewed_sql"])
        guard_score, guard_reason = _grade_guard(case, verdict)
        results.append(_row(case, GUARD_METRIC, guard_score, guard_reason))

        if guard_score != PASS:
            # Nothing below is gradable: the reviewed SQL is not the statement
            # this case reviewed, so its obligations and result cannot be.
            if case["guard"] == "valid":
                not_graded = "not graded: the guard verdict is not the reviewed one"
                results.append(_row(case, OBLIGATION_METRIC, FAIL, not_graded))
                if case.get("result") is not None:
                    results.append(_row(case, RESULT_METRIC, FAIL, not_graded))
            continue

        if case["guard"] == "rejected":
            continue

        obligation_score, obligation_reason = _grade_obligations(case)
        results.append(_row(case, OBLIGATION_METRIC, obligation_score, obligation_reason))

        if case.get("result") is not None:
            result_score, result_reason = _grade_result(case)
            results.append(_row(case, RESULT_METRIC, result_score, result_reason))

    return {
        "dataset": str(spec.path),
        "mode": "gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": [GUARD_METRIC, OBLIGATION_METRIC, RESULT_METRIC],
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
