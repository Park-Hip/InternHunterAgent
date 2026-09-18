"""Opt-in live calibration scoring check (not a release gate).

Scores the committed calibration corpus (v7 + v8) and reports the per-class
threshold metrics.  This module calls only ``calibration`` and reports what the
threshold contract requires, without touching the agent runtime or the
deterministic grader.

The suite is disabled in the default pytest run by the project's ``-m 'not eval'``
addopts.  It is selected explicitly with ``-m eval`` when an operator wants a live
diagnostic over the combined corpus.  It is not part of any CI workflow and does
not certify a release; the live semantic release-gate CI path was retired in #415.

The check reports one threshold per semantic class (SAF, HON, HLP) and an
aggregate bar, and fails closed on zero selection, an unavailable case, or a class
whose recall drops below 1.0.  False passes (a judge pass on a human-FAIL case) are
measured and reported as precision, never silently accepted as recall.
"""

from __future__ import annotations

import pytest

from evals import calibration
from evals.semantic import AVAILABLE

_CLASS_GROUPS = (
    ("SAF", "class:SAF"),
    ("HON", "class:HON"),
    ("HLP", "class:HLP"),
)


def _run_gate(
    thresholds_by_class: dict[str, float] | None = None,
) -> dict:
    """Score the combined corpus and return the threshold report for inspection."""
    corpus = calibration.load_combined_calibration()
    assert corpus["cases"], "release gate corpus must contain at least one case"

    results = calibration.score_calibration(corpus)
    assert results, "release gate scored zero cases"

    thresholds = (
        calibration.RELEASE_THRESHOLDS_BY_CLASS
        if thresholds_by_class is None
        else thresholds_by_class
    )

    report = calibration.calibration_report(
        corpus,
        results,
        threshold=calibration.RELEASE_THRESHOLD,
        thresholds_by_class=thresholds,
    )

    available_cases = [
        case_id
        for case_id, result in results.items()
        if result.get("status") == AVAILABLE
    ]
    unavailable = report.get("unavailable_case_ids", [])
    print(f"\n=== release-gate: {len(available_cases)} scored, "
          f"{len(unavailable)} unavailable ===")
    for cls, group in _CLASS_GROUPS:
        metrics = report["groups"].get(group)
        if metrics is None:
            print(f"  [MISSING] {group}: no scored cases")
            continue
        thr = thresholds.get(cls, calibration.RELEASE_THRESHOLD)
        recall = metrics.get("recall")
        status = "PASS" if recall is not None and recall >= 1.0 else "FAIL"
        print(f"  [{status}] {group}: n={metrics.get('sample_size', 0)}, "
              f"threshold={thr}, "
              f"recall={recall if recall is None else f'{recall:.3f}'}, "
              f"precision={metrics.get('precision')}, "
              f"false_passes={metrics.get('false_positive')}")
    overall = report["groups"].get("overall")
    if overall is not None:
        recall = overall.get("recall")
        status = "PASS" if recall is not None and recall >= 1.0 else "FAIL"
        print(f"  [{status}] overall: n={overall.get('sample_size', 0)}, "
              f"recall={recall if recall is None else f'{recall:.3f}'}, "
              f"precision={overall.get('precision')}, "
              f"false_passes={overall.get('false_positive')}")

    if unavailable:
        print(f"  unavailable: {unavailable}")

    # Fail-closed on partial scoring loss: an unavailable case is a provider or
    # judge outage that must not be silently dropped from every metric group.
    # Even if the scored subset keeps recall at 1.0, a partial run cannot certify
    # the release policy.
    assert not unavailable, (
        f"release gate scored {len(available_cases)}/{len(results)} cases; "
        f"{len(unavailable)} unavailable — provider or judge outage: {unavailable}"
    )

    breached: list[str] = []
    for group, metrics in report["groups"].items():
        recall = metrics.get("recall")
        sample = metrics.get("sample_size", 0)
        if sample == 0:
            continue
        if recall is None or recall < 1.0:
            breached.append(f"{group}: recall={recall} (n={sample})")

    assert not breached, (
        "release gate threshold breached:\n" + "\n".join(f"  - {b}" for b in breached)
    )

    assert available_cases, (
        "release gate scored zero cases — provider or judge unavailable"
    )

    return report


@pytest.mark.eval
def test_release_gate_enforces_threshold_and_reports_per_class() -> None:
    """Score the calibration corpus and verify the per-class threshold report.

    The report is defined by these invariants that this single test asserts:

    1. **Nonzero collection.**  The corpus must contain cases; an empty corpus
       would make the threshold meaningless.
    2. **Per-class threshold reporting.**  Every case must be scored, and each
       class (plus the aggregate) must keep recall at 1.0 under its own threshold.
       Unavailable cases are called out explicitly.
    3. **Fail-closed on breach.**  If any class or the overall group has recall
       < 1.0, the test fails with a summary that names every breached group.
    """
    report = _run_gate()
    for cls in ("SAF", "HON", "HLP"):
        assert report["groups"].get(f"class:{cls}", {}).get("sample_size", 0) > 0, (
            f"release gate corpus must score class:{cls}"
        )