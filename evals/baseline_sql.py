"""Text-to-SQL baseline run for issue #708: generate once, score offline as often as needed.

`generate` sends the first turn of every scored question through the product's own
`generate_sql` (one model call each) and saves the SQL. `score` executes the saved SQL and
the reference SQL against the frozen snapshot and compares the result sets; it makes no
model calls. Follow-up turns need the agent to rewrite them, so the agent run scores them.

    uv run python -m evals.baseline_sql generate --out evals/runs/baseline/<name>.json
    uv run python -m evals.baseline_sql score evals/runs/baseline/<name>.json
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

from evals.sql_check import compare_result_sets
from src.agents.runtime.prompts import load_resolved_prompt_versions
from src.agents.tools.query_clean_jobs import generate_sql
from src.core.config import settings
from src.services.query.sql_validator import validate_sql

DATASET = Path(__file__).parent / "datasets" / "baseline.yaml"
SNAPSHOT_DATE = "2026-10-18"
COMPARE_MODES = {"ids": "ids_only", "count": "aggregate_count", "rows": "rows_equal"}
_CURRENT_DATE = re.compile(r"\bCURRENT_DATE\b", re.IGNORECASE)


def scored_questions() -> list[dict[str, Any]]:
    """Questions whose first turn has a reference SQL."""
    questions = yaml.safe_load(DATASET.read_text(encoding="utf-8"))
    return [q for q in questions if q["reference_sql"] and q["reference_sql"][0]]


async def generate(out: Path) -> None:
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
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {len(records)} generations to {out}")


def score(run_path: Path, database_url: str) -> None:
    run = json.loads(run_path.read_text(encoding="utf-8"))
    questions = {q["id"]: q for q in scored_questions()}
    results = []
    for record in run["records"]:
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

    out = run_path.with_suffix(".score.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
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
    commands.add_parser("generate").add_argument("--out", type=Path, required=True)
    scoring = commands.add_parser("score")
    scoring.add_argument("run", type=Path)
    scoring.add_argument(
        "--database-url", default=os.environ.get("BASELINE_DATABASE_URL"),
        help="read-only URL of the frozen snapshot (default: $BASELINE_DATABASE_URL)",
    )
    args = parser.parse_args()
    if args.command == "generate":
        asyncio.run(generate(args.out))
    else:
        if not args.database_url:
            parser.error("score needs --database-url or BASELINE_DATABASE_URL")
        score(args.run, args.database_url)


if __name__ == "__main__":
    main()
