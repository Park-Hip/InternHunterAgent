"""Score the versioned calibration corpora with the real judge, resumably.

Separate from ``evals/score.py`` (capture-artifact scoring) because the input is
different: this module scores the committed, immutable, human-labelled corpus,
not a recorded capture. It is the supported writer of calibration judge evidence
under ``evals/runs/``, and the only place that persists calibration judge scores.

The real judge is reached only through the project's existing semantic path:
``evals.semantic.evaluate_semantic_repeat`` -> ``evals.judge.build_judge``, the
same call chain the live release gate exercises.

Usage (from a clean worktree, provider keys present in the environment or
``.env``):

    uv run python -m evals.calibration_score \\
        --corpus v7 --corpus v8 \\
        --out evals/runs/<run>-judge-scores.json

The run is resumable: a case already recorded AVAILABLE with a numeric score is
skipped on re-entry, so an interrupted, judge-throttled run keeps its completed
calls. ``--rescore`` re-measures every case. Judge results are kept in a separate
artifact and never write back into the human labels.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals._paths import CALIBRATION_VERSIONS
from evals.calibration import load_combined_calibration
from evals.judge import _load_judge_cfg
from evals.scenarios import load_scenarios
from evals.semantic import AVAILABLE, evaluate_semantic_repeat, semantic_assertion

_CORPORA = CALIBRATION_VERSIONS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _judge_meta() -> dict[str, Any]:
    """Judge provenance without any secret value."""
    cfg = _load_judge_cfg()
    return {
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "temperature": cfg.get("temperature"),
        "rpm": cfg.get("rpm"),
        "timeout_seconds": cfg.get("timeout_seconds"),
    }


def _combined_corpus(corpora: list[str]) -> dict[str, Any]:
    """Merge the named corpora into one v7-and-forward case list via the shared loader."""
    return load_combined_calibration(tuple(_CORPORA[name] for name in corpora))


def _repeat_for_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "turns": [
            {"seams": {"question": turn["question"], "answer": turn["answer"]}}
            for turn in case["trajectory"]
        ]
    }


def score_corpora(
    corpora: list[str],
    out_path: Path,
    *,
    rescore: bool = False,
) -> dict[str, Any]:
    """Score every case of the named corpora, persisting after each case."""
    corpus = _combined_corpus(corpora)
    scenarios = {item["id"]: item for item in load_scenarios()}
    scenarios_by_case: dict[str, dict[str, Any]] = {}
    for case in corpus["cases"]:
        scenario = scenarios.get(case["scenario_id"])
        if scenario is None or semantic_assertion(scenario) is None:
            raise ValueError(
                f"case {case['id']} references a scenario with no semantic assertion"
            )
        scenarios_by_case[case["id"]] = scenario

    if out_path.exists() and not rescore:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        results: dict[str, dict[str, Any]] = existing.get("results", {})
        if existing.get("corpus_id") != corpus["corpus_id"]:
            raise ValueError(
                f"{out_path} already holds corpus {existing.get('corpus_id')!r}, "
                f"not {corpus['corpus_id']!r}; use a different --out"
            )
    else:
        results = {}

    artifact: dict[str, Any] = {
        "artifact": "calibration-judge-scores",
        "corpus_id": corpus["corpus_id"],
        "generated_at": _utc_now(),
        "judge": _judge_meta(),
        "results": results,
    }

    def persist() -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    for case in corpus["cases"]:
        recorded = results.get(case["id"])
        usable = (
            isinstance(recorded, dict)
            and recorded.get("status") == AVAILABLE
            and isinstance(recorded.get("score"), (int, float))
        )
        if usable and not rescore:
            continue
        result = evaluate_semantic_repeat(scenarios_by_case[case["id"]], _repeat_for_case(case))
        if result is None:
            raise ValueError(
                f"validated calibration scenario lost its semantic assertion: "
                f"{case['scenario_id']}"
            )
        results[case["id"]] = result.to_dict()
        artifact["generated_at"] = _utc_now()
        persist()

    available = sum(
        1 for item in results.values() if item.get("status") == AVAILABLE
    )
    print(
        json.dumps(
            {
                "corpus_id": corpus["corpus_id"],
                "cases": len(corpus["cases"]),
                "scored": len(results),
                "available": available,
                "unavailable": len(results) - available,
                "out": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return artifact


def build_combined_agreement(scores_path: Path) -> dict[str, Any]:
    """Build the agreement report from a persisted judge-scores artifact."""
    from evals.calibration import build_agreement_report

    corpus = load_combined_calibration()
    data = json.loads(scores_path.read_text(encoding="utf-8"))
    if data.get("corpus_id") != corpus["corpus_id"]:
        raise ValueError(
            f"{scores_path} holds corpus {data.get('corpus_id')!r}, not "
            f"{corpus['corpus_id']!r}"
        )
    return {
        "artifact": "calibration-agreement-report",
        "corpus_id": corpus["corpus_id"],
        "generated_at": _utc_now(),
        "judge": data.get("judge"),
        "policy": (
            "recall-first per class: for each class, the highest sweep threshold "
            "at which that class's recall is 1.0; false passes (precision) are "
            "reported, never traded for recall"
        ),
        **build_agreement_report(corpus, data["results"]),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Score the versioned calibration corpora with the real judge, "
        "or build the agreement report from persisted scores."
    )
    parser.add_argument(
        "--corpus",
        action="append",
        choices=sorted(_CORPORA),
        help="Corpus to score; repeat for more than one (v7 and/or v8).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Judge-scores artifact to write (resumed when present), or agreement "
        "report path in report mode.",
    )
    parser.add_argument(
        "--agreement-of",
        type=Path,
        help="Build the agreement report from this judge-scores artifact instead "
        "of scoring.",
    )
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="Re-measure every case, including previously scored ones.",
    )
    args = parser.parse_args(argv)
    if args.agreement_of is not None:
        _write_json(args.out, build_combined_agreement(args.agreement_of))
        return
    if not args.corpus:
        parser.error("--corpus is required when scoring")
    score_corpora(args.corpus, args.out, rescore=args.rescore)


if __name__ == "__main__":
    main()