from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals import driver
from evals.harness import ProviderTelemetryCallback, SeamRun
from evals.replay import REPLAY_SCHEMA_VERSION, load_replay, validate_replay
from src.agents.runtime.prompts import load_prompt_version


def test_resolving_the_fixture_url_never_freezes_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The driver discovers the fixture DSN *before* it binds DATABASE_URL.

    src.core.config caches Settings() on first construction, reading DATABASE_URL
    from the environment and .env. If resolving the fixture URL constructed
    Settings, the cache would freeze against the serving database and the
    driver's later bind would be silently ignored - running a capture against
    production data. Keep this resolution free of src.core.config.
    """
    import src.core.config as config

    def fail_if_called() -> None:
        raise AssertionError("resolving the fixture URL must not construct Settings()")

    monkeypatch.setattr(config, "load_settings", fail_if_called)

    assert driver.fixture_database_url().startswith("postgresql")


def test_driver_binds_tracing_to_the_evaluation_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "production")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")

    driver._bind_fixture_environment()

    assert driver.os.environ["LANGFUSE_TRACING_ENVIRONMENT"] == "evaluation"
    assert driver.os.environ["LANGFUSE_ENABLED"] == "false"


def test_capture_case_passes_the_driver_repeat_to_evaluation_tracing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run_single_turn_case(case: dict, *, repeat: int) -> SeamRun:
        captured["case"] = case
        captured["repeat"] = repeat
        return SeamRun(question="q", answer="a")

    monkeypatch.setattr(driver.harness, "run_single_turn_case", fake_run_single_turn_case)

    runs = asyncio.run(driver._capture_case(_case(), repeat_index=2))

    assert len(runs) == 1
    assert captured == {"case": _case(), "repeat": 2}


def _stub_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep build_manifest() off a live database.

    Every path through build_manifest() calls _database_fingerprint, which opens a real
    connection to the fixture DSN. CI runs pytest before evals.fixtures.loader, so the
    fixture schema does not exist yet and the call raises; on a developer machine with no
    eval Postgres listening it instead hangs for the full TCP connect timeout. Both are
    environment, not behavior, so every manifest-exercising test stubs this.
    """
    monkeypatch.setattr(
        driver, "_database_fingerprint", lambda url: ("d" * 64, "internhunter_eval", 22)
    )


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
    monkeypatch.setattr(driver, "_worktree_state", lambda: "clean")
    _stub_fingerprint(monkeypatch)
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
    assert len(manifest["scenario_registry_hash"]) == 64
    assert manifest["worktree_state"] == "clean"
    assert manifest["baseline_eligible"] is True
    assert manifest["models"]["react"]
    assert manifest["sampling"]["sql_generation"]["temperature"] == 0.0
    assert manifest["scorer_version"] == driver.SCORER_VERSION
    assert manifest["prompt_version"] == load_prompt_version()


def test_manifest_names_the_prompt_it_ran(monkeypatch: pytest.MonkeyPatch) -> None:
    """prompt_hash proves two runs used different prompts; only the version says which.

    T0024.1 put a version label on the prompt so runs recorded either side of a prompt
    change are never compared as if comparable. A capture that omits it leaves the
    doctrine unenforced, which is how T0024.6's change invalidated the T0025.7 baseline
    silently (M35).
    """
    monkeypatch.setattr(driver, "_worktree_state", lambda: "clean")
    _stub_fingerprint(monkeypatch)
    monkeypatch.setattr(driver, "load_prompt_version", lambda: "v9")

    assert driver.build_manifest()["prompt_version"] == "v9"


def test_driver_persists_all_seams_and_resumes_completed_scenario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    async def fake_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
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
    _stub_fingerprint(monkeypatch)
    output = tmp_path / "run.json"
    case = _case()

    first = asyncio.run(driver.run([case], output, sleep=lambda _: asyncio.sleep(0), pacing_seconds=0))
    second = asyncio.run(driver.run([case], output, resume=True, sleep=lambda _: asyncio.sleep(0), pacing_seconds=0))

    assert calls == 2
    assert first["status"] == "COMPLETE"
    assert second["scenarios"][case["id"]]["status"] == "COMPLETE"
    turn = first["scenarios"][case["id"]]["repeats"][0]["turns"][0]
    assert turn["seams"]["sql_text"] == "SELECT COUNT(*) FROM clean_jobs"
    assert turn["telemetry"] == {}
    assert json.loads(output.read_text(encoding="utf-8"))["manifest"]["run_id"] == first["manifest"]["run_id"]


def test_quota_exhaustion_marks_remaining_scenarios_unrun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def quota_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        raise RuntimeError("429 quota exceeded")

    monkeypatch.setattr(driver, "_capture_case", quota_capture)
    _stub_fingerprint(monkeypatch)
    output = tmp_path / "run.json"
    cases = [_case("HLP-TEST-1"), _case("HLP-TEST-2")]

    result = asyncio.run(driver.run(cases, output, sleep=lambda _: asyncio.sleep(0), pacing_seconds=0))

    assert result["status"] == "PARTIAL_QUOTA"
    assert result["scenarios"]["HLP-TEST-1"]["status"] == "INFRA"
    assert result["scenarios"]["HLP-TEST-2"]["status"] == "UNRUN"


def test_manifest_records_tracing_when_operator_opts_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """An operator who enables Langfuse must not get a manifest claiming tracing was off."""
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setattr(driver, "_git_sha", lambda: "abc123")
    _stub_fingerprint(monkeypatch)

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

    async def quota_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        raise RuntimeError("429 tokens per minute. Please try again in 12s.")

    async def record(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(driver, "_capture_case", quota_capture)
    _stub_fingerprint(monkeypatch)
    result = asyncio.run(driver.run([_case()], tmp_path / "run.json", sleep=record, pacing_seconds=0))

    assert slept == [13.0, 13.0]
    assert [event["delay_seconds"] for event in result["manifest"]["retry_events"]] == [13.0, 13.0]


def test_diff_refuses_different_inputs(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    payload = driver._new_run(
        {
            "run_id": "a",
            "fixture_hash": "same",
            "prompt_hash": "one",
            "config_hash": "same",
            "scenario_registry_hash": "same",
            "worktree_state": "clean",
        }
    )
    left.write_text(json.dumps(payload), encoding="utf-8")
    payload["manifest"]["run_id"] = "b"
    payload["manifest"]["prompt_hash"] = "two"
    right.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="prompt_hash"):
        driver.compare_runs(left, right)


def test_dirty_worktree_is_not_baseline_eligible_or_comparable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(driver, "_worktree_state", lambda: "dirty")
    _stub_fingerprint(monkeypatch)
    manifest = driver.build_manifest()

    assert manifest["baseline_eligible"] is False
    with pytest.raises(ValueError, match="dirty or unknown"):
        driver._assert_comparable({"manifest": manifest}, {"manifest": manifest})


def test_turns_are_paced_so_each_meets_an_unspent_quota_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One turn asks for more than a per-minute window holds alongside its
    predecessor, so every turn after the first waits the window out."""
    waited: list[float] = []

    async def fake_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        return [SeamRun(question="q", answer="a", tools_called=[], tool_output=None, sql_text=None)]

    async def record(delay: float) -> None:
        waited.append(delay)

    monkeypatch.setattr(driver, "_capture_case", fake_capture)
    monkeypatch.setattr(driver, "repeat_count", lambda case: 3)
    _stub_fingerprint(monkeypatch)
    asyncio.run(
        driver.run([_case()], tmp_path / "run.json", sleep=record, pacing_seconds=60.0)
    )

    assert waited == [60.0, 60.0]


def test_conversational_turns_pace_between_themselves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pause reaches inside a multi-turn case; its second turn would
    otherwise spend the window its first turn just filled."""
    waited: list[float] = []
    paused_before_turn: list[int] = []

    async def fake_conversational(case: dict, repeat: int, pause=None):
        for turn_index in range(2):
            if turn_index and pause is not None:
                await pause()
                paused_before_turn.append(turn_index)
        return [
            SeamRun(question="q", answer="a", tools_called=[], tool_output=None, sql_text=None)
        ], None

    async def record(delay: float) -> None:
        waited.append(delay)

    monkeypatch.setattr(driver.harness, "run_conversational_case", fake_conversational)
    monkeypatch.setattr(driver, "repeat_count", lambda case: 1)
    _stub_fingerprint(monkeypatch)
    case = {**_case(), "type": "conversational", "turns": ["first", "second"]}
    asyncio.run(driver.run([case], tmp_path / "run.json", sleep=record, pacing_seconds=60.0))

    assert paused_before_turn == [1]
    assert waited == [60.0]


def test_pacing_is_recorded_in_the_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(driver, "_git_sha", lambda: "abc123")
    monkeypatch.setattr(driver, "_worktree_state", lambda: "clean")
    _stub_fingerprint(monkeypatch)

    assert driver.build_manifest()["turn_pacing_seconds"] == driver.load_turn_pacing_seconds()


def test_provider_telemetry_preserves_reported_usage_and_finish_reason() -> None:
    callback = ProviderTelemetryCallback()
    message = SimpleNamespace(
        usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        response_metadata={"finish_reason": "stop"},
    )
    callback.on_llm_end(
        SimpleNamespace(
            llm_output={"token_usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}},
            generations=[[SimpleNamespace(message=message, generation_info={})]],
        )
    )

    telemetry = callback.snapshot(latency_ms=42)

    assert telemetry["latency_ms"] == 42
    assert telemetry["provider_token_usage"]["aggregate"] == {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
    }
    assert telemetry["finish_reasons"] == ["stop"]


def test_provider_telemetry_marks_missing_provider_fields_unavailable() -> None:
    callback = ProviderTelemetryCallback()
    callback.on_llm_end(SimpleNamespace(llm_output=None, generations=[]))

    telemetry = callback.snapshot(latency_ms=1)

    assert telemetry["provider_token_usage"]["calls"] == [
        {
            "input_tokens": "unavailable",
            "output_tokens": "unavailable",
            "total_tokens": "unavailable",
            "finish_reason": "unavailable",
        }
    ]
    assert telemetry["finish_reasons"] == ["unavailable"]


def _capture_and_grade_from_replay() -> tuple[dict, dict]:
    replay = load_replay()
    capture = {
        "manifest": {"run_id": "capture-123", "prompt_version": "v-test"},
        "status": "COMPLETE",
        "scenarios": {},
    }
    grade = {"run_id": "capture-123", "scenarios": {}}
    for scenario_id, scenario in replay["scenarios"].items():
        capture_repeats = []
        grade_entries = []
        for repeat in scenario["repeats"]:
            capture_turns = []
            for turn in repeat["turns"]:
                capture_turns.append(
                    {
                        "turn": turn["turn"],
                        "status": "COMPLETE",
                        "seams": {**turn["seams"], "trace_id": None},
                        "telemetry": {"latency_ms": 42},
                    }
                )
                grade_entries.append(
                    {
                        "repeat": repeat["repeat"],
                        "turn": turn["turn"],
                        "status": turn["expected_grade"],
                        "checks": [
                            {
                                "name": "execution_accuracy",
                                "passed": turn["expected_execution_accuracy"] != "FAIL",
                                "detail": f"execution accuracy {turn['expected_execution_accuracy']}",
                            }
                        ],
                    }
                )
            capture_repeats.append({"repeat": repeat["repeat"], "status": "COMPLETE", "turns": capture_turns})
        capture["scenarios"][scenario_id] = {"status": "COMPLETE", "repeats": capture_repeats}
        grade["scenarios"][scenario_id] = grade_entries
    return capture, grade


def test_freeze_projects_a_capture_into_a_valid_sanitized_replay(tmp_path: Path) -> None:
    capture, grade = _capture_and_grade_from_replay()
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    driver.main(["freeze", str(capture_path), "--grade", str(grade_path), "-o", str(output)])
    frozen = json.loads(output.read_text(encoding="utf-8"))

    validate_replay(frozen)
    assert frozen["manifest"] == {
        "run_id": "capture-123",
        "schema_version": REPLAY_SCHEMA_VERSION,
        "source_capture": "capture.json",
        "sanitized": True,
        "prompt_version": "v-test",
    }
    encoded = output.read_text(encoding="utf-8")
    assert "trace_id" not in encoded
    assert "latency_ms" not in encoded


def test_freeze_refuses_a_capture_that_cannot_name_its_prompt(tmp_path: Path) -> None:
    """An unlabelled capture must not become a labelled-looking replay."""
    capture, grade = _capture_and_grade_from_replay()
    del capture["manifest"]["prompt_version"]
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    with pytest.raises(ValueError, match="prompt_version"):
        driver.freeze_capture(capture_path, grade_path, output)

    assert not output.exists()


def test_freeze_refuses_a_capture_with_a_live_trace_id(tmp_path: Path) -> None:
    capture, grade = _capture_and_grade_from_replay()
    capture["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0]["seams"]["trace_id"] = "live-trace"
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    with pytest.raises(ValueError, match="trace_id"):
        driver.freeze_capture(capture_path, grade_path, output)

    assert not output.exists()


def test_freeze_preserves_a_failed_execution_result(tmp_path: Path) -> None:
    capture, grade = _capture_and_grade_from_replay()
    grade["scenarios"]["HON-CURRENCY-1"][0]["checks"][0] = {
        "name": "execution_accuracy",
        "passed": False,
        "detail": "execution accuracy is FAIL",
    }
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    frozen = driver.freeze_capture(capture_path, grade_path, output)

    validate_replay(frozen)
    turn = frozen["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0]
    assert turn["expected_execution_accuracy"] == "FAIL"


def test_freeze_derives_an_exempt_execution_result_from_the_registry(tmp_path: Path) -> None:
    capture, grade = _capture_and_grade_from_replay()
    grade["scenarios"]["HON-SQL-DESCRIBE-1"][0]["checks"] = []
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    frozen = driver.freeze_capture(capture_path, grade_path, output)

    turn = frozen["scenarios"]["HON-SQL-DESCRIBE-1"]["repeats"][0]["turns"][0]
    assert turn["expected_execution_accuracy"] == "EXEMPT"


def test_freeze_projects_completed_evidence_from_a_partial_quota_capture(tmp_path: Path) -> None:
    capture, grade = _capture_and_grade_from_replay()
    capture["status"] = "PARTIAL_QUOTA"
    capture["scenarios"]["HLP-COUNT-1"] = {"status": "INFRA", "repeats": []}
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    frozen = driver.freeze_capture(capture_path, grade_path, output)

    validate_replay(frozen)
    assert "HLP-COUNT-1" not in frozen["scenarios"]
