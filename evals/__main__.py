"""Run the evaluation dataset live, score a capture offline, commit or re-score a milestone run, or gate the SQL guard."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import evals.milestone as milestone
from evals.datasets import dataset, default_dataset_name, list_datasets
from evals.metrics import METRIC_BY_NAME, MetricKind, metric
from evals.report import print_table, to_table_rows
from evals.run import run_dataset, write_report
from evals.sql_gate import GateUnavailable, SqlGuardDataset, failed_cases, run_sql_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=list_datasets(), default=default_dataset_name())
    parser.add_argument("--only", help="Comma-separated metric names (default: all)")
    parser.add_argument("--ids", help="Comma-separated dataset IDs")
    parser.add_argument("--capture", type=Path, help="Retained replay JSON for credential-free deterministic scoring")
    parser.add_argument("--out", type=Path, default=Path("evals/runs/report-latest.json"))
    parser.add_argument(
        "--allow-fail",
        action="store_true",
        help="Report scores without turning them into an exit code, for exploratory runs. "
        "A metric that could not be evaluated still fails in every mode: an unevaluated "
        "run must never read as a pass.",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Run the credential-free SQL guard gate: reviewed SQL statements, no "
        "capture, no model, no judge. Fails when the fixture database is unreachable "
        "rather than skipping it.",
    )
    parser.add_argument(
        "--milestone",
        metavar="LABEL",
        help="Also write this run as evals/runs/<date>-<label>/ with a lineage "
        "manifest and the evidence needed to re-score it offline.",
    )
    parser.add_argument(
        "--rescore",
        type=Path,
        metavar="RUN_DIR",
        help="Re-score a committed milestone run from its own evidence and verify "
        "its recorded deterministic scores. Makes no model call.",
    )
    parser.add_argument(
        "--database-url",
        help="Snapshot database for a baseline re-score (default: $BASELINE_DATABASE_URL)",
    )
    args = parser.parse_args(argv)

    if args.gate:
        return _run_gate(args)
    if args.rescore:
        return _run_rescore(args)
    names = args.only.split(",") if args.only else list(METRIC_BY_NAME)
    ids = args.ids.split(",") if args.ids else None
    try:
        report = asyncio.run(run_dataset(dataset(args.dataset), metric_names=names, ids=ids, capture_path=args.capture))
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    if args.milestone:
        try:
            run_dir = milestone.write_agent_run(report, args.milestone)
        except milestone.MilestoneError as exc:
            parser.error(str(exc))
        print(f"Milestone run written to {run_dir}")
    write_report(report, args.out)
    print_table(to_table_rows(report["by_metric"]))
    print(f"Prompt lineage ({report['prompt_versions_source']}): {report['prompt_versions']}")
    print(f"Report written to {args.out}")
    return _exit_code(report["by_metric"], args.allow_fail)


def _run_rescore(args: argparse.Namespace) -> int:
    try:
        result = milestone.rescore(args.rescore, database_url=args.database_url)
    except (milestone.MilestoneError, ValueError, KeyError, OSError) as exc:
        print(f"RESCORE FAILED: {exc}", file=sys.stderr)
        return 2
    print(
        f"Re-scored {result['run_id']} from {result['run_dir']}: "
        f"{result['reproduced_rows']} row(s), {len(result['mismatches'])} mismatch(es)"
    )
    for name in result["skipped_metrics"]:
        print(f"NOT RE-SCORED {name}: a judge call is not reproducible offline")
    for mismatch in result["mismatches"]:
        print(f"MISMATCH {mismatch}", file=sys.stderr)
    return 1 if result["mismatches"] else 0


def _exit_code(by_metric: dict[str, list[dict[str, Any]]], allow_fail: bool) -> int:
    """Turn the report into an exit code. Unavailable evidence always fails.

    Only deterministic metrics carry a threshold. A judge score is continuous in
    [0, 1], so requiring 1.0 of it would fail every run and prove nothing; judge
    metrics stay reported-only until a threshold is configured.
    """
    unevaluated: list[str] = []
    below_threshold: list[str] = []
    for name, rows in by_metric.items():
        gated = metric(name).kind == MetricKind.DETERMINISTIC
        for row in rows:
            label = f"{name}[{row.get('scenario_id')}]"
            if row.get("error") or row.get("reason") == "UNRUN":
                unevaluated.append(label)
            elif gated and row.get("score") != 1.0:
                below_threshold.append(label)
    for label in unevaluated:
        print(f"FAILED {label}: the metric could not be evaluated", file=sys.stderr)
    if unevaluated:
        return 1
    if below_threshold and not allow_fail:
        for label in below_threshold:
            print(f"FAILED {label}: scored below the deterministic threshold", file=sys.stderr)
        return 1
    return 0


def _run_gate(args: argparse.Namespace) -> int:
    """The credential-free SQL guard gate: the reviewed statements are called directly."""
    if args.dataset != default_dataset_name():
        print(
            "--gate scores its own reviewed dataset; --dataset does not apply",
            file=sys.stderr,
        )
        return 2
    ids = args.ids.split(",") if args.ids else None
    try:
        report = run_sql_gate(SqlGuardDataset(), ids=ids)
    except GateUnavailable as exc:
        # An unavailable database is a failed gate. Reporting it as a pass is the
        # failure mode this gate exists to remove.
        print(f"GATE FAILED: {exc}", file=sys.stderr)
        return 2
    from evals.sql_gate import write_report as write_gate_report

    write_gate_report(report, args.out)
    print_table(to_table_rows(report["by_metric"]))
    print(f"Report written to {args.out}")
    failures = failed_cases(report)
    for scenario_id, metric_name, reason in failures:
        print(f"FAIL {scenario_id} [{metric_name}]: {reason}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
