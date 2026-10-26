"""Text-to-SQL baseline run for issue #708: generate once, score offline as often as needed.

`generate` sends the first turn of every scored question through the product's own
`generate_sql` (one model call each) and saves the SQL. `score` executes the saved SQL and
the reference SQL against the frozen snapshot and compares the result sets; it makes no
model calls. Follow-up turns need the agent to rewrite them, so the agent run scores them.

    uv run python -m evals.baseline_sql generate --milestone baseline-v1
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

import yaml

from evals import snapshot_manifest
from evals.sql_check import compare_result_sets
from src.agents.runtime.prompts import load_resolved_prompt_versions
from src.agents.tools.query_clean_jobs import generate_sql
from src.core.config import settings
from src.services.query.sql_validator import validate_sql


def verify_snapshot(database_url: str) -> None:
    return snapshot_manifest.verify_snapshot(database_url)


def verify_manifest(database_url: str) -> None:
    return snapshot_manifest.verify_manifest(database_url)

DATASET = Path(__file__).parent / "datasets" / "baseline.yaml"
SNAPSHOT_DATE = "2026-10-18"
COMPARE_MODES = {"ids": "ids_only", "count": "aggregate_count", "rows": "rows_equal"}
_CURRENT_DATE = re.compile(r"\bCURRENT_DATE\b", re.IGNORECASE)


def scored_questions() -> list[dict[str, Any]]:
    """Questions whose first turn has a reference SQL."""
    questions = yaml.safe_load(DATASET.read_text(encoding="utf-8"))
    return [q for q in questions if q["reference_sql"] and q["reference_sql"][0]]


async def generate(
    out: Path | None = None,
    *,
    milestone_label: str | None = None,
    milestone_root: Path | None = None,
) -> dict[str, Any]:
    # Read the settings first, so a configuration error stops the run before any model call.
    model = settings.agent.deployment_for("sql_generation").model
    records = []
    for question in scored_questions():
        try:
            sql, error = await generate_sql(question["turns"][0]), None
        except Exception as exc:  # a provider failure is recorded, not fatal
            sql, error = None, f"{type(exc).__name__}: {exc}"
        records.append({"id": question["id"], "question": question["turns"][0], "sql": sql, "error": error})
        print(question["id"], "error" if error else "ok", flush=True)
    run = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "prompt_versions": load_resolved_prompt_versions(),
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
    """Score generation records against the snapshot; shared by score and rescore."""
    verify_snapshot(database_url)
    questions = {q["id"]: q for q in scored_questions()}
    results = []
    for record in records:
        question = questions[record["id"]]
        result: dict[str, Any] = {"id": record["id"], "split": question["split"], "need": question["need"]}
        if record["sql"] is None:
            result |= {"status": "ERROR", "reason": record["error"]}
        else:
            as_of = question.get("as_of", SNAPSHOT_DATE)
            sql = _CURRENT_DATE.sub(f"DATE '{as_of}'", record["sql"])
            validation = validate_sql(record["sql"])
            result["validator"] = "accepted" if validation.valid else f"rejected: {validation.reason}"
            result |= compare_result_sets(
                sql, question["reference_sql"][0], database_url,
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
    captures = milestone.read_captures(run_dir)
    # A score must describe the evidence the manifest names: refuse an edited
    # capture rather than overwrite the run with scores for different SQL.
    milestone.verify_evidence(manifest, captures, milestone.read_scores(run_dir))
    records = captures.get("records")
    if not isinstance(records, list):
        raise ValueError(f"{run_dir} is not a baseline milestone run")
    results = score_records(records, database_url)
    from evals.report import group_by_metric

    by_metric = group_by_metric(_score_rows(results))
    milestone.write_scores(run_dir, metrics=["sql_accuracy"], by_metric=by_metric)
    out = run_dir / milestone.SCORES_NAME
    _print_summary(results, out)


def metric_rows(records: list[dict[str, Any]], database_url: str) -> list[dict[str, Any]]:
    """Score generation records into the generic metric-row shape."""
    return _score_rows(score_records(records, database_url))


def _score_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project baseline rows onto the generic metric-row shape re-scoring compares."""
    return [
        {
            "scenario_id": row["id"],
            "turn": 1,
            "metric": "sql_accuracy",
            "score": 1.0 if row["status"] == "PASS" else 0.0 if row["status"] == "FAIL" else None,
            "reason": row["status"] if row["status"] != "PASS" else None,
            "details": {key: row[key] for key in ("validator", "reference_count", "actual_count", "expected", "actual", "missing_ids", "unexpected_ids", "missing_rows", "unexpected_rows", "reason", "error") if key in row},
            **({"error": row["error"]} if row.get("error") else {}),
        }
        for row in results
    ]


def _print_summary(results: list[dict[str, Any]], out: Path) -> None:
    for split in ("dev", "held-out"):
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
        asyncio.run(generate(args.out, milestone_label=args.milestone))
        return
    if not args.database_url:
        parser.error("score needs --database-url or BASELINE_DATABASE_URL")
    score(args.run, args.database_url)


if __name__ == "__main__":
    main()
