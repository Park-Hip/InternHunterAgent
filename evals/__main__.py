"""Run the evaluation dataset live, or score a retained capture offline."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from evals.datasets import dataset, default_dataset_name, list_datasets
from evals.metrics import METRIC_BY_NAME
from evals.report import print_table, to_table_rows
from evals.run import run_dataset, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=list_datasets(), default=default_dataset_name())
    parser.add_argument("--only", help="Comma-separated metric names (default: all)")
    parser.add_argument("--ids", help="Comma-separated dataset IDs")
    parser.add_argument("--capture", type=Path, help="Retained replay JSON for credential-free deterministic scoring")
    parser.add_argument("--out", type=Path, default=Path("evals/runs/report-latest.json"))
    parser.add_argument("--require-pass", action="store_true", help="Fail if any selected metric scores below 1")
    args = parser.parse_args(argv)
    names = args.only.split(",") if args.only else list(METRIC_BY_NAME)
    ids = args.ids.split(",") if args.ids else None
    try:
        report = asyncio.run(run_dataset(dataset(args.dataset), metric_names=names, ids=ids, capture_path=args.capture))
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    write_report(report, args.out)
    print_table(to_table_rows(report["by_metric"]))
    print(f"Report written to {args.out}")
    rows = [row for metric_rows in report["by_metric"].values() for row in metric_rows]
    return 1 if any(row.get("error") or row.get("reason") == "UNRUN" or (args.require_pass and row.get("score") != 1.0) for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
