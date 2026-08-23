"""Score a recorded capture artifact, outside the capture loop.

Capture and scoring have different economics. A full DeepSeek capture is 77 turns
in about five minutes for about four cents; judging the same registry is 365 calls
against a judge deliberately throttled to 8 RPM, so 46 minutes at best. Running the
second inside the first held a five-minute run open for an hour, kept its checkpoint
mid-run for all of it, and made recorded evidence impossible to re-score without
re-capturing it.

So scoring is a pass over the artifact, per D-c and D-f, taking the shape
`evals/grader.py` already has:

    python -m evals.driver --output run.json     # capture, no judge
    python -m evals.score --run run.json         # judge, resumable, re-runnable
    python -m evals.grader --run run.json ...    # deterministic, no model

This module is the only writer of judge scores to Langfuse. It is also the only
place that can post corrected scores after a re-grade, which is what an in-loop
writeback cannot do.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _bind_environment() -> None:
    """Name the environment before the tracing layer reads it at import.

    Scoring never runs the agent, so it needs no database binding. It does need to
    post into the same Langfuse environment the capture traced into, otherwise the
    scores land beside the traces they belong to rather than on them. Set, not
    `setdefault`, for exactly the reason `evals/driver.py` sets it: a developer
    `.env` naming `local` would otherwise win and split the two apart.
    """
    os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = "evaluation"


_bind_environment()

from evals import harness  # noqa: E402
from evals.harness import SCORER_VERSION  # noqa: E402
from evals.semantic import AVAILABLE, evaluate_semantic_repeat, semantic_assertion  # noqa: E402
from evals.scenarios import load_scenarios  # noqa: E402
from evals.writeback import (  # noqa: E402
    count_trace_scores,
    sample_verification_target,
    verify_ingestion,
    write_scores,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _seam_run(turn: dict[str, Any]) -> harness.SeamRun:
    """Rebuild the scored turn from what the capture persisted."""
    seams = turn["seams"]
    return harness.SeamRun(
        question=seams["question"],
        answer=seams["answer"],
        tools_called=seams.get("tools_called") or [],
        tool_output=seams.get("tool_output"),
        sql_text=seams.get("sql_text"),
        trace_id=seams.get("trace_id"),
        telemetry=turn.get("telemetry") or {},
    )


def _has_usable_scores(repeat: dict[str, Any]) -> bool:
    """True only when the judge actually returned a number for something.

    `harness.score` isolates a failing metric by recording `{"score": None,
    "error": ...}`, which is a truthy dict. Treating that as scored would cement a
    429 or a judge JSON hiccup permanently: the repeat would be skipped by every
    later pass, and the only way back would be re-spending the whole registry.
    """
    scores = repeat.get("scores")
    if not scores:
        return False
    return any(
        payload.get("score") is not None
        for metric_scores in scores.values()
        for payload in metric_scores.values()
    )


def _scored_repeats(artifact: dict[str, Any]) -> int:
    return sum(
        1
        for record in artifact["scenarios"].values()
        for repeat in record["repeats"]
        if _has_usable_scores(repeat)
    )


def score_artifact(
    path: Path,
    *,
    scenarios: list[dict[str, Any]] | None = None,
    rescore: bool = False,
) -> dict[str, Any]:
    """Judge every completed repeat in `path`, persisting after each one.

    Resumable and re-runnable by construction (R3.5). A repeat that already carries
    scores from the current scorer is skipped, so an interrupt at judge call 300 of
    365 keeps the 300, and a second pass over a fully scored artifact is a no-op
    rather than an error. `rescore` forces every repeat to be measured again, which
    is how corrected scores reach Langfuse after a re-grade.
    """
    artifact = json.loads(path.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in (scenarios or load_scenarios())}

    summary: dict[str, Any] = {
        "run": str(path),
        "scored": 0,
        "skipped": 0,
        "reposted": 0,
        "unscorable": 0,
        "scores_written": 0,
        "started_at": _utc_now(),
    }

    for scenario_id, record in artifact["scenarios"].items():
        case = cases.get(scenario_id)
        for repeat in record["repeats"]:
            if repeat["status"] != "COMPLETE" or not repeat["turns"]:
                summary["unscorable"] += 1
                continue
            if case is None:
                # The registry no longer carries this scenario, so there is no
                # expectation to judge against. Recorded, never silently skipped.
                repeat["scoring_error"] = "scenario is not in the current registry"
                summary["unscorable"] += 1
                continue
            judged = _has_usable_scores(repeat) and (
                repeat.get("scorer_version") == SCORER_VERSION
            )
            posted = bool(repeat.get("scores_written"))
            semantic_required = semantic_assertion(case) is not None
            semantic_ready = (
                repeat.get("semantic_result", {}).get("status") == AVAILABLE
            )
            if (
                judged
                and posted
                and (not semantic_required or semantic_ready)
                and not rescore
            ):
                summary["skipped"] += 1
                continue

            final_run = _seam_run(repeat["turns"][-1])
            if rescore or not judged:
                repeat["scores"] = harness.score_seams(case, final_run)
                repeat["scorer_version"] = SCORER_VERSION
                repeat["scored_at"] = _utc_now()
                repeat.pop("scoring_error", None)
                summary["scored"] += 1
                # Persisted before the writeback, so an interrupt during a Langfuse
                # call costs the post and not the judge calls that paid for it.
                _write_json(path, artifact)
            else:
                # Judged on an earlier pass whose post never landed. Re-posting is
                # cheap and idempotent; re-judging is 46 minutes of throttled calls.
                summary["reposted"] += 1

            if semantic_required and (rescore or not semantic_ready):
                repeat["semantic_result"] = evaluate_semantic_repeat(
                    case, repeat
                ).to_dict()
                _write_json(path, artifact)

            written = write_scores(final_run.trace_id, repeat["scores"])
            repeat["scores_written"] = written
            summary["scores_written"] += written
            _write_json(path, artifact)

    summary["finished_at"] = _utc_now()
    summary["repeats_with_scores"] = _scored_repeats(artifact)

    manifest = artifact.setdefault("manifest", {})
    # Sampled from the turns rather than read out of `manifest.langfuse_ingestion`:
    # that key is newer than the captures already on disk, and trusting it alone
    # left every artifact recorded before it existed unverifiable at scoring time,
    # which is precisely the set an operator re-scores.
    trace_id, dataset_run_id = sample_verification_target(artifact)
    verified = verify_ingestion(trace_id, dataset_run_id=dataset_run_id)
    verified["checked_at"] = _utc_now()
    manifest["langfuse_ingestion_at_scoring"] = verified
    summary["traces_ingested"] = verified["ingested"]

    # `scores_written` counts what was enqueued; this counts what Langfuse kept.
    # They disagreed once, silently, and the whole pass wrote nothing.
    confirmed = count_trace_scores(trace_id)
    verified["scores_on_sampled_trace"] = confirmed
    summary["scores_on_sampled_trace"] = confirmed

    manifest.setdefault("scoring_passes", []).append(
        {
            key: summary[key]
            for key in (
                "started_at",
                "finished_at",
                "scored",
                "skipped",
                "reposted",
            )
        }
    )
    _write_json(path, artifact)
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Judge a recorded capture artifact and post its scores to Langfuse."
    )
    parser.add_argument(
        "--run", type=Path, required=True, help="Capture artifact to score in place."
    )
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="Measure every completed repeat again, including already-scored ones.",
    )
    args = parser.parse_args(argv)
    if not args.run.exists():
        parser.error(f"No such capture artifact: {args.run}")
    print(json.dumps(score_artifact(args.run, rescore=args.rescore), indent=2))


if __name__ == "__main__":
    main()
