from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from evals.judge import build_judge


def test_judge_scaffold() -> None:
    test_case = LLMTestCase(
        input="Say hello to a new user.",
        actual_output="Hi there! It's great to have you here.",
    )
    metric = GEval(
        name="PoliteGreeting",
        criteria="Is the output a polite greeting? Score 0-1.",
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=build_judge(),
        threshold=0.05,
    )
    assert_test(test_case, [metric])
