"""Load the versioned golden Q&A set and adapt it into a DeepEval dataset.

Kept separate from the fixture DB loader (`evals/fixtures/`) — this module
needs no database connection.
"""

import json
from pathlib import Path

from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import ToolCall

GOLDEN_DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.json"

_REQUIRED_KEYS = {"id", "category", "type", "expected_output"}


def load_goldens() -> list[dict]:
    """Parse evals/goldens/golden_dataset.json into a list of case dicts."""
    raw = json.loads(GOLDEN_DATASET_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Expected a JSON array in {GOLDEN_DATASET_PATH}")

    for case in raw:
        missing = _REQUIRED_KEYS - case.keys()
        if missing:
            raise ValueError(f"Golden case {case.get('id', '<unknown>')} missing keys: {missing}")

        has_input = "input" in case
        has_turns = "turns" in case
        if has_input == has_turns:
            raise ValueError(
                f"Golden case {case['id']} must have exactly one of 'input' or 'turns'"
            )

    return raw


def build_eval_dataset() -> EvaluationDataset:
    """Build a DeepEval EvaluationDataset from the single-turn goldens.

    The 2 conversational cases (type=="conversational") are left out here —
    the next ticket turns them into ConversationalTestCases at run time.
    """
    goldens = [case for case in load_goldens() if case["type"] == "single"]

    deepeval_goldens = []
    for case in goldens:
        expected_tools = case.get("expected_tools")
        tool_calls = (
            [ToolCall(name=tool_name) for tool_name in expected_tools]
            if expected_tools is not None
            else None
        )

        deepeval_goldens.append(
            Golden(
                input=case["input"],
                expected_output=case["expected_output"],
                expected_tools=tool_calls,
                additional_metadata={
                    "id": case["id"],
                    "category": case["category"],
                    "honesty_probe": case["honesty_probe"],
                    "difficulty": case["difficulty"],
                },
            )
        )

    return EvaluationDataset(goldens=deepeval_goldens)
