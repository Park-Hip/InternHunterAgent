"""Generate a local, single-file viewer for scenario-driver trace records."""

from __future__ import annotations

import argparse
import ast
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from evals._paths import ROOT

# Sampling knobs that the viewer treats as first-class (displayed before dynamic knobs).
# New knobs that deserve this status should be added here; otherwise they fall through.
def _fixed_sampling_keys() -> tuple[str, ...]:
    from src.core.config import settings
    cfg = (settings.config_yaml.get("eval") or {}).get("viewer")
    if isinstance(cfg, dict):
        keys = cfg.get("fixed_sampling_keys")
        if isinstance(keys, list) and all(isinstance(k, str) for k in keys):
            return tuple(keys)
    return ("temperature", "max_tokens")


_FIXED_SAMPLING = _fixed_sampling_keys()

# `query_clean_jobs` returns prose, not a Python literal: a header naming the
# columns, then one `- col=value, col=value` line per row (see
# `src/agents/tools/query_clean_jobs.py::_build_answer`). Both the "Found N
# result(s) with columns: ..." header and the truncated "... Columns: ..."
# header end the same way, so one pattern covers both.
_COLUMNS_PATTERN = re.compile(r"columns:\s*(.+?)\.\s*$", re.IGNORECASE)

# Which seam a grader check judges, so a verdict is read beside the evidence that
# produced it rather than in a list of its own. Names come from
# `evals/grader.py::_structural_checks`, `_text_checks`, and `_judge_checks`.
# `required_substance_N` is numbered per rule, so it is matched by prefix.
_CHECK_SEAMS = {
    "tools_recorded": "routing",
    "no_tool_called": "routing",
    "required_tool_called": "routing",
    "execution_accuracy": "sql",
    "answer_present": "answer",
    "answer_count": "answer",
    "no_single_cross_currency_winner": "answer",
    "forbidden_phrase_absent": "answer",
    "forbidden_pattern_absent": "answer",
    "judge_metric": "answer",
}
_CHECK_SEAM_PREFIXES = (("required_substance_", "answer"),)

# Seam keys `evals/harness.py::score_seams` persists under `repeat["scores"]`, and
# the on-screen seam each one judged. The judge shares these three seams with the
# deterministic grader, so its output is read beside the same evidence.
_JUDGE_SEAMS = {
    "seam1_routing": "routing",
    "seam2_nl_to_sql": "sql",
    "seam3_synthesis": "answer",
}



def _text(value: Any, empty: str = "Not captured") -> str:
    if value is None or value == "":
        return empty
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _cell(value: Any) -> str:
    return "null" if value is None else _text(value)


def _split_row(line: str, columns: list[str]) -> list[str] | None:
    """Split one `col=value, col=value` row using the header's column names.

    Values carry free text that can contain both ", " and "=", so the split is
    anchored on the known column names rather than on the separators.
    """
    starts: list[tuple[int, int]] = []
    cursor = 0
    for index, column in enumerate(columns):
        token = f"{column}=" if index == 0 else f", {column}="
        position = line.find(token, cursor)
        if position < 0:
            return None
        starts.append((position, len(token)))
        cursor = position + len(token)
    return [
        line[position + width : (starts[index + 1][0] if index + 1 < len(starts) else len(line))]
        for index, (position, width) in enumerate(starts)
    ]


def _parse_tool_answer(text: str) -> dict[str, Any] | None:
    """Parse the tool's real prose output into the viewer's table model."""
    lines = text.splitlines()
    if not lines:
        return None
    match = _COLUMNS_PATTERN.search(lines[0].strip())
    if match is None:
        return None
    columns = [column.strip() for column in match.group(1).split(",") if column.strip()]
    if not columns:
        return None
    rows: list[list[str]] = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        values = _split_row(stripped[2:], columns)
        if values is None:
            return None
        rows.append(values)
    # The header carries any truncation caveat, which the operator needs in order
    # to judge seam 3's honesty, so it travels with the table instead of being
    # dropped once the rows are parsed out.
    return {"kind": "table", "count": len(rows), "headers": columns, "rows": rows, "note": lines[0].strip()}


def _rows(value: Any) -> dict[str, Any]:
    """Convert common tool-output shapes into a compact table model for the viewer."""
    parsed = value
    if isinstance(value, str):
        table = _parse_tool_answer(value)
        if table is not None:
            return table
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return {"kind": "text", "text": value}
    if not isinstance(parsed, (list, tuple)):
        return {"kind": "text", "text": _text(value)}

    rows = list(parsed)
    if rows and all(isinstance(row, dict) for row in rows):
        headers = list(dict.fromkeys(key for row in rows for key in row))
        values = [[_cell(row.get(header)) for header in headers] for row in rows]
    else:
        values = [[_cell(cell) for cell in row] if isinstance(row, (list, tuple)) else [_cell(row)] for row in rows]
        width = max((len(row) for row in values), default=0)
        headers = [f"Column {index}" for index in range(1, width + 1)]
        values = [row + [""] * (width - len(row)) for row in values]
    return {"kind": "table", "count": len(values), "headers": headers, "rows": values}


def _setting(value: Any) -> str:
    """Render a manifest setting, distinguishing "not set" from a recorded value."""
    return "not recorded" if value is None else _text(value)


def _prompt_lineage(manifest: dict[str, Any]) -> str:
    """Render named lineage while retaining readable historical aggregate stamps."""
    prompt_versions = manifest.get("prompt_versions")
    if isinstance(prompt_versions, dict) and prompt_versions:
        return ", ".join(
            f"{surface}: {version}"
            for surface, version in sorted(prompt_versions.items())
        )
    return _setting(manifest.get("prompt_version"))


def _scenario_outcome(manifest: dict[str, Any]) -> str:
    """Say how much of the registry succeeded, since the capture status no longer does.

    The screen shows `Capture: COMPLETE`, which after R6.1 means the run reached the
    end of the registry rather than that every scenario in it passed. Without this
    row a capture that survived a 429 is indistinguishable from a clean one.
    """
    counts = manifest.get("scenario_status_counts")
    if not isinstance(counts, dict) or not counts:
        return _setting(None)
    order = ["COMPLETE", "INFRA", "UNRUN"]
    keys = [key for key in order if key in counts]
    keys += sorted(key for key in counts if key not in order)
    return ", ".join(f"{counts[key]} {key}" for key in keys)


def _seam_for_check(name: str) -> str:
    """Name the seam a check judges; scenario-level checks judge the run itself."""
    if name in _CHECK_SEAMS:
        return _CHECK_SEAMS[name]
    for prefix, seam in _CHECK_SEAM_PREFIXES:
        if name.startswith(prefix):
            return seam
    return "run"


def index_grades(grade: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index a grader report by the viewer's `scenario/repeat/turn` key.

    Scenario- and repeat-level verdicts (`UNRUN`, `INFRA`) carry no turn number
    because they judge a turn that was never captured, so they join to nothing here.
    """
    index: dict[str, dict[str, Any]] = {}
    for scenario_id, entries in (grade or {}).get("scenarios", {}).items():
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("repeat") is None or entry.get("turn") is None:
                continue
            index[f"{scenario_id}/{entry['repeat']}/{entry['turn']}"] = entry
    return index


def index_execution_results(report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index execution evidence by the same scenario/repeat/turn key as grades."""
    index: dict[str, dict[str, Any]] = {}
    for scenario_id, repeats in (report or {}).get("scenarios", {}).items():
        if not isinstance(repeats, list):
            continue
        for repeat in repeats:
            if not isinstance(repeat, dict):
                continue
            for turn_number, result in enumerate(repeat.get("turns", []), start=1):
                if isinstance(result, dict):
                    index[f"{scenario_id}/{repeat.get('repeat')}/{turn_number}"] = result
    return index


def _coverage_state(
    *, turn_status: Any, configured: bool | None, applicable: bool, captured: bool
) -> str:
    """Keep missing evidence states distinct instead of treating all as absent."""
    if turn_status != "COMPLETE":
        return "CAPTURE_FAILED"
    if not applicable:
        return "NOT_APPLICABLE"
    if configured is False or configured is None:
        return "NOT_CONFIGURED"
    return "CAPTURED" if captured else "PROVIDER_DID_NOT_EMIT"


def _evidence_coverage(
    turn_record: dict[str, Any], seams: dict[str, Any], manifest: dict[str, Any]
) -> list[list[str]]:
    telemetry = turn_record.get("telemetry")
    tracing = manifest.get("tracing")
    tracing = tracing if isinstance(tracing, dict) else {}
    tools = seams.get("tools_called")
    tools = tools if isinstance(tools, list) else []
    return [
        [
            "Trace linkage",
            _coverage_state(
                turn_status=turn_record.get("status"),
                configured=tracing.get("langfuse_enabled"),
                applicable=True,
                captured=bool(seams.get("trace_id")),
            ),
        ],
        [
            "Tool arguments",
            _coverage_state(
                turn_status=turn_record.get("status"),
                configured=True,
                applicable=bool(tools),
                captured=isinstance(seams.get("tool_arguments"), list),
            ),
        ],
        [
            "Per-call telemetry",
            _coverage_state(
                turn_status=turn_record.get("status"),
                configured=isinstance(telemetry, dict),
                applicable=True,
                captured=bool(
                    isinstance(telemetry, dict)
                    and isinstance(telemetry.get("provider_token_usage"), dict)
                    and telemetry["provider_token_usage"].get("calls")
                ),
            ),
        ],
    ]


def _checks(grade: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return the checks that did not pass, tagged with the seam each one judges.

    The grader distinguishes unavailable evidence from a check that did not apply.
    Preserve that distinction in the viewer instead of deriving a label from
    `passed`, because both states use `None` for that field.
    """
    return [
        {
            "name": str(check.get("name", "unnamed check")),
            "detail": _text(check.get("detail"), "No detail recorded"),
            "tier": str(check.get("tier", "unknown")),
            "outcome": str(
                check.get(
                    "outcome",
                    "FAILED" if check.get("passed") is False else "UNAVAILABLE",
                )
            ),
            "seam": _seam_for_check(str(check.get("name", ""))),
        }
        for check in (grade or {}).get("checks", [])
        if isinstance(check, dict) and check.get("passed") is not True
    ]


def _telemetry(record: Any) -> dict[str, Any]:
    """Split the turn's telemetry into labelled fields instead of one JSON blob."""
    if not isinstance(record, dict):
        return {"available": False}
    usage = record.get("provider_token_usage")
    usage = usage if isinstance(usage, dict) else {}
    aggregate = usage.get("aggregate")
    aggregate = aggregate if isinstance(aggregate, dict) else {}
    calls = [call for call in usage.get("calls", []) if isinstance(call, dict)]
    finish_reasons = record.get("finish_reasons")
    return {
        "available": True,
        "latency_ms": _setting(record.get("latency_ms")),
        "input_tokens": _setting(aggregate.get("input_tokens")),
        "output_tokens": _setting(aggregate.get("output_tokens")),
        "total_tokens": _setting(aggregate.get("total_tokens")),
        "finish_reasons": ", ".join(map(str, finish_reasons)) if isinstance(finish_reasons, list) and finish_reasons else _setting(finish_reasons),
        "calls": [
            [
                str(number),
                _setting(call.get("input_tokens")),
                _setting(call.get("output_tokens")),
                _setting(call.get("total_tokens")),
                _setting(call.get("finish_reason")),
            ]
            for number, call in enumerate(calls, start=1)
        ],
    }


def run_header(manifest: dict[str, Any]) -> dict[str, Any]:
    """Describe what produced this capture: provider and sampling per profile.

    Two arms of the same scenario set are only comparable if the screen can say what
    each one ran, which is why `providers` is in the manifest (T0027.2).
    """
    providers = manifest.get("providers") if isinstance(manifest.get("providers"), dict) else {}
    models = manifest.get("models") if isinstance(manifest.get("models"), dict) else {}
    sampling = manifest.get("sampling") if isinstance(manifest.get("sampling"), dict) else {}
    profiles = list(dict.fromkeys([*providers, *models, *sampling]))
    knobs = [
        key
        for key in dict.fromkeys(k for profile in profiles for k in (sampling.get(profile) or {}))
        if key not in _FIXED_SAMPLING
    ]
    rows = []
    for profile in profiles:
        knob_values = sampling.get(profile) or {}
        rows.append(
            [
                profile,
                _setting(providers.get(profile)),
                _setting(models.get(profile)),
                _setting(knob_values.get("temperature")),
                _setting(knob_values.get("max_tokens")),
                *(_setting(knob_values.get(knob)) for knob in knobs),
            ]
        )
    return {
        "headers": ["Profile", "Provider", "Model", "Temperature", "Max tokens", *(knob.replace("_", " ").capitalize() for knob in knobs)],
        "rows": rows,
        "facts": [
            ["Git SHA", _setting(manifest.get("git_sha"))],
            ["Prompt lineage", _prompt_lineage(manifest)],
            ["Baseline eligible", _setting(manifest.get("baseline_eligible"))],
            ["Scenarios", _scenario_outcome(manifest)],
        ],
    }


def _normalize_judge_scores(repeat: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten persisted `repeat["scores"]` into informational, per-seam entries.

    `harness.score` isolates one failing metric as `{"score": None, "error": ...}` so
    a broken judge call reads as unavailable rather than a score of zero, and the
    rest of the seam's scores survive. Only the three seams `score_seams` emits are
    kept, because those are the seams this viewer places beside their evidence.
    """
    scores = repeat.get("scores")
    if not isinstance(scores, dict) or not scores:
        return []
    entries: list[dict[str, Any]] = []
    for seam_name, metric_scores in scores.items():
        seam = _JUDGE_SEAMS.get(seam_name)
        if seam is None or not isinstance(metric_scores, dict):
            continue
        metrics: list[dict[str, Any]] = []
        for metric_name, payload in metric_scores.items():
            payload = payload if isinstance(payload, dict) else {}
            score = payload.get("score")
            scored = isinstance(score, (int, float)) and not isinstance(score, bool)
            metrics.append(
                {
                    "name": str(metric_name),
                    "score": score if scored else None,
                    "available": scored,
                    "reason": _text(payload.get("reason"), ""),
                    "error": _text(payload.get("error"), ""),
                }
            )
        entries.append({"seam": seam, "metrics": metrics})
    return entries


def _normalize_semantic_result(repeat: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize the optional repeat-level semantic verdict for display.

    A result exists only when the scenario declares a semantic assertion. `status`
    keeps an available score apart from a provider failure the operator may re-run,
    so the viewer never implies a deterministic verdict from this diagnostic.
    """
    result = repeat.get("semantic_result")
    if not isinstance(result, dict) or not result:
        return None
    score = result.get("score")
    confidence = result.get("confidence")
    return {
        "status": str(result.get("status", "UNAVAILABLE")),
        "available": result.get("status") == "AVAILABLE",
        "score": (
            score
            if isinstance(score, (int, float)) and not isinstance(score, bool)
            else None
        ),
        "confidence": (
            confidence
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
            else None
        ),
        "rationale": _text(result.get("rationale"), ""),
    }


def flatten_turns(
    run: dict[str, Any],
    scenarios: list[dict[str, Any]] | None = None,
    grade: dict[str, Any] | None = None,
    execution_accuracy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Turn the driver's nested artifact into records suitable for the browser."""
    scenario_index = {scenario["id"]: scenario for scenario in scenarios or []}
    grades = index_grades(grade)
    execution = index_execution_results(execution_accuracy)
    manifest = run.get("manifest") if isinstance(run.get("manifest"), dict) else {}
    turns: list[dict[str, Any]] = []
    for scenario_id, scenario_record in run.get("scenarios", {}).items():
        for repeat_record in scenario_record.get("repeats", []):
            judge_scores = _normalize_judge_scores(repeat_record)
            semantic_result = _normalize_semantic_result(repeat_record)
            repeat_turns = repeat_record.get("turns", [])
            for turn_index, turn_record in enumerate(repeat_turns):
                is_final_turn = bool(repeat_turns) and turn_index == len(repeat_turns) - 1
                seams = turn_record.get("seams", {})
                tools = seams.get("tools_called", [])
                key = f"{scenario_id}/{repeat_record.get('repeat', '?')}/{turn_record.get('turn', '?')}"
                turn_grade = grades.get(key)
                execution_result = execution.get(key)
                scenario = scenario_index.get(scenario_id, {})
                turns.append(
                    {
                        "key": key,
                        "scenario_id": scenario_id,
                        "scenario_name": scenario.get("name", scenario_id),
                        "repeat": repeat_record.get("repeat"),
                        "turn": turn_record.get("turn"),
                        "status": turn_record.get("status", "UNKNOWN"),
                        # Capture status and grade status answer different questions -
                        # "was the turn recorded" against "was the behavior right" - so
                        # they are named apart and never collapsed into one field.
                        "grade_status": str(turn_grade.get("status", "UNKNOWN")) if turn_grade else "UNGRADED",
                        "grade_tier": _cell(turn_grade.get("tier")) if turn_grade else "No grade file joined",
                        "checks": _checks(turn_grade),
                        "question": _text(seams.get("question")),
                        "routing": ", ".join(map(str, tools)) if tools else "No tool call captured",
                        "expected_tools": ", ".join(map(str, scenario.get("expected_tools", []))) or "No exact tool expectation recorded",
                        "tool_arguments": _text(seams.get("tool_arguments"), "Not captured"),
                        "sql": _text(seams.get("sql_text")),
                        "rows": _rows(seams.get("tool_output")),
                        "execution": execution_result or {"status": "NOT_CONFIGURED"},
                        "answer": _text(seams.get("answer")),
                        "trace_id": _text(seams.get("trace_id"), "No trace id"),
                        "telemetry": _telemetry(turn_record.get("telemetry")),
                        "coverage": _evidence_coverage(turn_record, seams, manifest),
                        # Judge output attaches only to the repeat's final captured
                        # turn: it is produced from that final SeamRun, and pinning
                        # it there keeps earlier turns byte-for-byte as before.
                        "judge_scores": judge_scores if is_final_turn else [],
                        "semantic_result": semantic_result if is_final_turn else None,
                    }
                )
    return turns


_NON_MEASURED = frozenset({"INFRA", "UNRUN", "UNGRADED", "NOT_EVALUATED"})


def load_pricing() -> dict[str, dict[str, float]]:
    """Serving prices (USD per million tokens) for the dashboard's cost estimate."""
    try:
        import yaml

        settings = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
        return (settings or {}).get("eval", {}).get("pricing_usd_per_mtok") or {}
    except (OSError, ImportError):
        return {}


def _token_usage(run: dict[str, Any]) -> dict[str, Any]:
    """Sum the per-turn telemetry aggregates into one run-level token picture."""
    input_tokens = output_tokens = total_tokens = 0
    turns_with_telemetry = 0
    latencies: list[float] = []
    for scenario_record in (run.get("scenarios") or {}).values():
        if not isinstance(scenario_record, dict):
            continue
        for repeat_record in scenario_record.get("repeats", []):
            if not isinstance(repeat_record, dict):
                continue
            for turn_record in repeat_record.get("turns", []):
                if not isinstance(turn_record, dict):
                    continue
                telemetry = turn_record.get("telemetry")
                usage = telemetry.get("provider_token_usage") if isinstance(telemetry, dict) else None
                aggregate = usage.get("aggregate") if isinstance(usage, dict) else None
                if not isinstance(aggregate, dict):
                    continue
                turns_with_telemetry += 1
                input_tokens += int(aggregate.get("input_tokens") or 0)
                output_tokens += int(aggregate.get("output_tokens") or 0)
                total_tokens += int(aggregate.get("total_tokens") or 0)
                latency = telemetry.get("latency_ms")
                if isinstance(latency, (int, float)):
                    latencies.append(float(latency))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "turns_with_telemetry": turns_with_telemetry,
        "latency_average_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "latency_max_ms": max(latencies) if latencies else None,
    }


def _cost_estimate(models: list[Any], usage: dict[str, Any], pricing: dict[str, dict[str, float]]) -> dict[str, Any]:
    """Price the run's token totals, refusing to guess when attribution is missing.

    Telemetry records tokens per turn, not per model profile. When the manifest
    serves more than one distinct agent model the split is unknowable, so the
    estimate says so instead of silently applying one price to everything.
    """
    distinct = sorted({str(model) for model in models if model})
    if not distinct:
        return {"available": False, "reason": "The manifest records no serving model."}
    unknown = [model for model in distinct if model not in pricing]
    if unknown:
        return {"available": False, "reason": f"No price is recorded for {', '.join(unknown)}; add it to eval.pricing_usd_per_mtok."}
    if len(distinct) > 1:
        return {"available": False, "reason": f"Tokens are not attributed per model ({', '.join(distinct)}), so no single price applies."}
    prices = pricing[distinct[0]]
    input_cost = usage["input_tokens"] / 1e6 * float(prices.get("input", 0))
    output_cost = usage["output_tokens"] / 1e6 * float(prices.get("output", 0))
    return {
        "available": True,
        "model": distinct[0],
        "input_usd": round(input_cost, 4),
        "output_usd": round(output_cost, 4),
        "total_usd": round(input_cost + output_cost, 4),
    }


def build_dashboard(
    run: dict[str, Any],
    flat_turns: list[dict[str, Any]],
    grade: dict[str, Any] | None = None,
    pricing: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Aggregate a run into pass-rate, token, latency, and cost summaries.

    Category pass rates prefer the grader's own `summary.by_class` when a grade file
    is joined - it is authoritative and includes verdicts that never captured a turn
    (UNRUN, INFRA). Without it the dashboard falls back to counting the captured
    turns' grade statuses and says which source produced the numbers.
    """
    counts = Counter(str(turn.get("grade_status")) for turn in flat_turns)
    measured = sum(n for status, n in counts.items() if status not in _NON_MEASURED)
    pass_rate = counts["PASS"] / measured if measured else None
    by_class: dict[str, dict[str, Any]] = {}
    summary_classes = ((grade or {}).get("summary") or {}).get("by_class")
    class_source = "grade summary"
    if isinstance(summary_classes, dict) and summary_classes:
        for category, entry in summary_classes.items():
            by_class[str(category)] = {
                "counts": {str(k): int(v) for k, v in (entry.get("counts") or {}).items()},
                "measured": int(entry.get("measured") or 0),
                "pass_rate": entry.get("pass_rate"),
            }
    else:
        class_source = "captured turns (no grade file joined)"
        category_counts: dict[str, Counter] = {}
        for turn in flat_turns:
            category = str(turn["scenario_id"]).split("-", maxsplit=1)[0]
            category_counts.setdefault(category, Counter())[str(turn.get("grade_status"))] += 1
        for category, tally in category_counts.items():
            class_measured = sum(n for status, n in tally.items() if status not in _NON_MEASURED)
            by_class[category] = {
                "counts": dict(tally),
                "measured": class_measured,
                "pass_rate": tally["PASS"] / class_measured if class_measured else None,
            }
    failing_checks = Counter(
        str(check.get("name"))
        for turn in flat_turns
        for check in turn.get("checks", [])
        if check.get("outcome") == "FAILED"
    )
    manifest = run.get("manifest") if isinstance(run.get("manifest"), dict) else {}
    usage = _token_usage(run)
    return {
        "turns": len(flat_turns),
        "counts": dict(sorted(counts.items())),
        "measured": measured,
        "pass_rate": pass_rate,
        "class_source": class_source,
        "classes": [
            {"category": category, **stats}
            for category, stats in sorted(by_class.items())
        ],
        "failing_checks": sorted(failing_checks.items(), key=lambda item: (-item[1], item[0])),
        "usage": usage,
        "cost": _cost_estimate(list((manifest.get("models") or {}).values()), usage, pricing or {}),
    }


def sample_run() -> dict[str, Any]:
    """Return a small two-turn artifact for zero-quota viewer verification.

    The tool_output strings reproduce `query_clean_jobs`'s real prose format, so
    verifying against this sample exercises the same parsing path a recorded run
    takes. An earlier Python-literal sample exercised a path production never hit.
    """
    return {
        "manifest": {
            "run_id": "sample-run",
            "git_sha": "0000000",
            "baseline_eligible": False,
            "providers": {"react": "sample-provider", "sql_generation": "sample-provider"},
            "models": {"react": "sample-react-model", "sql_generation": "sample-sql-model"},
            "sampling": {
                "react": {"temperature": 0, "max_tokens": 1024, "reasoning_effort": None},
                "sql_generation": {"temperature": 0, "max_tokens": 512, "reasoning_effort": None},
            },
        },
        "status": "COMPLETE",
        "scenarios": {
            "HLP-SAMPLE-1": {
                "repeats": [
                    {
                        "repeat": 1,
                        "turns": [
                            {"turn": 1, "status": "COMPLETE", "seams": {"question": "How many jobs?", "tools_called": ["query_clean_jobs"], "sql_text": "SELECT COUNT(*) FROM clean_jobs", "tool_output": "Found 1 result(s) with columns: count.\n- count=2", "answer": "There are 2 jobs.", "trace_id": "sample-trace-1"}, "telemetry": {"latency_ms": 1200, "provider_token_usage": {"calls": [{"input_tokens": 900, "output_tokens": 40, "total_tokens": 940, "finish_reason": "stop"}], "aggregate": {"input_tokens": 900, "output_tokens": 40, "total_tokens": 940}}, "finish_reasons": ["stop"]}},
                            {"turn": 2, "status": "COMPLETE", "seams": {"question": "Which companies are listed?", "tools_called": ["query_clean_jobs"], "sql_text": "SELECT company FROM clean_jobs", "tool_output": "Found 2 result(s) with columns: company.\n- company=Acme\n- company=Beta", "answer": "The listed companies are Acme and Beta.", "trace_id": "sample-trace-2"}},
                        ],
                    }
                ]
            }
        },
    }


def build_viewer_html(
    run: dict[str, Any],
    scenarios: list[dict[str, Any]] | None = None,
    grade: dict[str, Any] | None = None,
    execution_accuracy: dict[str, Any] | None = None,
) -> str:
    """Build a self-contained HTML viewer with no API or external asset dependency."""
    manifest = run.get("manifest", {})
    manifest = manifest if isinstance(manifest, dict) else {}
    run_id = str(manifest.get("run_id", "unknown-run"))
    turn_records = flatten_turns(run, scenarios, grade, execution_accuracy)
    payload = {
        "run_id": run_id,
        "status": run.get("status", "UNKNOWN"),
        "header": run_header(manifest),
        "turns": turn_records,
        "dashboard": build_dashboard(run, turn_records, grade, load_pricing()),
    }
    serialized = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    title = html.escape(f"Trace viewer - {run_id}")
    return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root { color-scheme: dark; --bg:#0a0e14; --card:#141b25; --well:#0e141d; --ink:#e8eef5; --muted:#95a4b6; --line:#28374a; --accent:#ff5fa8; --accent-deep:#55112f; --accent-ink:#2b0316; --green:#42d98d; --red:#ff6d6d; --amber:#ffb84d; }
    * { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
    header { background:#04070c; border-bottom:2px solid var(--accent); color:#f2f7fc; padding:20px max(24px,calc((100vw - 1180px)/2)); }
    .header-row,.toolbar,.turn-meta,.card-head { display:flex; align-items:center; gap:12px; } .header-row,.toolbar { justify-content:space-between; }
    .header-col { display:flex; flex-direction:column; align-items:flex-end; gap:10px; } @media (max-width:800px) { .header-col { align-items:flex-start; } }
    /* A long scenario id in .progress used to squeeze the nav buttons until their own
       labels broke across two lines. Let the toolbar reflow, and never break a label. */
    .toolbar,.turn-meta { flex-wrap:wrap; } .toolbar button { white-space:nowrap; }
    h1 { margin:0; font-size:24px; letter-spacing:-.02em; } h2 { margin:0; font-size:18px; } h3 { margin:0; font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:var(--accent); }
    main { max-width:1180px; margin:0 auto; padding:20px 24px 36px; }
    /* The toolbar sticks to the top so Prev/Next, search, and the jump menu stay
       reachable while a long tool-output table is being scrolled. */
    .toolbar { margin-bottom:14px; position:sticky; top:0; z-index:20; background:rgba(10,14,20,.92); backdrop-filter:blur(8px); border:1px solid var(--line); border-radius:12px; padding:10px 12px; }
    select,button,textarea,input { font:inherit; }
    button { cursor:pointer; border:1px solid var(--line); border-radius:8px; background:#1d2937; color:var(--ink); padding:8px 13px; font-weight:650; } button:hover:not(:disabled) { border-color:var(--accent); color:var(--accent); } button:disabled { opacity:.4; cursor:default; }
    #prev,#next { background:var(--accent); border-color:var(--accent); color:var(--accent-ink); } #prev:hover:not(:disabled),#next:hover:not(:disabled) { color:var(--accent-ink); filter:brightness(1.18); }
    select,textarea,input[type="search"] { border:1px solid var(--line); border-radius:8px; background:var(--well); color:var(--ink); padding:8px 12px; } select:focus,textarea:focus,input[type="search"]:focus { outline:2px solid var(--accent); outline-offset:-2px; }
    .search { flex:1 1 240px; min-width:190px; }
    .progress { color:var(--muted); font-variant-numeric:tabular-nums; } .run-fail { color:var(--red); }
    .rule { background:#251b06; border:1px solid #6d5512; border-radius:10px; padding:12px 16px; margin:12px 0; color:#ffd98f; }
    .chips { display:flex; flex-wrap:wrap; gap:6px; } .chip { border-radius:999px; padding:5px 12px; font-size:12px; font-weight:700; letter-spacing:.03em; background:#1d2937; } .chip.active { background:var(--accent); border-color:var(--accent); color:var(--accent-ink); } .chip.c-FAIL.active { background:var(--red); border-color:var(--red); color:#2b0505; } .chip.c-PASS.active { background:var(--green); border-color:var(--green); color:#032312; } .chip.c-INFRA.active { background:var(--amber); border-color:var(--amber); color:#2b1a02; }
    .tabs { display:flex; gap:8px; } .tab { border-radius:999px; padding:7px 16px; font-weight:700; background:#141b25; } .tab.active { background:var(--accent); border-color:var(--accent); color:var(--accent-ink); }
    /* Dashboard cards: pass-rate bars, token totals, and the cost estimate. */
    .dash { display:grid; gap:16px; margin-top:14px; }
    .statgrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }
    .stat { background:var(--well); border:1px solid var(--line); border-radius:10px; padding:12px 14px; min-width:0; } .stat label { display:block; color:var(--muted); font-size:11px; font-weight:650; text-transform:uppercase; letter-spacing:.06em; margin-bottom:6px; } .stat strong { font-size:22px; letter-spacing:-.01em; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; } .stat span { display:block; color:var(--muted); font-size:12px; margin-top:5px; overflow-wrap:anywhere; }
    .bar { height:10px; background:#1d2937; border-radius:999px; overflow:hidden; min-width:90px; } .barfill { height:100%; border-radius:999px; } .barfill.good { background:var(--green); } .barfill.mid { background:var(--amber); } .barfill.bad { background:var(--red); }
    .failrow { display:flex; align-items:center; gap:10px; margin-top:8px; } .failname { width:230px; max-width:40%; font-size:13px; overflow-wrap:anywhere; } .failcount { color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }
    .question { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; margin-top:14px; }
    .grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin-top:16px; } .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; min-width:0; }
    .card-head { justify-content:space-between; margin-bottom:14px; } .seam { color:var(--accent); } .field { margin-top:14px; } .field label { display:block; color:var(--muted); font-size:12px; font-weight:650; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
    details.field summary { cursor:pointer; color:var(--accent); font-weight:650; text-transform:uppercase; font-size:12px; letter-spacing:.06em; }
    pre,.answer,.rows-text { white-space:pre-wrap; overflow-wrap:anywhere; margin:0; background:var(--well); border:1px solid var(--line); border-radius:7px; padding:10px; min-height:42px; } .answer { background:#0c1e19; border-color:#1d4636; }
    /* Long evidence stays readable without pushing the rest of the turn off screen:
       tables and long text scroll inside a bounded box until expanded. */
    .scrollbox { max-height:320px; overflow:auto; border-radius:7px; } .scrollbox.open { max-height:none; } .expand { margin-top:6px; padding:4px 11px; font-size:12px; color:var(--accent); background:var(--accent-deep); border-color:#8a2a58; }
    .trace { color:var(--muted); font-size:12px; margin-top:14px; overflow-wrap:anywhere; } .row-count { color:var(--muted); font-size:12px; margin-bottom:6px; } .row-note { color:var(--amber); font-size:12px; font-weight:650; margin-bottom:6px; } .table-wrap { overflow-x:auto; } table { border-collapse:collapse; width:100%; font-size:13px; } th,td { border-bottom:1px solid var(--line); padding:7px 8px; text-align:left; vertical-align:top; } th { color:var(--accent); font-weight:650; white-space:nowrap; position:sticky; top:0; background:var(--card); }
    .notes { margin-top:16px; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; } textarea { width:100%; min-height:110px; resize:vertical; margin-top:8px; } .saved { color:var(--muted); font-size:12px; margin-top:6px; }
    .empty { text-align:center; padding:70px 20px; color:var(--muted); } @media (max-width:800px) { .grid { grid-template-columns:1fr; } main { padding:14px; } .header-row { align-items:flex-start; flex-direction:column; } }
    .runbar { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; margin-bottom:6px; } .facts { display:flex; flex-wrap:wrap; gap:18px; } .fact { font-size:13px; overflow-wrap:anywhere; } .fact label { color:var(--muted); font-size:11px; font-weight:650; text-transform:uppercase; letter-spacing:.06em; margin-right:6px; }
    .badge { display:inline-block; border-radius:999px; padding:2px 10px; font-size:12px; font-weight:700; letter-spacing:.04em; border:1px solid transparent; } .b-PASS,.b-CAPTURED { background:rgba(66,217,141,.16); color:var(--green); border-color:rgba(66,217,141,.5); } .b-FAIL,.b-CAPTURE_FAILED { background:rgba(255,109,109,.16); color:var(--red); border-color:rgba(255,109,109,.5); } .b-INFRA,.b-PROVIDER_DID_NOT_EMIT { background:rgba(255,184,77,.14); color:var(--amber); border-color:rgba(255,184,77,.5); } .b-UNRUN,.b-UNGRADED,.b-UNKNOWN,.b-NOT_CONFIGURED,.b-NOT_APPLICABLE,.b-NOT_EVALUATED { background:#1d2937; color:var(--muted); border-color:var(--line); } .b-score { background:rgba(122,162,255,.16); color:#9db8ff; border-color:rgba(122,162,255,.5); } .b-unavailable { background:#1d2937; color:var(--muted); border-color:var(--line); }
    /* The failure panel leads the turn view: an operator scans why a turn failed
       before reading any evidence beneath it. */
    .failpanel { margin-top:14px; background:rgba(255,109,109,.08); border:1px solid rgba(255,109,109,.45); border-left:5px solid var(--red); border-radius:10px; padding:14px 16px; } .failpanel h2 { color:var(--red); } .failpanel p { margin:8px 0 0; overflow-wrap:anywhere; } .failpanel ol { margin:10px 0 0; padding-left:20px; } .failpanel li { margin-top:8px; font-size:14px; } .failpanel .detail { overflow-wrap:anywhere; } .failpanel .meta { color:var(--muted); font-size:12px; }
    .verdict { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-top:14px; font-size:13px; color:var(--muted); }
    .checks { margin-top:14px; display:grid; gap:10px; } .check { border:1px solid var(--line); border-left-width:4px; border-radius:8px; padding:10px 12px; background:var(--well); } .check-fail { border-left-color:var(--red); background:rgba(255,109,109,.07); } .check-na { border-left-color:var(--amber); }
    .check-head { display:flex; flex-wrap:wrap; align-items:center; gap:8px; font-size:13px; } .check-head .tier { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; } .check-detail { margin-top:6px; font-size:13px; overflow-wrap:anywhere; white-space:pre-wrap; }
    .tele { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; } .tele div { background:var(--well); border:1px solid var(--line); border-radius:7px; padding:8px 10px; } .tele label { display:block; color:var(--muted); font-size:11px; font-weight:650; text-transform:uppercase; letter-spacing:.06em; margin-bottom:3px; } .tele span { font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
  </style>
</head>
<body>
  <header><div class="header-row"><div><h1>Trace viewer</h1><div id="run-label"></div></div><div class="header-col"><div id="run-status"></div><div class="tabs" role="tablist"><button id="tab-turns" class="tab active" type="button">Turns</button><button id="tab-dashboard" class="tab" type="button">Dashboard</button></div></div></div></header>
  <main>
    <section class="runbar" id="run-header"></section>
    <div id="app"></div>
  </main>
  <script id="run-data" type="application/json">__DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById('run-data').textContent);
    const turns = data.turns;
    const storageKey = 'internhunter-trace-notes/' + data.run_id + '/';
    const GRADES = ['PASS', 'FAIL', 'INFRA', 'UNRUN', 'UNGRADED'];
    let mode = 'turns';
    let filter = 'ALL';
    let query = '';
    let view = turns;
    let index = 0;
    const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'} )[c]);
    const block = (label, value, cls='') => `<div class="field"><label>${label}</label><div class="${cls}">${label === 'Rows returned' ? rowsBlock(value) : esc(value)}</div></div>`;
    // Long evidence (SQL, answers, tool output) scrolls inside a bounded box with an
    // expander, so one verbose turn cannot push the operator note off screen.
    const collapsible = (cls, inner, moreLabel) => `<div class="scrollbox"><div class="${cls}">${inner}</div></div><button class="expand" type="button" data-more="${moreLabel || 'Show more ⤵'}">${moreLabel || 'Show more ⤵'}</button>`;
    const longBlock = (label, value) => `<div class="field"><label>${label}</label>${collapsible('answer', esc(value))}</div>`;
    const table = (headers, rows) => `<div class="table-wrap"><table><thead><tr>${headers.map(header => `<th scope="col">${esc(header)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${esc(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    const badge = (status, label) => `<span class="badge b-${esc(status)}">${esc(label === undefined ? status : label)}</span>`;
    const teleBlock = tele => {
      if (!tele.available) return '<div class="rows-text">No telemetry was recorded for this turn.</div>';
      const fields = [['Latency (ms)', tele.latency_ms], ['Input tokens', tele.input_tokens], ['Output tokens', tele.output_tokens], ['Total tokens', tele.total_tokens], ['Finish reasons', tele.finish_reasons]];
      const grid = `<div class="tele">${fields.map(([label, value]) => `<div><label>${esc(label)}</label><span>${esc(value)}</span></div>`).join('')}</div>`;
      if (!tele.calls.length) return grid + '<div class="row-count" style="margin-top:10px">No per-call usage was reported.</div>';
      return `${grid}<div class="row-count" style="margin-top:12px">${tele.calls.length} model call${tele.calls.length === 1 ? '' : 's'} in this turn</div>${table(['Call', 'Input', 'Output', 'Total', 'Finish reason'], tele.calls)}`;
    };
    const checkBadgeStatus = outcome => ({FAILED: 'FAIL', UNAVAILABLE: 'INFRA', NOT_EVALUATED: 'NOT_EVALUATED'})[outcome] || outcome;
    const checksFor = (turn, seam) => {
      const items = turn.checks.filter(check => check.seam === seam);
      if (!items.length) return '';
      return `<div class="checks">${items.map(check => `<div class="check ${check.outcome === 'FAILED' ? 'check-fail' : 'check-na'}"><div class="check-head"><strong>${esc(check.name)}</strong>${badge(checkBadgeStatus(check.outcome), check.outcome)}<span class="tier">${esc(check.tier)} tier</span></div><div class="check-detail">${esc(check.detail)}</div></div>`).join('')}</div>`;
    };
    /* Persisted model-judge output is informational only: it sits beside the
       evidence the judge read and never feeds the deterministic PASS/FAIL. */
    const formatScore = score => typeof score === 'number' ? String(Math.round(score * 1000) / 1000) : '—';
    const judgeScoresFor = (t, seam) => {
      const entry = (t.judge_scores || []).find(item => item.seam === seam);
      if (!entry || !entry.metrics.length) return '';
      const rows = entry.metrics.map(m => {
        const mark = m.available ? `<span class="badge b-score">${formatScore(m.score)}</span>` : '<span class="badge b-unavailable">unavailable</span>';
        const detail = m.available ? esc(m.reason) : esc(m.error || m.reason);
        return `<div class="check ${m.available ? '' : 'check-na'}"><div class="check-head"><strong>${esc(m.name)}</strong>${mark}</div>${detail ? `<div class="check-detail">${detail}</div>` : ''}</div>`;
      }).join('');
      return `<div class="field"><label>Model-judge scores</label><div class="checks">${rows}</div></div>`;
    };
    const semanticBlock = t => {
      const s = t.semantic_result;
      if (!s) return '';
      const mark = s.available ? `<span class="badge b-score">${formatScore(s.score)}</span>` : `<span class="badge b-unavailable">${esc(s.status)}</span>`;
      const confidence = s.confidence === null || s.confidence === undefined ? '' : `<span class="tier">confidence ${formatScore(s.confidence)}</span>`;
      const detail = s.rationale ? `<div class="check-detail">${esc(s.rationale)}</div>` : '';
      return `<div class="field"><label>Semantic result</label><div class="checks"><div class="check ${s.available ? '' : 'check-na'}"><div class="check-head"><strong>Semantic behavior</strong>${mark}${confidence}</div>${detail}</div></div></div>`;
    };
    const rowsBlock = rows => {
      if (rows.kind === 'text') return `<div class="rows-text">${esc(rows.text)}</div>`;
      const note = rows.note ? `<div class="row-note">${esc(rows.note)}</div>` : '';
      if (!rows.count) return note + '<div class="rows-text">No rows returned.</div>';
      return `${note}<div class="row-count">${rows.count} row${rows.count === 1 ? '' : 's'} · ${rows.headers.length} column${rows.headers.length === 1 ? '' : 's'}</div><div class="scrollbox">${table(rows.headers, rows.rows)}</div><button class="expand" type="button" data-more="Expand full table ⤢">Expand full table ⤢</button>`;
    };
    /* The failure panel leads the turn: an operator scans why it failed before
       reading any evidence. Checks that did not pass stay beside their seam. */
    const failPanel = t => {
      const failed = t.checks.filter(check => check.outcome === 'FAILED');
      if (!failed.length) {
        return t.grade_status === 'FAIL'
          ? `<section class="failpanel"><h2>✗ This turn failed</h2><p>No failed check joined this turn; the verdict came from the grade file without per-check detail.</p></section>`
          : '';
      }
      const items = failed.map(check => `<li><strong>${esc(check.name)}</strong> <span class="meta">· ${esc(check.seam)} seam · ${esc(check.tier)} tier</span><div class="detail">${esc(check.detail)}</div></li>`).join('');
      return `<section class="failpanel"><h2>✗ Why this turn failed</h2><ol>${items}</ol></section>`;
    };
    const executionBlock = result => {
      if (result.status === 'NOT_CONFIGURED') return '<div class="rows-text">No execution-accuracy report was joined.</div>';
      const facts = [['Result', result.status], ['Comparison', result.comparison_mode || 'not recorded'], ['Generated rows', result.generated_row_count ?? 'not recorded'], ['Reference rows', result.reference_row_count ?? 'not recorded']];
      const summary = `<div class="tele">${facts.map(([label, value]) => `<div><label>${esc(label)}</label><span>${esc(value)}</span></div>`).join('')}</div>`;
      const renderedRows = rows => Array.isArray(rows) ? rowsBlock({kind:'table', count:rows.length, headers:Object.keys(rows[0] || {}), rows:rows.map(row => Object.values(row).map(String))}) : '<div class="rows-text">Not recorded</div>';
      return `${summary}<div class="field"><label>Generated rows</label>${renderedRows(result.generated_rows)}</div><div class="field"><label>Reference rows</label>${renderedRows(result.reference_rows)}</div>`;
    };
    const coverageBlock = coverage => table(['Evidence', 'Coverage'], coverage.map(([label, status]) => [label, status]));
    const storageRead = key => { try { return {value: window.localStorage.getItem(key) || '', error: ''}; } catch (_) { return {value: '', error: 'Notes are unavailable in this browser; navigation still works.'}; } };
    const storageWrite = (key, value) => { try { window.localStorage.setItem(key, value); return true; } catch (_) { return false; } };
    function renderRunHeader() {
      const header = data.header;
      const facts = header.facts.map(([label, value]) => `<span class="fact"><label>${esc(label)}</label>${esc(value)}</span>`).join('');
      const body = header.rows.length ? table(header.headers, header.rows) : '<div class="rows-text">This capture records no provider or sampling block.</div>';
      document.getElementById('run-header').innerHTML = `<div class="card-head"><h2>What produced this capture</h2><div class="facts">${facts}</div></div>${body}`;
    }
    // Grade chips plus free-text search decide which turns the pager walks through.
    function applyView(keepKey) {
      const needle = query.trim().toLowerCase();
      view = turns.filter(turn => (filter === 'ALL' || turn.grade_status === filter) && (!needle || [turn.scenario_id, turn.scenario_name, turn.question, turn.answer, turn.routing, turn.sql, ...turn.checks.map(check => check.name + ' ' + check.detail)].join('\\n').toLowerCase().includes(needle)));
      const kept = view.findIndex(turn => turn.key === keepKey);
      index = kept >= 0 ? kept : 0;
    }
    function renderDashboard(root) {
      const d = data.dashboard || {};
      const pct = value => value === null || value === undefined ? '—' : Math.round(value * 100) + '%';
      const fmt = value => value === null || value === undefined ? '—' : Number(value).toLocaleString('en-US');
      const stat = (label, value, sub='') => `<div class="stat"><label>${esc(label)}</label><strong>${value}</strong>${sub ? `<span>${sub}</span>` : ''}</div>`;
      const classes = d.classes || [];
      const classRows = classes.map(c => {
        const rate = c.pass_rate === null || c.pass_rate === undefined ? null : Math.round(c.pass_rate * 100);
        const tone = rate === null ? '' : rate >= 80 ? 'good' : rate >= 50 ? 'mid' : 'bad';
        const bar = rate === null ? '<span class="progress">—</span>' : `<div class="bar"><div class="barfill ${tone}" style="width:${rate}%"></div></div>`;
        const counts = Object.entries(c.counts).map(([status, n]) => `<span class="badge b-${esc(status)}">${esc(status)} ${n}</span>`).join(' ');
        return `<tr><td><strong>${esc(c.category)}</strong></td><td>${counts}</td><td class="progress">${c.measured} measured</td><td>${pct(c.pass_rate)}</td><td style="min-width:140px">${bar}</td></tr>`;
      }).join('');
      const cost = d.cost && d.cost.available
        ? stat('Estimated cost', '$' + d.cost.total_usd.toFixed(4), `${esc(d.cost.model)} · in $${d.cost.input_usd.toFixed(4)} / out $${d.cost.output_usd.toFixed(4)}`)
        : stat('Estimated cost', '—', esc((d.cost && d.cost.reason) || ''));
      const latency = d.usage && d.usage.latency_average_ms !== null && d.usage.latency_average_ms !== undefined
        ? stat('Avg latency', fmt(d.usage.latency_average_ms) + ' ms', `max ${fmt(d.usage.latency_max_ms)} ms`)
        : '';
      const fails = d.failing_checks || [];
      const failBars = fails.length ? fails.map(([name, count]) => `<div class="failrow"><span class="failname">${esc(name)}</span><div class="bar"><div class="barfill bad" style="width:${Math.round(count / fails[0][1] * 100)}%"></div></div><span class="failcount">× ${count}</span></div>`).join('') : '<div class="rows-text">No failed checks were joined for this run.</div>';
      const usage = d.usage || {};
      root.innerHTML = `<div class="dash">
      <section class="card"><div class="card-head"><h2>Run health</h2><span class="progress">${esc(d.class_source || '')}</span></div>
      <div class="statgrid">
        ${stat('Captured turns', String(d.turns ?? 0))}
        ${stat('Overall pass rate', pct(d.pass_rate), `${(d.counts && d.counts.PASS) || 0} PASS · ${d.measured ?? 0} measured (INFRA/UNRUN/NOT_EVALUATED excluded)`)}
        ${latency}
        ${stat('Tokens in / out', `${fmt(usage.input_tokens)} / ${fmt(usage.output_tokens)}`, `${usage.turns_with_telemetry ?? 0} of ${d.turns ?? 0} turns report usage`)}
        ${stat('Total tokens', fmt(usage.total_tokens))}
        ${cost}
      </div></section>
      <section class="card"><div class="card-head"><h2>Pass rate by category</h2></div>
      <div class="table-wrap"><table><thead><tr><th scope="col">Category</th><th scope="col">Verdicts</th><th scope="col"></th><th scope="col">Pass rate</th><th scope="col"></th></tr></thead><tbody>${classRows || '<tr><td colspan="5" class="rows-text">No graded turns are available in this run.</td></tr>'}</tbody></table></div></section>
      <section class="card"><div class="card-head"><h2>Most frequent failing checks</h2></div>${failBars}</section>
      </div>`;
    }
    function wireToolbar(root) {
      root.querySelectorAll('.chip').forEach(chip => { chip.onclick = () => { filter = chip.dataset.grade; applyView(view[index] ? view[index].key : null); render(); }; });
      const search = root.querySelector('#search');
      if (search) search.oninput = () => { query = search.value; applyView(view[index] ? view[index].key : null); render(); };
    }
    function render() {
      document.getElementById('tab-turns').classList.toggle('active', mode === 'turns');
      document.getElementById('tab-dashboard').classList.toggle('active', mode === 'dashboard');
      document.getElementById('tab-turns').onclick = () => { mode = 'turns'; render(); };
      document.getElementById('tab-dashboard').onclick = () => { mode = 'dashboard'; render(); };
      const previousSearch = document.getElementById('search');
      const resume = previousSearch ? { pos: previousSearch.selectionStart } : null;
      document.getElementById('run-label').textContent = data.run_id + ' · ' + turns.length + ' captured turn' + (turns.length === 1 ? '' : 's');
      const failCount = turns.filter(turn => turn.grade_status === 'FAIL').length;
      document.getElementById('run-status').innerHTML = 'Capture: ' + esc(data.status) + (failCount ? ` · <strong class="run-fail">${failCount} failed</strong>` : '');
      renderRunHeader();
      const root = document.getElementById('app');
      if (mode === 'dashboard') { renderDashboard(root); return; }
      if (!turns.length) { root.innerHTML = '<div class="empty">No captured turns are available in this run.</div>'; return; }
      const counts = {};
      GRADES.forEach(status => { counts[status] = turns.filter(turn => turn.grade_status === status).length; });
      const chipRow = ['ALL', ...GRADES.filter(status => counts[status])].map(status => `<button type="button" class="chip c-${esc(status)}${status === filter ? ' active' : ''}" data-grade="${esc(status)}">${status === 'ALL' ? 'All' : esc(status)} ${status === 'ALL' ? turns.length : counts[status]}</button>`).join('');
      const searchBox = `<input id="search" class="search" type="search" placeholder="Search scenario, question, SQL, answer, checks… (press /)" value="${esc(query)}" aria-label="Search turns">`;
      if (!view.length) {
        root.innerHTML = `<div class="toolbar">${searchBox}<div class="chips" id="grade-filter">${chipRow}</div></div><div class="empty">No turn matches this filter${query.trim() ? ' and search text' : ''}.</div>`;
        wireToolbar(root);
        return;
      }
      const t = view[index];
      const noteKey = storageKey + t.key;
      root.innerHTML = `<div class="toolbar"><div class="turn-meta"><button id="prev">← Prev</button><button id="next">Next →</button><span class="progress">Turn ${index + 1} of ${view.length} · ${esc(t.scenario_id)} · repeat ${esc(t.repeat)}</span></div><div class="turn-meta">${searchBox}<div class="chips" id="grade-filter">${chipRow}</div><select id="jump" aria-label="Jump to turn">${view.map((item, i) => `<option value="${i}">${i + 1}. ${item.grade_status === 'FAIL' ? '✗ ' : ''}${esc(item.scenario_id)} / r${esc(item.repeat)} / t${esc(item.turn)} · ${esc(item.grade_status)}</option>`).join('')}</select></div></div>
      <div class="rule"><strong>Review rule:</strong> mark the earliest wrong seam only, then stop. Downstream symptoms of an upstream defect are not separate labels.</div>
      <section class="question"><h3>${esc(t.scenario_name)}</h3>${block('Question', t.question)}
      <div class="verdict">Verdict ${badge(t.grade_status)}<span>Grade tier: ${esc(t.grade_tier)}</span><span>Capture status: ${esc(t.status)}</span></div>
      ${failPanel(t)}${checksFor(t, 'run')}
      <details class="field"><summary>Evidence coverage</summary>${coverageBlock(t.coverage)}</details>
      <details class="field"><summary>Telemetry</summary>${teleBlock(t.telemetry)}</details></section>
      <section class="grid"><article class="card"><div class="card-head"><h2 class="seam">1 · Routing</h2></div>${block('Expected tools', t.expected_tools)}${block('Captured tools', t.routing)}${longBlock('Captured tool arguments', t.tool_arguments)}${checksFor(t, 'routing')}${judgeScoresFor(t, 'routing')}</article><article class="card"><div class="card-head"><h2 class="seam">2 · NL → SQL</h2></div>${longBlock('Generated SQL', t.sql)} ${block('Rows returned', t.rows)}<div class="field"><label>Generated versus reference rows</label>${executionBlock(t.execution)}</div>${checksFor(t, 'sql')}${judgeScoresFor(t, 'sql')}</article><article class="card"><div class="card-head"><h2 class="seam">3 · Synthesis</h2></div>${longBlock('Final answer', t.answer)}${checksFor(t, 'answer')}${semanticBlock(t)}${judgeScoresFor(t, 'answer')}</article></section>
      <section class="notes"><h2>Operator note</h2><textarea id="note" placeholder="Record the first wrong seam and evidence. Stop after the earliest failure."></textarea><div class="saved" id="saved">Notes are stored in this browser for this run.</div></section>`;
      document.getElementById('jump').value = index;
      document.getElementById('prev').disabled = index === 0; document.getElementById('next').disabled = index === view.length - 1;
      document.getElementById('prev').onclick = () => { index--; render(); }; document.getElementById('next').onclick = () => { index++; render(); };
      document.getElementById('jump').onchange = event => { index = Number(event.target.value); render(); };
      wireToolbar(root);
      // An expander only earns its place when its box actually overflows.
      root.querySelectorAll('.expand').forEach(button => {
        const box = button.previousElementSibling;
        if (!(box instanceof HTMLElement) || box.scrollHeight <= box.clientHeight + 4) { button.remove(); return; }
        button.onclick = () => { const open = box.classList.toggle('open'); button.textContent = open ? 'Show less ⤒' : (button.dataset.more || 'Show more ⤵'); };
      });
      const note = document.getElementById('note');
      const saved = document.getElementById('saved');
      note.addEventListener('input', event => { saved.textContent = storageWrite(noteKey, event.target.value) ? 'Saved locally' : 'Notes are unavailable in this browser; navigation still works.'; });
      const noteState = storageRead(noteKey);
      note.value = noteState.value;
      if (noteState.error) saved.textContent = noteState.error;
      if (resume) { const next = document.getElementById('search'); if (next) { next.focus(); next.setSelectionRange(resume.pos, resume.pos); } }
    }
    document.addEventListener('keydown', event => {
      if (event.target.tagName === 'TEXTAREA') return;
      if (event.target.id === 'search') {
        if (event.key === 'Escape') { const key = view[index] ? view[index].key : null; event.target.value = ''; query = ''; applyView(key); render(); }
        return;
      }
      if (event.key === '/') { if (mode !== 'turns') return; event.preventDefault(); const search = document.getElementById('search'); if (search) search.focus(); return; }
      if (mode !== 'turns') return;
      if (event.key === 'ArrowLeft' && index > 0) { index--; render(); }
      if (event.key === 'ArrowRight' && index < view.length - 1) { index++; render(); }
    });
    render();
  </script>
</body>
</html>'''.replace("__TITLE__", title).replace("__DATA__", serialized)


def _read_grade(path: Path, parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Load a `grader.py` report, failing with the command that produces one."""
    try:
        grade = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        parser.error(
            f"grade file not found: {path}. Create one with: "
            f"uv run python -m evals.grader --run <run.json> > {path}"
        )
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"could not read grade file {path}: {exc}")
    if not isinstance(grade, dict) or not isinstance(grade.get("scenarios"), dict):
        parser.error(f"grade file {path} is not a grader report; expected a top-level 'scenarios' object")
    return grade


def _read_execution_accuracy(path: Path, parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Load the structured SQL comparison report that explains a seam-2 verdict."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"could not read execution-accuracy file {path}: {exc}")
    if not isinstance(report, dict) or not isinstance(report.get("scenarios"), dict):
        parser.error(
            "execution-accuracy file is not a report; expected a top-level 'scenarios' object"
        )
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a local HTML viewer for a scenario-driver run.")
    parser.add_argument("run", type=Path, nargs="?", help="Scenario-driver run JSON artifact")
    parser.add_argument("--sample", action="store_true", help="Generate a two-turn sample without a recorded run or model quota")
    parser.add_argument("--grade", type=Path, help="Grader report JSON to join per turn (optional)")
    parser.add_argument(
        "--execution-accuracy",
        type=Path,
        help="Execution-accuracy JSON to show generated and reference row evidence",
    )
    parser.add_argument("--output", type=Path, help="HTML output path (defaults beside the run artifact)")
    args = parser.parse_args(argv)
    if args.sample and args.run:
        parser.error("pass either a run artifact or --sample, not both")
    if not args.sample and not args.run:
        parser.error("provide a run artifact or --sample")
    if args.sample and args.grade:
        parser.error("--grade joins a grader report to a recorded run; it does not apply to --sample")
    if args.sample and args.execution_accuracy:
        parser.error("--execution-accuracy joins a recorded run; it does not apply to --sample")
    grade = _read_grade(args.grade, parser) if args.grade else None
    execution_accuracy = (
        _read_execution_accuracy(args.execution_accuracy, parser)
        if args.execution_accuracy
        else None
    )
    if args.sample:
        run = sample_run()
        scenarios = [{"id": "HLP-SAMPLE-1", "name": "Sample trace viewer run"}]
        output = args.output or Path("trace-viewer-sample.html")
    else:
        assert args.run is not None
        try:
            run = json.loads(args.run.read_text(encoding="utf-8"))
        except FileNotFoundError:
            parser.error(f"run artifact not found: {args.run}. Create one with: uv run python -m evals.driver --output {args.run}")
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"could not read run artifact {args.run}: {exc}")
        if not isinstance(run, dict) or not isinstance(run.get("manifest"), dict):
            parser.error(f"run artifact {args.run} is not a valid scenario-driver JSON artifact")
        from evals.scenarios import load_scenarios

        scenarios = load_scenarios()
        output = args.output or args.run.with_name(f"{args.run.stem}-viewer.html")
    output.write_text(
        build_viewer_html(run, scenarios, grade, execution_accuracy), encoding="utf-8"
    )
    print(output)


if __name__ == "__main__":
    main()
