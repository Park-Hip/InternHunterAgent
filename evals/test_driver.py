from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from evals import driver
from evals.harness import SeamRun


def _case(scenario_id: str = "HLP-TEST-1", probe: bool = False) -> dict:
    return {
        "id": scenario_id,
        "type": "single",
        "input": "How many jobs are there?",
        "expected": "a count",
        "probe": probe,
    }


def test_manifest_records_reproducibility_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setattr(driver, "_git_sha", lambda: "abc123")
    monkeypatch.setattr(
        driver,
        "_database_fingerprint",
        lambda url: ("d" * 64, "internhunter_eval", 22),
    )
    manifest = driver.build_manifest()

    assert manifest["git_sha"] == "abc123"
    assert len(manifest["fixture_hash"]) == 64
    assert manifest["database_name"] == "internhunter_eval"
    assert manifest["database_row_count"] == 22
    assert manifest["retry_policy"]["provider_sdk_max_retries"] == 0
    assert manifest["retry_policy"]["honors_provider_retry_hint"] is True
    assert manifest["tracing"]["langfuse_enabled"] is False
    assert len(manifest["prompt_hash"]) == 64
    assert len(manifest["config_hash"]) == 64
    assert manifest["models"]["react"]
    assert manifest["sampling"]["sql_generation"]["temperature"] == 0.0
    assert manifest["scorer_version"] == driver.SCORER_VERSION


def test_driver_persists_all_seams_and_resumes_completed_scenario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    async def fake_capture(case: dict) -> list[SeamRun]:
        nonlocal calls
        calls += 1
        return [
            SeamRun(
                question=case["input"],
                answer="There are 2 jobs.",
                tools_called=["query_clean_jobs"],
                tool_output="[(2,)]",
                sql_text="SELECT COUNT(*) FROM clean_jobs",
                trace_id="trace-1",
            )
        ]

    monkeypatch.setattr(driver, "_capture_case", fake_capture)
    output = tmp_path / "run.json"
    case = _case()

    first = asyncio.run(driver.run([case], output, sleep=lambda _: asyncio.sleep(0)))
    second = asyncio.run(driver.run([case], output, resume=True, sleep=lambda _: asyncio.sleep(0)))

    assert calls == 2
    assert first["status"] == "COMPLETE"
    assert second["scenarios"][case["id"]]["status"] == "COMPLETE"
    turn = first["scenarios"][case["id"]]["repeats"][0]["turns"][0]
    assert turn["seams"]["sql_text"] == "SELECT COUNT(*) FROM clean_jobs"
    assert json.loads(output.read_text(encoding="utf-8"))["manifest"]["run_id"] == first["manifest"]["run_id"]


def test_quota_exhaustion_marks_remaining_scenarios_unrun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def quota_capture(case: dict) -> list[SeamRun]:
        raise RuntimeError("429 quota exceeded")

    monkeypatch.setattr(driver, "_capture_case", quota_capture)
    output = tmp_path / "run.json"
    cases = [_case("HLP-TEST-1"), _case("HLP-TEST-2")]

    result = asyncio.run(driver.run(cases, output, sleep=lambda _: asyncio.sleep(0)))

    assert result["status"] == "PARTIAL_QUOTA"
    assert result["scenarios"]["HLP-TEST-1"]["status"] == "INFRA"
    assert result["scenarios"]["HLP-TEST-2"]["status"] == "UNRUN"


def test_manifest_records_tracing_when_operator_opts_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """An operator who enables Langfuse must not get a manifest claiming tracing was off."""
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setattr(driver, "_git_sha", lambda: "abc123")
    monkeypatch.setattr(
        driver, "_database_fingerprint", lambda url: ("d" * 64, "internhunter_eval", 22)
    )

    assert driver.build_manifest()["tracing"]["langfuse_enabled"] is True


def test_quota_backoff_honors_the_providers_own_retry_hint() -> None:
    """A TPM window outlasts the default ladder, so the provider's stated wait wins."""
    quota = RuntimeError(
        "Error code: 429 - Rate limit reached ... on tokens per minute (TPM): "
        "Limit 8000, Used 6784, Requested 3105. Please try again in 14.1675s."
    )

    assert driver._retry_delay(quota, 0) == pytest.approx(15.1675)


def test_quota_backoff_without_a_hint_outlasts_a_per_minute_window() -> None:
    quota = RuntimeError("429 rate_limit_exceeded: quota exhausted")

    assert driver._retry_delay(quota, 0) >= 20.0
    assert driver._retry_delay(quota, 1) >= 40.0


def test_retry_hint_is_capped_and_non_quota_errors_keep_the_short_ladder() -> None:
    assert driver._retry_delay(RuntimeError("try again in 3600s"), 0) == driver.MAX_BACKOFF_SECONDS
    assert driver._retry_delay(RuntimeError("connection reset"), 0) == 1.0
    assert driver._retry_delay(RuntimeError("connection reset"), 1) == 2.0


def test_quota_retry_records_the_delay_it_actually_waited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []

    async def quota_capture(case: dict) -> list[SeamRun]:
        raise RuntimeError("429 tokens per minute. Please try again in 12s.")

    async def record(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(driver, "_capture_case", quota_capture)
    result = asyncio.run(driver.run([_case()], tmp_path / "run.json", sleep=record))

    assert slept == [13.0, 13.0]
    assert [event["delay_seconds"] for event in result["manifest"]["retry_events"]] == [13.0, 13.0]


def test_diff_refuses_different_inputs(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    payload = driver._new_run({"run_id": "a", "fixture_hash": "same", "prompt_hash": "one", "config_hash": "same"})
    left.write_text(json.dumps(payload), encoding="utf-8")
    payload["manifest"]["run_id"] = "b"
    payload["manifest"]["prompt_hash"] = "two"
    right.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="prompt_hash"):
        driver.compare_runs(left, right)
