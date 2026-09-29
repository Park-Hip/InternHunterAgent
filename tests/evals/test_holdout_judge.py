"""Opt-in, 12-call judge-versus-human check for the retained v8 holdout.

Disagreement is printed as a finding, not a failing assertion while criteria
and dataset design are still under review. Run with pytest -o addopts='' -m eval
-s tests/evals/test_holdout_judge.py after setting the judge credential.
"""

from pathlib import Path

from deepeval.metrics import GEval
import pytest
import yaml

from evals.datasets import dataset
from evals.env import bind_fixture_environment
from evals.metrics import judge_case, metric as metric_spec


CASES = yaml.safe_load(Path("evals/calibration_v8.yaml").read_text(encoding="utf-8"))["cases"]
SCENARIOS = {item["id"]: item for item in dataset("default").scenarios()}


@pytest.mark.eval
@pytest.mark.parametrize("item", CASES, ids=lambda item: item["id"])
def test_judge_agreement_finding(item: dict) -> None:
    bind_fixture_environment()
    from evals.judge import get_judge

    scenario = SCENARIOS[item["scenario_id"]]
    turn = item["trajectory"][-1]
    capture = {"question": turn["question"], "answer": turn["answer"]}
    test_case, params, criteria = judge_case(capture, scenario, metric_spec("rubric"))
    metric = GEval(name="rubric", criteria=criteria, evaluation_params=params, model=get_judge(), async_mode=False)
    metric.measure(test_case, _show_indicator=False)
    predicted = "PASS" if metric.score >= 0.5 else "FAIL"
    print(f"{item['id']}: human={item['human']['overall']} judge={predicted} score={metric.score} agreement={predicted == item['human']['overall']}")
    assert metric.score is not None
