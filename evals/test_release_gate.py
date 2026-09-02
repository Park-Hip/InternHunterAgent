"""Bounded live semantic release gate.

Runs a small, fixed smoke suite drawn from the release-gate calibration corpus and enforces
the release-policy threshold.  This module is the narrowest possible execution path for the
gate described in issue #344: it calls only ``calibration`` and reports only what the threshold
contract requires, without touching the agent runtime or the deterministic grader.

The suite is disabled in the default pytest run by the project's ``-m 'not eval'`` addopts.
It is selected explicitly with ``-m eval``, which is how CI gates and manual smoke runs both
invoke it.  A run that selects zero cases fails closed rather than silently passing.

The gate fails when any required class has recall below 1.0 at the release threshold, or when
the overall recall drops below 1.0.  Unavailable cases — a provider quota hit, a judge crash,
anything that prevents scoring — count as fails for the classes they touch, keeping the gate
fail-closed.

The release-gate corpus (``calibration_release_gate.yaml``) is a deliberately narrowed subset
of the full calibration: one PASS and one FAIL case for each of SAF, HON, and HLP — the three
classes that map to the release policy's safety, honesty, and core-helpfulness pillars.
The full 44-case calibration remains available for diagnostic runs via ``calibration_v7.yaml``.
"""

from __future__ import annotations

from collections import defaultdict
import pytest

from evals import calibration
from evals.calibration import RELEASE_GATE_PATH, RELEASE_THRESHOLD, calibration_report
from evals.semantic import AVAILABLE


_REQUIRED_RELEASE_CLASSES = frozenset({"SAF", "HON", "HLP"})


def _validate_release_corpus(corpus: dict) -> None:
    cases = corpus["cases"]
    assert len(cases) == 6, (
        f"release gate corpus must contain exactly six cases, found {len(cases)}"
    )

    labels_by_class: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        scenario_class = case["scenario_id"].split("-", 1)[0]
        labels_by_class[scenario_class].append(case["human"]["overall"])

    assert set(labels_by_class) == _REQUIRED_RELEASE_CLASSES, (
        "release gate corpus must cover only SAF, HON, and HLP; "
        f"found {sorted(labels_by_class)}"
    )
    for scenario_class in sorted(_REQUIRED_RELEASE_CLASSES):
        assert sorted(labels_by_class[scenario_class]) == ["FAIL", "PASS"], (
            f"release gate corpus must contain one PASS and one FAIL for "
            f"{scenario_class}, found {labels_by_class[scenario_class]}"
        )


def _check_prerequisites() -> None:
    """Validate that the judge provider credential is available before attempting scoring.

    Failing early with a clear message is preferable to letting DeepEval explode deep inside
    the test with a confusing stack trace.  The key name must match the provider set in
    ``config/settings.yaml`` under ``eval.judge.provider`` (currently ``google`` → ``GOOGLE_API_KEY``).
    """
    import src.core.config as config
    import src.core.db as db

    # Force-reload settings so we read the live environment, not a cached copy.
    if hasattr(config, "_settings_cache"):
        config._settings_cache = None
    if hasattr(db, "_engine"):
        db._engine = None
    if hasattr(db, "_session_factory"):
        db._session_factory = None

    cfg = config.settings.config_yaml.get("eval", {}).get("judge", {})
    provider = (cfg.get("provider") or "").lower().strip()

    key_env: dict[str, str] = {
        "groq": "GROQ_API_KEY",
        "google": "GOOGLE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    required_key = key_env.get(provider)
    if required_key is None:
        raise RuntimeError(
            f"release gate: unsupported judge provider '{provider}' in config/settings.yaml; "
            f"supported: {list(key_env)}"
        )
    if not getattr(config.settings, required_key, None):
        raise RuntimeError(
            f"release gate: missing required credential {required_key} (judge provider='{provider}'); "
            f"set it before running the live gate."
        )


def _run_gate() -> dict:
    """Execute the release gate and return the report for inspection."""
    _check_prerequisites()

    corpus = calibration.load_calibration(RELEASE_GATE_PATH)
    assert corpus["cases"], "release gate corpus must contain at least one case"
    _validate_release_corpus(corpus)

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
    """Score the release-gate calibration corpus and verify the release gate semantics.

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

