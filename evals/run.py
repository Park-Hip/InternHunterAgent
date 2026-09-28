"""One capture and one metric pass per scenario, with an optional offline capture source."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import random
import re
from pathlib import Path
from typing import Any

import yaml
from evals._paths import ROOT
from deepeval.metrics import GEval, ToolCorrectnessMetric
from evals.datasets import DatasetSpec
from evals.metrics import METRIC_BY_NAME, NO_JUDGE, MetricKind, judge_case, tool_case
from evals.sql_check import grade_sql


class QuotaError(RuntimeError):
    """All attempts for a turn exhausted quota responses."""


def capture_settings() -> dict[str, int]:
    settings = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    config = settings["eval"]["capture"]
    for name in ("max_attempts", "consecutive_quota_failures_before_halt"):
        if type(config.get(name)) is not int or config[name] <= 0:
            raise ValueError(f"eval.capture.{name} must be a positive integer")
    return config


def is_quota_error(exc: Exception) -> bool:
    return any(signature in str(exc).lower() for signature in ("429", "rate limit", "rate_limit", "quota", "tpm", "tokens per minute"))


def retry_delay(exc: Exception, attempt: int) -> float:
    hint = re.search(r"try again in\s+([\d.]+)\s*(ms|s)\b", str(exc), re.I)
    if hint:
        return float(hint[1]) / (1000 if hint[2].lower() == "ms" else 1) + 1
    if is_quota_error(exc):
        ceiling = 2**attempt
        return random.uniform(ceiling / 2, ceiling)
    return (1.0, 2.0)[min(attempt, 1)]


async def capture_turn(agent: Any, question: str, config: dict[str, Any]) -> dict[str, Any]:
    """Capture the actual tool and nested SQL spans from the agent's invocation."""
    from deepeval.integrations.langchain import CallbackHandler
    from deepeval.tracing.trace_test_manager import trace_testing_manager
    from langchain_core.messages import HumanMessage

    trace_testing_manager.test_name = "eval-capture"
    trace_testing_manager.test_dict = None
    handler = CallbackHandler(thread_id=config["configurable"]["thread_id"]) if "configurable" in config else CallbackHandler(name="eval-capture")
    try:
        response = await agent.ainvoke({"messages": [HumanMessage(content=question)]}, config={**config, "callbacks": [*config.get("callbacks", []), handler]})
        trace = await trace_testing_manager.wait_for_test_dict()
    finally:
        trace_testing_manager.test_name = None
        trace_testing_manager.test_dict = None
    return {"question": question, "answer": str(response["messages"][-1].content).strip(), **extract_trace(trace)}


def extract_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Nested SQL generation is a sibling of the tool span, not its child."""
    calls = [tc for tc in (trace.get("toolsCalled") or []) if isinstance(tc, dict)]
    tools = [tc["name"] for tc in calls if isinstance(tc.get("name"), str)]
    tool_span = next((span for span in (trace.get("toolSpans") or []) if span.get("name") == "query_clean_jobs"), None)
    sql_span = next((span for span in (trace.get("llmSpans") or []) if tool_span and span.get("parentUuid") == tool_span.get("parentUuid")), None)
    sql = sql_span.get("output") if sql_span else None
    if isinstance(sql, dict):
        sql = sql.get("content")
    output = tool_span.get("output") if tool_span else None
    if isinstance(output, dict):
        output = output.get("content") or str(output)
    return {"tools_called": tools, "sql_text": sql if isinstance(sql, str) else None, "tool_output": str(output) if output is not None else None}


async def capture_with_retry(agent: Any, question: str, config: dict[str, Any], sleep=asyncio.sleep) -> dict[str, Any]:
    max_attempts = capture_settings()["max_attempts"]
    for attempt in range(max_attempts):
        try:
            return await capture_turn(agent, question, config)
        except Exception as exc:
            if attempt == max_attempts - 1:
                if is_quota_error(exc):
                    raise QuotaError(str(exc)) from exc
                raise
            await sleep(retry_delay(exc, attempt))
    raise AssertionError("unreachable")


async def capture_scenario(scenario: dict[str, Any], prompts: Any) -> list[dict[str, Any]]:
    """Use the same agent thread for each turn in a conversational scenario."""
    from langchain_core.messages import SystemMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from src.agents.runtime.factory import agent_factory
    from src.agents.runtime.prompts import prompt_bundle_context
    from src.agents.tracing.langfuse import langfuse_prompt_attributes, langfuse_request_trace, validate_langfuse_trace_context

    conversational = scenario.get("type") == "conversational"
    agent = agent_factory(system_prompt=SystemMessage(content=prompts.system.content), **({"checkpointer": InMemorySaver()} if conversational else {}))
    config: dict[str, Any] = {"configurable": {"thread_id": scenario["id"]}} if conversational else {}
    turns = scenario["turns"] if conversational else [scenario["input"]]
    captured: list[dict[str, Any]] = []
    validate_langfuse_trace_context(entry_point="eval:driver", scenario_id=scenario["id"], repeat=1)
    for index, question in enumerate(turns):
        with prompt_bundle_context(prompts):
            async with langfuse_request_trace(entry_point="eval:driver", scenario_id=scenario["id"], repeat=1, trace_name=f"eval-{scenario['id']}-{index + 1}", prompts=prompts):
                with langfuse_prompt_attributes(prompts.system):
                    turn = await capture_with_retry(agent, question, config)
        turn["conversation_history"] = [{"question": t["question"], "answer": t["answer"]} for t in captured]
        captured.append(turn)
    return captured


def load_capture(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Read first capture per scenario from a retained v1 replay, never execute it."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("scenarios"), dict):
        raise ValueError("Capture must contain a scenarios object")
    records = {}
    for sid, item in payload["scenarios"].items():
        turns = item["repeats"][0]["turns"]
        history: list[dict[str, str]] = []
        records[sid] = []
        for turn in turns:
            seam = dict(turn["seams"])
            seam["conversation_history"] = history.copy()
            records[sid].append(seam)
            history.append({"question": seam["question"], "answer": seam["answer"]})
    return records


def score_turn(capture: dict[str, Any], scenario: dict[str, Any], names: list[str], turn_index: int, database_url: str | None = None) -> list[dict[str, Any]]:
    results = []
    for name in names:
        spec = METRIC_BY_NAME[name]
        row: dict[str, Any] = {"scenario_id": scenario["id"], "turn": turn_index + 1, "metric": name, "score": None}
        try:
            if name == "tool_correctness":
                tool_expectation = scenario.get("turn_tool_expectations")
                allowed = tool_expectation[turn_index].get("allowed") if tool_expectation else scenario.get("expected_tools", [])
                observed = capture.get("tools_called", [])
                if allowed is not None and any(tool not in allowed for tool in observed):
                    row.update(score=0.0, reason="Unexpected tool call")
                else:
                    metric = ToolCorrectnessMetric(model=NO_JUDGE, async_mode=False, should_exact_match=bool(scenario.get("tool_order")))
                    metric.measure(tool_case(capture, scenario, turn_index), _show_indicator=False)
                    row.update(score=metric.score, reason=metric.reason)
            elif name == "sql_accuracy":
                reference = scenario["reference_sql"]
                reference = reference[turn_index] if isinstance(reference, list) else reference
                if not capture.get("sql_text"):
                    row.update(score=0.0, reason="No generated SQL captured")
                else:
                    result = grade_sql(capture["sql_text"], reference, scenario.get("sql_mode", "ids_only"), database_url, scenario.get("expected_count"), scenario.get("display_limit"))
                    row.update(score=1.0 if result["status"] == "PASS" else 0.0 if result["status"] == "FAIL" else None, reason=result["status"], details=result)
            elif spec.kind == MetricKind.JUDGE:
                from evals.judge import get_judge
                test_case, params, criteria = judge_case(capture, scenario, spec)
                metric = GEval(name=name, criteria=criteria, evaluation_params=params, model=get_judge(), async_mode=False)
                metric.measure(test_case, _show_indicator=False)
                row.update(score=metric.score, reason=metric.reason)
        except Exception as exc:
            row["error"] = str(exc)
        results.append(row)
    return results


async def run_dataset(spec: DatasetSpec, *, metric_names: list[str] | None = None, ids: list[str] | None = None, capture_path: Path | None = None, database_url: str | None = None) -> dict[str, Any]:
    """Run the selected dataset; offline mode scores only scenarios in the capture."""
    from evals.env import bind_fixture_environment
    bind_fixture_environment()  # must happen before any src import
    names = metric_names or list(METRIC_BY_NAME)
    unknown = set(names) - METRIC_BY_NAME.keys()
    if unknown:
        raise ValueError(f"Unknown metrics: {sorted(unknown)}")
    if capture_path and any(METRIC_BY_NAME[name].kind == MetricKind.JUDGE for name in names):
        raise ValueError("Offline captures support deterministic metrics only")
    scenarios = spec.scenarios()
    if ids:
        unknown_ids = set(ids) - {s["id"] for s in scenarios}
        if unknown_ids:
            raise ValueError(f"Unknown scenario IDs: {sorted(unknown_ids)}")
        scenarios = [s for s in scenarios if s["id"] in ids]
    offline = load_capture(capture_path) if capture_path else None
    if offline is not None:
        missing = {s["id"] for s in scenarios if s["id"] not in offline}
        if ids and missing:
            raise ValueError(f"Requested IDs absent from capture: {sorted(missing)}")
        scenarios = [s for s in scenarios if s["id"] in offline]
        if not scenarios:
            raise ValueError("No dataset scenarios found in capture")
    else:
        from src.agents.runtime.prompts import resolve_prompt_bundle_async
        prompts = await resolve_prompt_bundle_async()
    results: list[dict[str, Any]] = []
    captures: dict[str, list[dict[str, Any]]] = {}
    consecutive_quota_failures = 0
    quota_halt = capture_settings()["consecutive_quota_failures_before_halt"]
    for position, scenario in enumerate(scenarios):
        selected = [name for name in names if name in scenario["metrics"]]
        try:
            turns = offline[scenario["id"]] if offline is not None else await capture_scenario(scenario, prompts)
        except Exception as exc:
            consecutive_quota_failures = consecutive_quota_failures + 1 if isinstance(exc, QuotaError) else 0
            for name in selected:
                results.append({"scenario_id": scenario["id"], "metric": name, "score": None, "error": str(exc)})
            if consecutive_quota_failures >= quota_halt:
                for remaining in scenarios[position + 1:]:
                    results.extend({"scenario_id": remaining["id"], "metric": name, "score": None, "reason": "UNRUN"} for name in names if name in remaining["metrics"])
                break
            continue
        consecutive_quota_failures = 0
        captures[scenario["id"]] = turns
        for index, turn in enumerate(turns):
            results.extend(score_turn(turn, scenario, selected, index, database_url))
    return {"dataset": str(spec.path), "capture_source": str(capture_path) if capture_path else "live", "generated_at": datetime.now(timezone.utc).isoformat(), "metrics": names, "captures": captures, "results": results}


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
