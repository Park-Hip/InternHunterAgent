"""The credential-free v0 gate, and what it refuses to let pass.

A gate is only worth having if it fails when it should. Most of this module
exists to prove that: a wrong golden, a wrong plan, a missing evidence label, and
an absent-capability claim that is not true each have to turn the gate red, and
an unreachable database has to be a failure rather than a quiet pass.
"""

from __future__ import annotations

import copy

import pytest
import yaml

from evals.datasets import DatasetSpec, dataset
from evals.metrics import LEGACY_METRICS, METRIC_BY_NAME
from evals.v0_gate import (
    PLAN_METRIC,
    RESULT_METRIC,
    GateUnavailable,
    failed_cases,
    run_v0_gate,
)


def v0_cases() -> list[dict]:
    return copy.deepcopy(dataset("v0").scenarios())


def spec_for(cases: list[dict], tmp_path) -> DatasetSpec:
    path = tmp_path / "v0_doctored.yaml"
    path.write_text(yaml.safe_dump(cases, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return DatasetSpec(path)


@pytest.fixture(scope="module")
def fixture_available() -> bool:
    from evals.fixtures.loader import fixture_database_reachable

    return fixture_database_reachable()


class TestDatasetShape:
    def test_every_case_has_a_request_or_a_capability_claim(self) -> None:
        for case in v0_cases():
            has_request = case.get("expected_request") is not None
            has_claim = case.get("absent_capability") is not None
            assert has_request != has_claim, (
                f"{case['id']} needs exactly one of a reviewed request or a capability claim"
            )

    def test_a_requested_case_grades_its_plan(self) -> None:
        for case in v0_cases():
            if case.get("expected_request") is None:
                continue
            assert case.get("expected_filters") is not None, case["id"]

    def test_the_v0_dataset_declares_no_retired_metric(self) -> None:
        for case in v0_cases():
            assert not set(case["metrics"]) & LEGACY_METRICS, case["id"]

    def test_a_retired_metric_is_rejected_on_the_v0_dataset(self, tmp_path) -> None:
        cases = v0_cases()
        cases[0]["metrics"] = ["sql_accuracy"]
        with pytest.raises(ValueError, match="retired metrics"):
            spec_for(cases, tmp_path).scenarios()

    def test_the_two_gate_metrics_are_declared_and_deterministic(self) -> None:
        for name in (PLAN_METRIC, RESULT_METRIC):
            assert name in METRIC_BY_NAME
            assert METRIC_BY_NAME[name].kind.value == "deterministic"


class TestTheGateFailsWhenItShould:
    def test_a_wrong_golden_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        cases = v0_cases()
        target = next(case for case in cases if case["id"] == "V0-COUNT-CORPUS")
        target["expected_aggregates"]["count"] = 23
        failures = failed_cases(run_v0_gate(spec_for(cases, tmp_path)))
        assert any(scenario == "V0-COUNT-CORPUS" and metric == RESULT_METRIC for scenario, metric, _ in failures)

    def test_a_wrong_plan_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        cases = v0_cases()
        target = next(case for case in cases if case["id"] == "V0-LIST-ROLE-CITY")
        target["expected_filters"] = [{"field": "location", "values": ["Hanoi"]}]
        failures = failed_cases(run_v0_gate(spec_for(cases, tmp_path)))
        assert any(scenario == "V0-LIST-ROLE-CITY" and metric == PLAN_METRIC for scenario, metric, _ in failures)

    def test_a_missing_evidence_label_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        cases = v0_cases()
        target = next(case for case in cases if case["id"] == "V0-SALARY-AMBIGUOUS")
        target["required_labels"] = ["A LABEL THAT IS NOT A CONTRACT LABEL"]
        failures = failed_cases(run_v0_gate(spec_for(cases, tmp_path)))
        assert any(scenario == "V0-SALARY-AMBIGUOUS" and metric == RESULT_METRIC for scenario, metric, _ in failures)

    def test_a_state_that_is_not_the_reviewed_one_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        cases = v0_cases()
        target = next(case for case in cases if case["id"] == "V0-COUNT-CORPUS")
        target["contract_state"] = "UNSUPPORTED"
        failures = failed_cases(run_v0_gate(spec_for(cases, tmp_path)))
        assert any(scenario == "V0-COUNT-CORPUS" and metric == RESULT_METRIC for scenario, metric, _ in failures)

    def test_a_description_the_golden_requires_must_be_returned(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        cases = v0_cases()
        target = next(case for case in cases if case["id"] == "V0-DETAIL-DESCRIPTION")
        target["expected_description_contains"] = ["a phrase the posting does not contain"]
        failures = failed_cases(run_v0_gate(spec_for(cases, tmp_path)))
        assert any(scenario == "V0-DETAIL-DESCRIPTION" and metric == RESULT_METRIC for scenario, metric, _ in failures)

    def test_an_absent_capability_claim_that_is_false_fails(self, tmp_path, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        cases = v0_cases()
        target = next(case for case in cases if case["id"] == "V0-CLARIFY-SUBJECTIVE")
        # `salary_min` is a real filter field, so this claim is false and must fail.
        target["absent_capability"] = [{"kind": "no_filter_field_matching", "value": "salary"}]
        failures = failed_cases(run_v0_gate(spec_for(cases, tmp_path)))
        assert any(scenario == "V0-CLARIFY-SUBJECTIVE" for scenario, _, _ in failures)


class TestTheGateDoesNotSkip:
    def test_an_unreachable_database_is_a_failure_not_a_pass(self, monkeypatch) -> None:
        import evals.fixtures.loader as loader

        monkeypatch.setattr(loader, "fixture_database_reachable", lambda: False)
        with pytest.raises(GateUnavailable) as excinfo:
            run_v0_gate(dataset("v0"), ids=["V0-COUNT-CORPUS"])
        message = str(excinfo.value)
        assert "not reachable" in message
        assert "failed gate, not a pass" in message

    def test_the_gate_message_names_how_to_start_the_database(self, monkeypatch) -> None:
        import evals.fixtures.loader as loader

        monkeypatch.setattr(loader, "fixture_database_reachable", lambda: False)
        with pytest.raises(GateUnavailable) as excinfo:
            run_v0_gate(dataset("v0"), ids=["V0-COUNT-CORPUS"])
        assert "docker compose up -d postgres" in str(excinfo.value)


class TestTheGatePasses:
    def test_every_v0_case_passes_on_the_pinned_fixture(self, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        report = run_v0_gate(dataset("v0"))
        assert failed_cases(report) == []
        assert set(report["metrics"]) == {PLAN_METRIC, RESULT_METRIC}
        # Coverage is a pass/fail condition, so the gate runs every case the
        # dataset declares and the count is read rather than hard-coded.
        assert len(report["cases"]) == len(v0_cases())
        assert len(report["cases"]) >= 16

    def test_a_subset_can_be_selected(self, fixture_available) -> None:
        if not fixture_available:
            pytest.skip("the gate needs the evaluation fixture")
        report = run_v0_gate(dataset("v0"), ids=["V0-COUNT-CORPUS"])
        assert report["cases"] == ["V0-COUNT-CORPUS"]
        assert failed_cases(report) == []

    def test_an_unknown_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown dataset ids"):
            run_v0_gate(dataset("v0"), ids=["NOPE-1"])
