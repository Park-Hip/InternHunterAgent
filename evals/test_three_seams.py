"""`deepeval test run evals/test_three_seams.py` — runs the agent against every
golden and prints a score per metric per seam. No threshold gating (T0011.5
owns pass/fail calibration): tests always pass, they just report scores.
"""

import pytest

from evals.goldens import load_goldens
from evals.harness import run_case

GOLDENS = load_goldens()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", GOLDENS, ids=[case["id"] for case in GOLDENS])
async def test_three_seams(case: dict) -> None:
    result = await run_case(case)

    print(f"\n=== {result['case_id']} ===")
    print(f"question/last-turn: {case.get('input') or case.get('turns', [None])[-1]}")
    print(f"answer: {result['answer']}")
    print(f"tools_called: {result['tools_called']}")
    if result["sql_text"] is not None:
        print(f"generate_sql (seam 2) span SQL: {result['sql_text']}")

    for seam_name, metric_scores in result["results"].items():
        for metric_name, payload in metric_scores.items():
            line = f"  [{seam_name}] {metric_name}: {payload['score']}"
            if payload.get("error"):
                line += f" (error: {payload['error']})"
            print(line)

    # Report-only: T0011.5 owns threshold calibration and pass/fail gating.
    # A model producing a poor/empty answer is exactly what this harness is
    # here to measure, not something that should fail the pytest run.
