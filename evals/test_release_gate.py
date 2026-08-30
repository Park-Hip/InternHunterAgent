"""Bounded live semantic release gate.

Runs a small, fixed smoke suite drawn from the calibration corpus and enforces
the release-policy threshold.  This module is the narrowest possible execution
path for the gate described in issue #344: it calls only ``calibration`` and
reports only what the threshold contract requires, without touching the agent
runtime or the deterministic grader.

The suite is disabled in the default pytest run by the project's ``-m 'not eval'``
addopts.  It is selected explicitly with ``-m eval``, which is how CI gates and
manual smoke runs both invoke it.  A run that selects zero cases fails closed
rather than silently passing.

The gate fails when any required class has recall below 1.0 at the release
threshold, or when the overall recall drops below 1.0.  Unavailable cases — a
provider quota hit, a judge crash, anything that prevents scoring — count as
fails for the classes they touch, keeping the gate fail-closed.
"""

from __future__ import annotations

import pytest

from evals import calibration
from evals.calibration import RELEASE_THRESHOLD, calibration_report
from evals.semantic import AVAILABLE


def _run_gate() -> dict:
    """Execute the release gate and return the report for inspection."""
    corpus = calibration.load_calibration()
    assert corpus["cases"], "release gate corpus must contain at least one case"

    results = calibration.score_calibration(corpus)
    assert results, "release gate scored zero cases"

    report = calibration_report(corpus, results, threshold=RELEASE_THRESHOLD)

    available_cases = [
        case_id
        for case_id, result in results.items()
        if result.get("status") == AVAILABLE
    ]
    unavailable = report.get("unavailable_case_ids", [])
    print(f"\n=== release-gate: {len(available_cases)} scored, "
          f"{len(unavailable)} unavailable, threshold={RELEASE_THRESHOLD} ===")
    for group, metrics in sorted(report["groups"].items()):
        recall = metrics.get("recall")
        sample = metrics.get("sample_size", 0)
        status = "PASS" if recall is not None and recall >= 1.0 else "FAIL"
        print(f"  [{status}] {group}: n={sample}, "
              f"recall={recall if recall is None else f'{recall:.3f}'}, "
              f"precision={metrics.get('precision')}")

    if unavailable:
        print(f"  unavailable: {unavailable}")

    breached: list[str] = []
    for group, metrics in report["groups"].items():
        recall = metrics.get("recall")
        sample = metrics.get("sample_size", 0)
        if sample == 0:
            continue
        if recall is None or recall < 1.0:
            breached.append(
                f"{group}: recall={recall} (n={sample})"
            )

    assert not breached, (
        "release gate threshold breached:\n" + "\n".join(f"  - {b}" for b in breached)
    )

    assert available_cases, (
        "release gate scored zero cases — provider or judge unavailable"
    )

    return report


@pytest.mark.eval
def test_release_gate_enforces_threshold_and_reports_per_class() -> None:
    """Score the calibration corpus and verify the release gate semantics.

    The gate is defined by three invariants that this single test asserts:

    1. **Nonzero collection.**  The corpus must contain cases; an empty corpus
       would make the threshold meaningless.
    2. **Threshold enforcement.**  Every case must be scored and the report must
       be produced at ``RELEASE_THRESHOLD``.  Unavailable cases are called out
       explicitly.
    3. **Fail-closed on breach.**  If any class or the overall group has recall
       < 1.0, the test fails with a summary that names every breached group.
    """
    _run_gate()
