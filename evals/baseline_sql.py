"""Text-to-SQL baseline run for issue #708: generate once, score offline as often as needed.

`generate` sends the first turn of every scored question through the product's own
`generate_sql` (one model call each) and saves the SQL. `score` executes the saved SQL and
the reference SQL against the frozen snapshot and compares the result sets; it makes no
model calls. Follow-up turns need the agent to rewrite them, so the agent run scores them.
`--split dev` keeps the held-out file out of a tuning pass (#761).

    uv run python -m evals.baseline_sql generate --milestone baseline-v1
    uv run python -m evals.baseline_sql generate --split dev --out evals/runs/baseline/dev.json
    uv run python -m evals.baseline_sql score evals/runs/<date>-baseline-v1 \
      --database-url "$BASELINE_DATABASE_URL"

`generate --out <path>` still writes a standalone report, and `score` accepts either a legacy
JSON report or a milestone directory. Re-scoring a milestone run from its own evidence is
`uv run python -m evals --rescore <run dir>` (see `evals/milestone.py`).
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from evals import baseline_dataset, snapshot_manifest
from evals.baseline_config import load_baseline_settings
from evals.sql_check import compare_result_sets, verify_reader_role
from src.agents.runtime.prompts import load_resolved_prompt_versions
from src.agents.tools.query_clean_jobs import generate_sql
from src.core.config import settings
from src.services.query.sql_validator import validate_sql


def verify_snapshot(database_url: str) -> None:
    return snapshot_manifest.verify_snapshot(database_url)


def verify_manifest(database_url: str) -> None:
    return snapshot_manifest.verify_manifest(database_url)

DATASET = baseline_dataset.BASELINE.path
SNAPSHOT_DATE = "2026-10-18"
COMPARE_MODES = baseline_dataset.COMPARE_MODES
_CURRENT_DATE = re.compile(r"\bCURRENT_DATE\b", re.IGNORECASE)


def scored_questions(split: str | None = None) -> list[dict[str, Any]]:
    """Cases whose first turn has a reference SQL.

    ``split`` narrows the list to ``dev`` or ``held-out``. The default covers
    every split, which is what a committed run measures; the how-to uses
    ``dev`` while tuning so the held-out cases stay unread (#761).
    """
    cases = baseline_dataset.scored_cases()
    if split in (None, "all"):
        return cases
    if split not in {"dev", "held-out"}:
        raise ValueError(f"unknown baseline split {split!r}; expected dev or held-out")
    return [case for case in cases if case["split"] == split]


async def generate(
    out: Path | None = None,
    *,
    milestone_label: str | None = None,
    milestone_root: Path | None = None,
    split: str | None = None,
) -> dict[str, Any]:
    # Read the settings first, so a configuration error stops the run before any model call.
    baseline = load_baseline_settings()
    model = settings.agent.deployment_for("sql_generation").model
    records = []
    for repeat in range(1, baseline.layer1_repeats + 1):
        for question in scored_questions(split):
            try:
                sql, error = await generate_sql(question["turns"][0]), None
            except Exception as exc:  # a provider failure is recorded, not fatal
                sql, error = None, f"{type(exc).__name__}: {exc}"
            record = {
                "id": question["id"],
                "question": question["turns"][0],
                "sql": sql,
                "error": error,
            }
            if baseline.layer1_repeats > 1:
                record["repeat"] = repeat
            records.append(record)
            label = f"{question['id']} repeat {repeat}" if baseline.layer1_repeats > 1 else question["id"]
            print(label, "error" if error else "ok", flush=True)
    run = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "prompt_versions": load_resolved_prompt_versions(),
        "repeats": baseline.layer1_repeats,
        "split": split or "all",
        "records": records,
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"saved {len(records)} generations to {out}")
    if milestone_label:
        from evals import milestone

        run_dir = milestone.write_baseline_run(run, milestone_label, root=milestone_root or milestone.RUNS_ROOT)
        print(f"Milestone run written to {run_dir}")
    return run


def score_records(records: list[dict[str, Any]], database_url: str) -> list[dict[str, Any]]:
    """Score generation records against the snapshot; shared by score and rescore.

    The reader-role check comes first: a score made through the owner or a role
    with table-level privilege would not describe the boundary production
    enforces (#760, 5b). A validator rejection is a failure and is never run.
    """
    verify_reader_role(database_url)
    verify_snapshot(database_url)
    questions = {q["id"]: q for q in scored_questions()}
    results = []
    for record in records:
        question = questions[record["id"]]
        result: dict[str, Any] = {
            "id": record["id"],
            "split": question["split"],
            "need": question["need"],
        }
        if "repeat" in record:
            result["repeat"] = record["repeat"]
        if record["sql"] is None:
            result |= {"status": "ERROR", "reason": record["error"]}
        else:
            as_of = question.get("as_of", SNAPSHOT_DATE)
            sql = _CURRENT_DATE.sub(f"DATE '{as_of}'", record["sql"])
            validation = validate_sql(record["sql"])
            result["validator"] = (
                "accepted" if validation.valid else f"rejected: {validation.reason}"
            )
            if not validation.valid:
                result |= {"status": "FAIL", "reason": "validator_rejected"}
            else:
                result |= compare_result_sets(
                    sql,
                    question["reference_sql"][0],
                    database_url,
                    mode=COMPARE_MODES[question["compare"]],
                )
        results.append(result)
    return results


def score(run_path: Path, database_url: str) -> None:
    if run_path.is_dir():
        _score_milestone(run_path, database_url)
        return
    run = json.loads(run_path.read_text(encoding="utf-8"))
    results = score_records(run["records"], database_url)
    out = run_path.with_suffix(".score.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _print_summary(results, out)


def _score_milestone(run_dir: Path, database_url: str) -> None:
    from evals import milestone

    manifest = milestone.read_manifest(run_dir)
    if manifest.get("runner") != milestone.RUNNER_BASELINE_SQL:
        raise ValueError(
            f"{run_dir} is a {manifest.get('runner')!r} run, not a baseline SQL run; "
            "score an agent run with `python -m evals.baseline_agent score`"
        )
    captures = milestone.read_captures(run_dir)
    # A score must describe the evidence the manifest names: refuse an edited
    # capture rather than overwrite the run with scores for different SQL.
    milestone.verify_evidence(manifest, captures, milestone.read_scores(run_dir))
    records = captures.get("records")
    if not isinstance(records, list):
        raise ValueError(f"{run_dir} is not a baseline milestone run")
    results = score_records(records, database_url)
    from evals.reporting import group_by_metric

    by_metric = group_by_metric(_score_rows(results))
    milestone.write_scores(run_dir, metrics=["sql_accuracy"], by_metric=by_metric)
    out = run_dir / milestone.SCORES_NAME
    _print_summary(results, out)


def metric_rows(records: list[dict[str, Any]], database_url: str) -> list[dict[str, Any]]:
    """Score generation records into the generic metric-row shape."""
    return _score_rows(score_records(records, database_url))


def _score_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project baseline rows onto the generic metric-row shape re-scoring compares."""
    rows: list[dict[str, Any]] = []
    detail_keys = (
        "validator",
        "reference_count",
        "actual_count",
        "expected",
        "actual",
        "missing_ids",
        "unexpected_ids",
        "missing_rows",
        "unexpected_rows",
        "reason",
        "error",
    )
    for row in results:
        metric_row: dict[str, Any] = {
            "scenario_id": row["id"],
            "turn": 1,
            "metric": "sql_accuracy",
            "score": (
                1.0
                if row["status"] == "PASS"
                else 0.0
                if row["status"] == "FAIL"
                else None
            ),
            "reason": row["status"] if row["status"] != "PASS" else None,
            "details": {key: row[key] for key in detail_keys if key in row},
            **({"error": row["error"]} if row.get("error") else {}),
        }
        if "repeat" in row:
            metric_row["repeat"] = row["repeat"]
        rows.append(metric_row)
    return rows


def _print_summary(results: list[dict[str, Any]], out: Path) -> None:
    for split in ("dev", "held-out", "safety"):
        rows = [r for r in results if r["split"] == split]
        if not rows:
            continue
        passed = sum(r["status"] == "PASS" for r in rows)
        print(f"{split}: {passed}/{len(rows)} pass ({passed / len(rows):.0%})")
    print("statuses:", dict(Counter(r["status"] for r in results)))
    for r in results:
        if r["status"] != "PASS":
            detail = {k: r[k] for k in ("reason", "error", "reference_count", "actual_count", "expected", "actual") if k in r}
            print(f"  {r['id']} {r['status']} {detail}")
    print(f"details in {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    generating = commands.add_parser("generate")
    generating.add_argument("--out", type=Path)
    generating.add_argument(
        "--milestone", metavar="LABEL",
        help="write evals/runs/<date>-<label>/ with a lineage manifest",
    )
    generating.add_argument(
        "--split",
        choices=("dev", "held-out", "all"),
        default="all",
        help=(
            "score only one split (default: all). Use dev while tuning; "
            "held-out is measured at a milestone (#761)"
        ),
    )
    scoring = commands.add_parser("score")
    scoring.add_argument("run", type=Path, help="a legacy run JSON or a milestone run directory")
    scoring.add_argument(
        "--database-url", default=os.environ.get("BASELINE_DATABASE_URL"),
        help="read-only URL of the frozen snapshot (default: $BASELINE_DATABASE_URL)",
    )
    args = parser.parse_args()
    if args.command == "generate":
        if not args.out and not args.milestone:
            parser.error("generate needs --out or --milestone")
        asyncio.run(generate(args.out, milestone_label=args.milestone, split=args.split))
        return
    if not args.database_url:
        parser.error("score needs --database-url or BASELINE_DATABASE_URL")
    try:
        score(args.run, args.database_url)
    except (snapshot_manifest.SnapshotMismatch, OSError, ValueError) as exc:
        parser.exit(2, f"SCORE FAILED: {exc}\n")


if __name__ == "__main__":
    main()
