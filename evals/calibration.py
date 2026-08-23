"""Versioned human-label corpus validation and calibration reporting."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from evals.semantic import AVAILABLE, evaluate_semantic_repeat, semantic_assertion
from evals.scenarios import load_scenarios

CALIBRATION_PATH = Path(__file__).with_name("calibration_v6.yaml")
_REQUIRED = {
    "id",
    "scenario_id",
    "language",
    "prompt_version",
    "source",
    "trajectory",
    "human",
}


def load_calibration(path: Path = CALIBRATION_PATH) -> dict[str, Any]:
    """Load independent human labels for the current semantic contracts."""
    corpus = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(corpus, dict) or set(corpus) != {
        "schema_version",
        "corpus_id",
        "cases",
    }:
        raise ValueError(
            "Calibration corpus must contain schema_version, corpus_id, and cases"
        )
    if corpus["schema_version"] != 1 or not isinstance(corpus["corpus_id"], str):
        raise ValueError(
            "Calibration corpus has an unsupported schema version or corpus id"
        )
    scenarios = {item["id"]: item for item in load_scenarios()}
    cases = corpus["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("Calibration corpus cases must be a non-empty list")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != _REQUIRED:
            raise ValueError(
                "Each calibration case must use the complete versioned schema"
            )
        if not isinstance(case["id"], str) or case["id"] in seen:
            raise ValueError("Calibration case ids must be unique strings")
        seen.add(case["id"])
        scenario = scenarios.get(case["scenario_id"])
        if scenario is None or semantic_assertion(scenario) is None:
            raise ValueError(
                "Calibration cases must reference a scenario with a semantic assertion"
            )
        if not all(
            isinstance(case[field], str) and case[field]
            for field in ("language", "prompt_version", "source")
        ):
            raise ValueError(
                "Calibration cases must stamp language, prompt version, and source"
            )
        trajectory = case["trajectory"]
        if (
            not isinstance(trajectory, list)
            or not trajectory
            or not all(
                isinstance(turn, dict)
                and set(turn) == {"question", "answer"}
                and all(isinstance(value, str) and value for value in turn.values())
                for turn in trajectory
            )
        ):
            raise ValueError(
                "Calibration trajectories require non-empty question and answer turns"
            )
        human = case["human"]
        if not isinstance(human, dict) or set(human) != {"overall", "rationale"}:
            raise ValueError(
                "Calibration cases require a human overall label and rationale"
            )
        if human["overall"] not in {"PASS", "FAIL"} or not isinstance(
            human["rationale"], str
        ):
            raise ValueError("Human labels must be PASS or FAIL with a rationale")
    return corpus


def calibration_report(
    corpus: dict[str, Any],
    results: dict[str, dict[str, Any]],
    threshold: float | None = None,
) -> dict[str, Any]:
    """Compare available judge scores with human labels without overwriting them."""
    groups: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    unavailable: list[str] = []
    for case in corpus["cases"]:
        result = results.get(case["id"], {})
        if result.get("status") != AVAILABLE or not isinstance(
            result.get("score"), (int, float)
        ):
            unavailable.append(case["id"])
            continue
        if threshold is None:
            continue
        row = (result["score"] >= threshold, case["human"]["overall"] == "PASS")
        scenario_class = case["scenario_id"].split("-", 1)[0]
        for group in (
            "overall",
            f"class:{scenario_class}",
            f"language:{case['language']}",
            f"prompt_version:{case['prompt_version']}",
            "assertion_type:semantic",
        ):
            groups[group].append(row)

    def metrics(rows: list[tuple[bool, bool]]) -> dict[str, Any]:
        tp = sum(predicted and actual for predicted, actual in rows)
        fp = sum(predicted and not actual for predicted, actual in rows)
        fn = sum(not predicted and actual for predicted, actual in rows)
        return {
            "sample_size": len(rows),
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        }

    return {
        "threshold": threshold,
        "groups": {key: metrics(value) for key, value in sorted(groups.items())},
        "unavailable_case_ids": unavailable,
    }


def score_calibration(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Run the DeepEval semantic path over human-labelled corpus evidence.

    The returned map is deliberately separate from the corpus. A judge result may be
    regenerated, but the independently authored human label is never rewritten by it.
    """
    scenarios = {item["id"]: item for item in load_scenarios()}
    results: dict[str, dict[str, Any]] = {}
    for case in corpus["cases"]:
        repeat = {
            "turns": [
                {"seams": {"question": turn["question"], "answer": turn["answer"]}}
                for turn in case["trajectory"]
            ]
        }
        result = evaluate_semantic_repeat(scenarios[case["scenario_id"]], repeat)
        if result is None:
            raise ValueError(
                "validated calibration scenario lost its semantic assertion"
            )
        results[case["id"]] = result.to_dict()
    return results
