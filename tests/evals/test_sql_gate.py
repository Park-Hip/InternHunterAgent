"""The SQL guard gate, and what it refuses to let pass.

A gate is only worth having if it fails when it should. Most of this module
exists to prove that: a wrong golden, a moved group count, a missing or invented
obligation, a floor case that stops being rejected, and a rejection by a
different rule each have to turn the gate red, and an unreachable database has
to be a failure rather than a quiet pass.
"""

from __future__ import annotations

import copy

import pytest
import yaml

from evals.sql_gate import (
    GUARD_METRIC,
    OBLIGATION_METRIC,
    RESULT_METRIC,
    GateUnavailable,
    SqlGuardDataset,
    failed_cases,
    run_sql_gate,
)

FALSE_SUCCESS_CASE = "R05-salary-by-currency"


def cases() -> list[dict]:
    return copy.deepcopy(SqlGuardDataset().cases())


def case_named(case_id: str) -> dict:
    return next(case for case in cases() if case["id"] == case_id)


def spec_for(doctored_cases: list[dict], tmp_path) -> SqlGuardDataset:
    path = tmp_path / "sql_guard_doctored.yaml"
    path.write_text(
        yaml.safe_dump({"cases": doctored_cases}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return SqlGuardDataset(path)


@pytest.fixture(scope="module")
def fixture_available() -> bool:
    from evals.fixtures.loader import fixture_database_reachable

    return fixture_database_reachable()


class TestDatasetShape:
    def test_every_case_class_is_covered(self) -> None:
        classes = {case["class"] for case in cases()}
        assert classes == {"reviewed", "hidden", "cost", "ambiguous", "injection"}

    def test_the_guard_floor_pins_a_rule_per_attack(self) -> None:
        reasons = {
            case["id"]: case.get("expected_reason_contains", "")
            for case in cases()
            if case["class"] in {"hidden", "cost"}
        }
        assert all(reasons.values()), reasons
        pinned = " ".join(reasons.values())
        assert "Hidden column" in pinned
        assert "Server-side function calls are not allowed" in pinned
        assert "may only reference the clean_jobs table" in pinned

    def test_the_false_success_case_reviews_a_non_empty_obligation_set(self) -> None:
        case = case_named(FALSE_SUCCESS_CASE)
        assert case["guard"] == "valid"
        assert case["expected_obligations"], (
            "R05 is the false-success case; its reviewed obligation set is the assertion"
        )
        assert "avg(" in case["reviewed_sql"]

    def test_an_accepted_risk_names_its_risk_and_blesses_no_result(self) -> None:
        risks = [case for case in cases() if case["class"] == "ambiguous"]
        assert risks
        for case in risks:
            assert case["risk"].strip(), case["id"]
            assert case["guard"] == "valid", case["id"]
            assert case.get("result") is None, case["id"]

    def test_an_unread_case_key_is_rejected(self, tmp_path) -> None:
        doctored = cases()
        doctored[0]["expected_obligation"] = []
        with pytest.raises(ValueError, match="unread keys"):
            spec_for(doctored, tmp_path).cases()

    def test_a_guard_verdict_that_contradicts_its_class_is_rejected(self, tmp_path) -> None:
        doctored = cases()
        doctored[0]["guard"] = "rejected"
        with pytest.raises(ValueError, match="declares guard"):
            spec_for(doctored, tmp_path).cases()

    def test_a_rejected_case_must_pin_its_rule(self, tmp_path) -> None:
        doctored = cases()
        target = next(case for case in doctored if case["guard"] == "rejected")
        del target["expected_reason_contains"]
        with pytest.raises(ValueError, match="must pin the rule"):
            spec_for(doctored, tmp_path).cases()

    def test_an_accepted_risk_must_name_the_risk(self, tmp_path) -> None:
        doctored = cases()
        target = next(case for case in doctored if case["class"] == "ambiguous")
        target["risk"] = ""
        with pytest.raises(ValueError, match="name it in `risk`"):
            spec_for(doctored, tmp_path).cases()

    def test_an_expected_count_outside_its_mode_is_rejected(self, tmp_path) -> None:
        doctored = cases()
        target = next(case for case in doctored if case["guard"] == "valid")
        target["result"] = {"mode": "ids_only", "reference_sql": "SELECT id FROM clean_jobs", "expected_count": 1}
        with pytest.raises(ValueError, match="outside aggregate_count mode"):
            spec_for(doctored, tmp_path).cases()

    def test_a_duplicate_id_is_rejected(self, tmp_path) -> None:
        doctored = cases()
        doctored[1]["id"] = doctored[0]["id"]
        with pytest.raises(ValueError, match="duplicated"):
            spec_for(doctored, tmp_path).cases()


class TestTheGateFailsWhenItShould:
    def test_a_wrong_golden_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        doctored = cases()
        target = next(case for case in doctored if case["id"] == "R01-list-role-city")
        target["result"]["reference_sql"] = "SELECT id FROM clean_jobs WHERE id IN (1, 2) ORDER BY id"
        failures = failed_cases(run_sql_gate(spec_for(doctored, tmp_path)))
        assert any(scenario == "R01-list-role-city" and metric == RESULT_METRIC for scenario, metric, _ in failures)

    def test_a_group_count_that_moved_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        doctored = cases()
        target = next(case for case in doctored if case["id"] == "R03-group-city")
        target["result"]["reference_sql"] = (
            "SELECT * FROM (VALUES ('Hanoi', 11), ('Da Nang', 4)) AS reviewed(location, count)"
        )
        failures = failed_cases(run_sql_gate(spec_for(doctored, tmp_path)))
        assert any(scenario == "R03-group-city" and metric == RESULT_METRIC for scenario, metric, _ in failures)

    def test_an_expected_count_that_disagrees_with_the_fixture_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        doctored = cases()
        target = next(case for case in doctored if case["id"] == "R02-count-corpus")
        target["result"]["expected_count"] = 23
        failures = failed_cases(run_sql_gate(spec_for(doctored, tmp_path)))
        assert any(scenario == "R02-count-corpus" and metric == RESULT_METRIC for scenario, metric, _ in failures)

    def test_a_missing_reviewed_obligation_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        doctored = cases()
        target = case_named(FALSE_SUCCESS_CASE)
        next(case for case in doctored if case["id"] == target["id"])["expected_obligations"] = []
        failures = failed_cases(run_sql_gate(spec_for(doctored, tmp_path)))
        assert any(
            scenario == FALSE_SUCCESS_CASE and metric == OBLIGATION_METRIC for scenario, metric, _ in failures
        )

    def test_an_invented_obligation_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        doctored = cases()
        target = next(case for case in doctored if case["id"] == "R01-list-role-city")
        target["expected_obligations"] = ["CROSS_CURRENCY"]
        failures = failed_cases(run_sql_gate(spec_for(doctored, tmp_path)))
        assert any(scenario == "R01-list-role-city" and metric == OBLIGATION_METRIC for scenario, metric, _ in failures)

    def test_a_floor_case_that_is_no_longer_rejected_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        doctored = cases()
        target = next(case for case in doctored if case["id"] == "C05-sleep")
        target["reviewed_sql"] = "SELECT count(*) AS count FROM clean_jobs"
        failures = failed_cases(run_sql_gate(spec_for(doctored, tmp_path)))
        assert any(scenario == "C05-sleep" and metric == GUARD_METRIC for scenario, metric, _ in failures)

    def test_a_rejection_by_a_different_rule_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        doctored = cases()
        target = next(case for case in doctored if case["id"] == "H02-hidden-bookkeeping")
        target["expected_reason_contains"] = "Server-side function calls are not allowed"
        failures = failed_cases(run_sql_gate(spec_for(doctored, tmp_path)))
        assert any(scenario == "H02-hidden-bookkeeping" and metric == GUARD_METRIC for scenario, metric, _ in failures)


class TestTheGateDoesNotSkip:
    def test_an_unreachable_database_is_a_failure_not_a_pass(self, monkeypatch) -> None:
        import evals.fixtures.loader as loader

        monkeypatch.setattr(loader, "fixture_database_reachable", lambda: False)
        with pytest.raises(GateUnavailable) as excinfo:
            run_sql_gate(SqlGuardDataset(), ids=["R02-count-corpus"])
        message = str(excinfo.value)
        assert "not reachable" in message
        assert "failed gate, not a pass" in message

    def test_the_gate_message_names_how_to_start_the_database(self, monkeypatch) -> None:
        import evals.fixtures.loader as loader

        monkeypatch.setattr(loader, "fixture_database_reachable", lambda: False)
        with pytest.raises(GateUnavailable) as excinfo:
            run_sql_gate(SqlGuardDataset(), ids=["R02-count-corpus"])
        assert "docker compose up -d postgres" in str(excinfo.value)


class TestTheGatePasses:
    def test_every_reviewed_case_passes_on_the_pinned_fixture(self, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        report = run_sql_gate(SqlGuardDataset())
        assert failed_cases(report) == []
        assert set(report["metrics"]) == {GUARD_METRIC, OBLIGATION_METRIC, RESULT_METRIC}
        # Coverage is a pass/fail condition, so the gate runs every case the
        # dataset declares and the count is read rather than hard-coded.
        assert len(report["cases"]) == len(cases())
        assert len(report["cases"]) >= 15

    def test_the_false_success_case_emits_its_reviewed_obligation(self, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        report = run_sql_gate(SqlGuardDataset(), ids=[FALSE_SUCCESS_CASE])
        rows = report["by_metric"][OBLIGATION_METRIC]
        assert [(row["scenario_id"], row["score"]) for row in rows] == [(FALSE_SUCCESS_CASE, 1.0)]

    def test_a_subset_can_be_selected(self, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        report = run_sql_gate(SqlGuardDataset(), ids=["R02-count-corpus"])
        assert report["cases"] == ["R02-count-corpus"]
        assert failed_cases(report) == []

    def test_an_unknown_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown dataset ids"):
            run_sql_gate(SqlGuardDataset(), ids=["NOPE-1"])
