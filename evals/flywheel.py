"""Offline candidate selector and human-review exporter for the trace-to-registry flywheel.

Phase 1 only reads local artifacts — no Langfuse calls, no registry writes.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

import yaml


def _class_from_scenario_id(scenario_id: str) -> str:
    """Derive class (SAF/HON/HLP) from a scenario ID prefix."""
    for prefix in ("SAF", "HON", "HLP"):
        if scenario_id.startswith(prefix + "-"):
            return prefix
    return "UNKNOWN"


def _load_json(path: str | Path) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def _judge_scores_for_scenario(
    scores: dict[str, Any], scenario_id: str
) -> tuple[float | None, str | None]:
    """Look up judge score and rationale for a scenario ID.

    Score keys in the artifact look like ``hlp-abstraction-fail``.  We match by
    normalising both sides to lowercase and replacing hyphens/underscores so that
    ``HLP_SENIOR_TITLE_1`` maps onto ``hlp-senior-title-*`` variants.
    """
    normalized = scenario_id.lower().replace("_", "-")
    # Also try without trailing digit(s) — score keys omit the repeat number.
    normalized_no_num = normalized.rstrip("0123456789").rstrip("-")
    results = scores.get("results", {})
    for key, entry in results.items():
        candidate = key.lower().replace("_", "-")
        # Strip trailing -pass/-fail to get the scenario stem
        for suffix in ("-pass", "-fail"):
            if candidate.endswith(suffix):
                candidate = candidate[: -len(suffix)]
                break
        if candidate == normalized or candidate == normalized_no_num:
            return entry.get("score"), entry.get("rationale")
    return None, None


def _calibration_lookup(calibration: dict[str, Any], scenario_id: str) -> str | None:
    """Return the human label (PASS/FAIL) from calibration for a scenario ID, if any."""
    normalized = scenario_id.lower().replace("_", "-")
    for case in calibration.get("cases", []):
        sid = case.get("scenario_id", "").lower().replace("_", "-")
        if sid == normalized:
            human = case.get("human", {})
            return human.get("overall") or human.get("label")
    return None


def select_candidates(
    grade_path: str | Path,
    scores_path: str | Path,
    calibration_path: str | Path = "evals/calibration_v7.yaml",
) -> list[dict]:
    """Return tiered candidate list for human review.

    Tier 1 — deterministic failures (scenario or any repeat is FAIL).
    Tier 2 — semantic disagreements from the agreement report.
    Tier 3 — ~10 % control sample of PASS scenarios, stratified by class.
    """
    grade = _load_json(grade_path)
    scores = _load_json(scores_path)
    calibration = _load_yaml(calibration_path)

    scenario_outcomes = grade.get("scenario_outcomes", {})
    candidates: list[dict] = []
    seen_scenario_ids: set[str] = set()

    # ---- Tier 1: deterministic failures ----
    for scenario_id, info in scenario_outcomes.items():
        status = info.get("status", "")
        repeats = info.get("repeats", [])
        has_repeat_fail = any(r.get("status") == "FAIL" for r in repeats)

        if status == "FAIL" or has_repeat_fail:
            class_name = _class_from_scenario_id(scenario_id)
            judge_score, judge_rationale = _judge_scores_for_scenario(scores, scenario_id)
            human_label = _calibration_lookup(calibration, scenario_id)
            trace_id = _extract_trace_id(grade, scenario_id)

            candidates.append(
                {
                    "tier": "T1",
                    "scenario_id": scenario_id,
                    "class": class_name,
                    "deterministic_verdict": "FAIL",
                    "judge_score": judge_score,
                    "judge_rationale": judge_rationale,
                    "human_label": human_label,
                    "trace_id": trace_id,
                    "reason": "Scenario has FAIL status in grade artifact"
                    if status == "FAIL"
                    else "At least one repeat has FAIL status",
                }
            )
            seen_scenario_ids.add(scenario_id)

    # ---- Tier 2: semantic disagreements ----
    try:
        report_path = Path(grade_path)
        report_path = report_path.with_stem(report_path.stem.replace("grade", "agreement-report"))
        report = _load_json(report_path)
    except FileNotFoundError:
        report = {}

    disagreements = report.get("report_at_release_thresholds", {}).get(
        "disagreements", []
    )
    for d in disagreements:
        scenario_id = d.get("scenario_id", "")
        class_name = d.get("class", _class_from_scenario_id(scenario_id))
        judge_score = d.get("judge_score")
        judge_rationale = d.get("judge_rationale")
        human_label = d.get("human_label")
        trace_id = _extract_trace_id(grade, scenario_id)

        if scenario_id not in seen_scenario_ids:
            candidates.append(
                {
                    "tier": "T2",
                    "scenario_id": scenario_id,
                    "class": class_name,
                    "deterministic_verdict": human_label or "UNKNOWN",
                    "judge_score": judge_score,
                    "judge_rationale": judge_rationale,
                    "human_label": human_label,
                    "trace_id": trace_id,
                    "reason": "Semantic disagreement between human label and judge verdict",
                }
            )
            seen_scenario_ids.add(scenario_id)

    # ---- Tier 3: control sample (~10% PASS, stratified by class) ----
    pass_scenarios: dict[str, list[str]] = {}
    for scenario_id, info in scenario_outcomes.items():
        if info.get("status") == "PASS" and scenario_id not in seen_scenario_ids:
            class_name = _class_from_scenario_id(scenario_id)
            pass_scenarios.setdefault(class_name, []).append(scenario_id)

    for class_name, sids in pass_scenarios.items():
        random.seed(42)  # reproducible sampling
        count = max(1, math.ceil(len(sids) * 0.1))
        sampled = random.sample(sids, min(count, len(sids)))
        for scenario_id in sampled:
            judge_score, judge_rationale = _judge_scores_for_scenario(scores, scenario_id)
            human_label = _calibration_lookup(calibration, scenario_id)
            trace_id = _extract_trace_id(grade, scenario_id)

            candidates.append(
                {
                    "tier": "T3",
                    "scenario_id": scenario_id,
                    "class": class_name,
                    "deterministic_verdict": "PASS",
                    "judge_score": judge_score,
                    "judge_rationale": judge_rationale,
                    "human_label": human_label,
                    "trace_id": trace_id,
                    "reason": "Control sample — stratified ~10% PASS selection",
                }
            )
            seen_scenario_ids.add(scenario_id)

    return candidates


def _extract_trace_id(grade: dict[str, Any], scenario_id: str) -> str | None:
    """Best-effort trace ID extraction from the grade artifact."""
    scenarios = grade.get("scenarios", {})
    repeats = scenarios.get(scenario_id, [])
    for rep in repeats:
        for turn in rep.get("turns", []):
            seams = turn.get("seams", {})
            tid = seams.get("trace_id")
            if tid:
                return tid
    return None


def export_review(candidates: list[dict], out_path: str | Path) -> None:
    """Write a Markdown review bundle to *out_path*."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    by_tier: dict[str, list[dict]] = {"T1": [], "T2": [], "T3": []}
    for c in candidates:
        by_tier.setdefault(c["tier"], []).append(c)

    lines: list[str] = []
    lines.append("<style>")
    lines.append("body { background-color: #FBFAF7; color: #1B1A17; font-family: sans-serif; }")
    lines.append("</style>")
    lines.append("")
    lines.append("# Flywheel Review Bundle")
    lines.append("")
    lines.append(f"**Total candidates:** {len(candidates)}")
    lines.append(f"- Tier 1 (deterministic failures): {len(by_tier['T1'])}")
    lines.append(f"- Tier 2 (semantic disagreements): {len(by_tier['T2'])}")
    lines.append(f"- Tier 3 (control sample): {len(by_tier['T3'])}")
    lines.append("")

    tier_titles = {"T1": "Tier 1 — Deterministic Failures", "T2": "Tier 2 — Semantic Disagreements", "T3": "Tier 3 — Control Sample"}
    for tier_key in ("T1", "T2", "T3"):
        items = by_tier[tier_key]
        if not items:
            continue
        lines.append(f"## {tier_titles[tier_key]}")
        lines.append("")
        for c in items:
            lines.append(f"### {c['scenario_id']}")
            lines.append("")
            lines.append(f"- **Class:** {c['class']}")
            lines.append(f"- **Verdict:** {c['deterministic_verdict']}")
            lines.append(f"- **Judge score:** {c['judge_score'] if c['judge_score'] is not None else 'N/A'}")
            if c.get("judge_rationale"):
                lines.append(f"- **Judge rationale:** {c['judge_rationale']}")
            if c.get("human_label"):
                lines.append(f"- **Human label:** {c['human_label']}")
            if c.get("trace_id"):
                lines.append(f"- **Trace ID:** {c['trace_id']}")
            lines.append(f"- **Reason:** {c['reason']}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Generated by evals/flywheel.py — Phase 1 offline trace selector.*")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline trace candidate selector and review exporter")
    parser.add_argument("--grade", required=True, help="Path to grade artifact JSON")
    parser.add_argument("--scores", required=True, help="Path to judge scores JSON")
    parser.add_argument(
        "--calibration",
        default="evals/calibration_v7.yaml",
        help="Path to calibration corpus YAML",
    )
    parser.add_argument("-o", "--output", required=True, help="Output Markdown path")
    args = parser.parse_args()

    candidates = select_candidates(args.grade, args.scores, args.calibration)
    export_review(candidates, args.output)
    print(f"Wrote {len(candidates)} candidates to {args.output}")


if __name__ == "__main__":
    main()
