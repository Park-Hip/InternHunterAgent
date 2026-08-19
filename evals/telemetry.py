"""Aggregate provider telemetry from a recorded evaluation capture.

This module is deliberately offline. It reads the per-turn telemetry written by
``evals.driver`` and never constructs a provider client.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / "config" / "settings.yaml"


def _percentile(values: Iterable[int], percentile: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _numeric(values: Iterable[Any]) -> list[int]:
    return [value for value in values if isinstance(value, int) and not isinstance(value, bool)]


def _metric(values: Iterable[int]) -> dict[str, int | float | None]:
    values = list(values)
    return {
        "count": len(values),
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
        "total": sum(values),
    }


def _pricing(provider: str) -> tuple[float, float]:
    settings = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8")) or {}
    prices = ((settings.get("eval") or {}).get("telemetry") or {}).get("prices") or {}
    price = prices.get(provider)
    if not isinstance(price, dict):
        raise ValueError(f"Missing eval.telemetry.prices.{provider} in config/settings.yaml")
    input_price = price.get("input_usd_per_million")
    output_price = price.get("output_usd_per_million")
    if not isinstance(input_price, (int, float)) or not isinstance(output_price, (int, float)):
        raise ValueError(f"Invalid telemetry pricing for provider {provider}")
    return float(input_price), float(output_price)


def _turns(capture: dict[str, Any]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for scenario in capture.get("scenarios", {}).values():
        for repeat in scenario.get("repeats", []):
            for turn in repeat.get("turns", []):
                if turn.get("status") == "COMPLETE" and isinstance(turn.get("telemetry"), dict):
                    turns.append(turn)
    return turns


def aggregate_capture(capture: dict[str, Any], *, measured_at: str | None = None) -> dict[str, Any]:
    """Return dated, provenance-stamped latency, usage, and cost metrics."""
    manifest = capture.get("manifest") or {}
    providers = manifest.get("providers") or {}
    provider_names = sorted({value for value in providers.values() if isinstance(value, str)})
    provider = manifest.get("provider") or (provider_names[0] if len(provider_names) == 1 else "unknown")
    input_price, output_price = _pricing(provider)
    turns = _turns(capture)
    latencies = _numeric(turn["telemetry"].get("latency_ms") for turn in turns)
    input_tokens = _numeric(
        turn["telemetry"].get("provider_token_usage", {}).get("aggregate", {}).get("input_tokens")
        for turn in turns
    )
    output_tokens = _numeric(
        turn["telemetry"].get("provider_token_usage", {}).get("aggregate", {}).get("output_tokens")
        for turn in turns
    )
    total_tokens = _numeric(
        turn["telemetry"].get("provider_token_usage", {}).get("aggregate", {}).get("total_tokens")
        for turn in turns
    )
    input_total = sum(input_tokens)
    output_total = sum(output_tokens)
    cost_usd = input_total * input_price / 1_000_000 + output_total * output_price / 1_000_000
    return {
        "measured_at": measured_at or datetime.now(timezone.utc).date().isoformat(),
        "source_capture": manifest.get("run_id"),
        "prompt_version": manifest.get("prompt_version"),
        "provider": provider,
        "turns": {
            "count": len(turns),
            "latency_ms": _metric(latencies),
            "input_tokens": _metric(input_tokens),
            "output_tokens": _metric(output_tokens),
            "total_tokens": _metric(total_tokens),
        },
        "cost": {
            "input_usd_per_million": input_price,
            "output_usd_per_million": output_price,
            "input_tokens": input_total,
            "output_tokens": output_total,
            "usd": round(cost_usd, 6),
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Aggregate recorded evaluation telemetry offline.")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", "-o", type=Path)
    args = parser.parse_args(argv)
    report = aggregate_capture(json.loads(args.capture.read_text(encoding="utf-8")))
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
