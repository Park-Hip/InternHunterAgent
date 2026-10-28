"""Gate the SQL guard, re-score a committed run, or diff two committed runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import evals.milestone as milestone
import evals.regression as regression
from evals.reporting import print_table, to_table_rows
from evals.snapshot_manifest import SnapshotMismatch
from evals.sql_gate import GateUnavailable, SqlGuardDataset, failed_cases, run_sql_gate, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated case IDs for the SQL guard gate")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("evals/runs/sql-gate-latest.json"),
        help="Where to write the gate report (default: a gitignored local file)",
    )
    parser.add_argument(
        "--rescore",
        type=Path,
        metavar="RUN_DIR",
        help="Re-score a committed milestone run from its own evidence and verify "
        "its recorded scores. Makes no model call.",
    )
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("BASELINE_RUN", "CANDIDATE_RUN"),
        help="Print the per-question diff between two committed milestone runs "
        "and check the absolute floors.",
    )
    parser.add_argument(
        "--explained",
        metavar="IDS",
        help="Comma-separated question IDs the pull request explains; they are "
        "printed but do not block the diff.",
    )
    parser.add_argument(
        "--database-url",
        help="Snapshot database for a baseline re-score (default: $BASELINE_DATABASE_URL)",
    )
    args = parser.parse_args(argv)

    if args.diff and args.rescore:
        parser.error("choose one of --diff or --rescore")
    if args.diff and args.ids:
        parser.error("--ids applies only to the SQL guard gate")
    if args.explained and not args.diff:
        parser.error("--explained is only meaningful with --diff")
    if args.diff:
        return _run_diff(args)
    if args.rescore:
        return _run_rescore(args)
    return _run_gate(args)


def _run_gate(args: argparse.Namespace) -> int:
    """The credential-free SQL guard gate: the reviewed statements are called directly."""
    ids = args.ids.split(",") if args.ids else None
    try:
        report = run_sql_gate(SqlGuardDataset(), ids=ids)
    except ValueError as exc:
        print(f"GATE FAILED: {exc}", file=sys.stderr)
        return 2
    except GateUnavailable as exc:
        # An unavailable database is a failed gate. Reporting it as a pass is the
        # failure mode this gate exists to remove.
        print(f"GATE FAILED: {exc}", file=sys.stderr)
        return 2

    write_report(report, args.out)
    print_table(to_table_rows(report["by_metric"]))
    print(f"Report written to {args.out}")
    failures = failed_cases(report)
    for scenario_id, metric_name, reason in failures:
        print(f"FAIL {scenario_id} [{metric_name}]: {reason}", file=sys.stderr)
    return 1 if failures else 0


def _run_diff(args: argparse.Namespace) -> int:
    try:
        report = regression.run_diff(
            Path(args.diff[0]),
            Path(args.diff[1]),
            explained=[args.explained] if args.explained else (),
        )
    except (
        milestone.MilestoneError,
        regression.RegressionError,
        SnapshotMismatch,
        ValueError,
        KeyError,
        OSError,
    ) as exc:
        print(f"DIFF FAILED: {exc}", file=sys.stderr)
        return 2
    regression.print_report(report)
    return 1 if report["blocked"] else 0


def _run_rescore(args: argparse.Namespace) -> int:
    try:
        result = milestone.rescore(args.rescore, database_url=args.database_url)
    except (milestone.MilestoneError, SnapshotMismatch, ValueError, KeyError, OSError) as exc:
        print(f"RESCORE FAILED: {exc}", file=sys.stderr)
        return 2
    print(
        f"Re-scored {result['run_id']} ({result['runner']}) from "
        f"{result['run_dir']}: {result['reproduced_rows']} row(s), "
        f"{len(result['mismatches'])} mismatch(es)"
    )
    for name in result["skipped_metrics"]:
        print(f"NOT RE-SCORED {name}: not a deterministic metric for this runner")
    for mismatch in result["mismatches"]:
        print(f"MISMATCH {mismatch}", file=sys.stderr)
    return 1 if result["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
