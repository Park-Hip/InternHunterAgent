"""Run the evaluation dataset live, score a retained capture offline, or gate v0."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from evals.datasets import dataset, default_dataset_name, list_datasets
from evals.metrics import METRIC_BY_NAME, MetricKind, metric
from evals.report import print_table, to_table_rows
from evals.run import run_dataset, write_report
from evals.v0_gate import GateUnavailable, failed_cases, run_v0_gate


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
        "--deterministic",
        action="store_true",
        help="Gate the governed v0 dataset: no capture, no model, no judge. Fails when the "
        "fixture database is unreachable rather than skipping it.",
    )
    args = parser.parse_args(argv)

    if args.deterministic:
        return _run_gate(args)
    names = args.only.split(",") if args.only else list(METRIC_BY_NAME)
    ids = args.ids.split(",") if args.ids else None
    try:
        report = asyncio.run(run_dataset(dataset(args.dataset), metric_names=names, ids=ids, capture_path=args.capture))
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    write_report(report, args.out)
    print_table(to_table_rows(report["by_metric"]))
    print(f"Report written to {args.out}")
    return _exit_code(report["by_metric"], args.allow_fail)


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
    """The credential-free v0 gate: the core is called directly, not captured."""
    spec = dataset(args.dataset)
    if not spec.is_v0:
        parser_error = "--deterministic only applies to the governed v0 dataset"
        print(parser_error, file=sys.stderr)
        return 2
    ids = args.ids.split(",") if args.ids else None
    try:
        report = run_v0_gate(spec, ids=ids)
    except GateUnavailable as exc:
        # An unavailable database is a failed gate. Reporting it as a pass is the
        # failure mode this gate exists to remove.
        print(f"GATE FAILED: {exc}", file=sys.stderr)
        return 2
    from evals.v0_gate import write_report as write_gate_report

    write_gate_report(report, args.out)
    print_table(to_table_rows(report["by_metric"]))
    print(f"Report written to {args.out}")
    failures = failed_cases(report)
    for scenario_id, metric_name, reason in failures:
        print(f"FAIL {scenario_id} [{metric_name}]: {reason}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
