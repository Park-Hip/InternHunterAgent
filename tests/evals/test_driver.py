from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals import driver
from evals import harness as harness_module
from evals.harness import ProviderTelemetryCallback, SeamRun
from evals.replay import REPLAY_SCHEMA_VERSION, load_replay, validate_replay
from src.agents.runtime.prompts import load_prompt_versions
from src.agents.tracing import langfuse


@pytest.fixture(autouse=True)
def no_live_langfuse(monkeypatch: pytest.MonkeyPatch):
    """Keep `driver.run` off the network in every test in this module.

    The ingestion probe at the end of a capture is a real HTTPS call to Langfuse
    Cloud on any checkout whose `.env` carries working credentials - which is
    exactly the state the manual verification asks for. A test that forgot to patch
    it would pass today only because a broken host makes the call fail fast.
    Tests that assert on the probe override this with their own stub.
    """
    monkeypatch.setattr(
        driver,
        "verify_ingestion",
        lambda trace_id, **kwargs: {
            "trace_id": trace_id,
            "ingested": None,
            "detail": "stubbed in tests",
        },
    )


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


def test_driver_binds_tracing_to_the_evaluation_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "production")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")

    driver._bind_fixture_environment()

    fixture_url = driver.fixture_database_url()
    assert driver.os.environ["DATABASE_URL"] == fixture_url
    assert driver.os.environ["AGENT_DATABASE_URL"] == fixture_url
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

    monkeypatch.setattr(
        driver.harness, "run_single_turn_case", fake_run_single_turn_case
    )

    runs = asyncio.run(driver._capture_case(_case(), repeat_index=2))

    assert len(runs) == 1
    assert captured == {"case": _case(), "repeat": 2}


def test_harness_uses_the_request_scoped_trace_context_for_evaluation_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_calls: list[dict] = []
    validations: list[dict] = []
    observed: dict[str, object] = {}

    @asynccontextmanager
    async def request_trace(**kwargs):
        # A bare **kwargs stub accepts a call the real function rejects, which is
        # how a capture-breaking signature mismatch reached main. Bind the real
        # signature so the keywords asserted below stay checked against it.
        inspect.signature(langfuse.langfuse_request_trace).bind(**kwargs)
        trace_calls.append(kwargs)
        yield "trace-request-scoped"

    async def fake_run_turn(
        agent, message: str, config: dict, trace_id: str
    ) -> SeamRun:
        observed.update(
            {
                "agent": agent,
                "message": message,
                "callbacks": config["callbacks"],
                "trace_id": trace_id,
            }
        )
        return SeamRun(question=message, answer="a", trace_id=trace_id)

    agent = object()
    monkeypatch.setattr(driver.harness, "agent_factory", lambda: agent)
    monkeypatch.setattr(driver.harness, "CallbackHandler", lambda **kwargs: object())
    monkeypatch.setattr(
        driver.harness,
        "validate_langfuse_trace_context",
        lambda **kwargs: validations.append(kwargs),
    )
    monkeypatch.setattr(driver.harness, "langfuse_request_trace", request_trace)
    monkeypatch.setattr(driver.harness, "_run_turn", fake_run_turn)

    result = asyncio.run(driver.harness.run_single_turn_case(_case(), repeat=2))

    assert result.trace_id == "trace-request-scoped"
    assert observed["agent"] is agent
    assert observed["trace_id"] == "trace-request-scoped"
    assert validations == [
        {"entry_point": "eval:driver", "scenario_id": "HLP-TEST-1", "repeat": 2}
    ]
    assert trace_calls == [
        {
            "entry_point": "eval:driver",
            "scenario_id": "HLP-TEST-1",
            "repeat": 2,
            "trace_name": "eval-HLP-TEST-1",
        }
    ]


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


def test_manifest_records_reproducibility_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(driver, "get_langfuse_client", lambda: None)
    monkeypatch.setattr(driver, "get_langfuse_handler", lambda: None)
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
    assert set(manifest["prompt_hashes"]) == {
        "system",
        "schema_context",
        "sql_generation",
    }
    assert all(len(value) == 64 for value in manifest["prompt_hashes"].values())
    assert len(manifest["config_hash"]) == 64
    assert len(manifest["scenario_registry_hash"]) == 64
    assert manifest["worktree_state"] == "clean"
    assert manifest["baseline_eligible"] is True
    assert manifest["models"]["react"]
    assert manifest["sampling"]["sql_generation"]["temperature"] == 0.0
    assert manifest["scorer_version"] == harness_module.SCORER_VERSION
    assert manifest["prompt_versions"] == load_prompt_versions()


def test_manifest_names_each_prompt_surface_it_ran(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test-only system version change leaves unrelated lineage intact.

    T0024.1 put a version label on the prompt so runs recorded either side of a prompt
    change are never compared as if comparable. A capture that omits it leaves the
    doctrine unenforced, which is how T0024.6's change invalidated the T0025.7 baseline
    silently (M35).
    """
    monkeypatch.setattr(driver, "_worktree_state", lambda: "clean")
    _stub_fingerprint(monkeypatch)
    monkeypatch.setattr(
        driver,
        "load_prompt_versions",
        lambda: {
            "system": "v12-test-only",
            "schema_context": "v11",
            "sql_generation": "v11",
        },
    )

    assert driver.build_manifest()["prompt_versions"] == {
        "system": "v12-test-only",
        "schema_context": "v11",
        "sql_generation": "v11",
    }


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

    first = asyncio.run(
        driver.run([case], output, sleep=lambda _: asyncio.sleep(0), pacing_seconds=0)
    )
    second = asyncio.run(
        driver.run(
            [case],
            output,
            resume=True,
            sleep=lambda _: asyncio.sleep(0),
            pacing_seconds=0,
        )
    )

    assert calls == 2
    assert first["status"] == "COMPLETE"
    assert second["scenarios"][case["id"]]["status"] == "COMPLETE"
    turn = first["scenarios"][case["id"]]["repeats"][0]["turns"][0]
    assert turn["seams"]["sql_text"] == "SELECT COUNT(*) FROM clean_jobs"
    assert turn["telemetry"] == {}
    assert (
        json.loads(output.read_text(encoding="utf-8"))["manifest"]["run_id"]
        == first["manifest"]["run_id"]
    )


def test_driver_links_each_capture_to_the_repeat_dataset_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The capture links traces and records the run id; it never scores.

    Scoring left the capture loop at D-f, so the driver's remaining job here is to
    persist the dataset run `evals/score.py` will attach its scores to.
    """

    async def fake_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        return [SeamRun(question="q", answer="a", trace_id=f"trace-{repeat_index}")]

    links: list[dict] = []
    client = SimpleNamespace()
    mirror = SimpleNamespace()

    def fake_link_capture(_client, _mirror, **kwargs) -> str:
        assert _client is client
        assert _mirror is mirror
        links.append(kwargs)
        return f"dataset-run-{kwargs['repeat']}"

    monkeypatch.setattr(driver, "_capture_case", fake_capture)
    monkeypatch.setattr(driver, "_dataset_mirror", lambda: (client, mirror))
    monkeypatch.setattr(driver, "link_capture", fake_link_capture)
    monkeypatch.setattr(driver, "verify_ingestion", lambda *a, **k: {"ingested": True})
    _stub_fingerprint(monkeypatch)

    result = asyncio.run(driver.run([_case()], tmp_path / "run.json", pacing_seconds=0))

    assert [link["trace_id"] for link in links] == ["trace-1", "trace-2"]
    assert [link["repeat"] for link in links] == [1, 2]
    assert all(link["turn"] == 1 for link in links)
    assert all(link["capture_run_id"] == result["manifest"]["run_id"] for link in links)

    repeats = result["scenarios"][_case()["id"]]["repeats"]
    assert [repeat["dataset_run_id"] for repeat in repeats] == [
        "dataset-run-1",
        "dataset-run-2",
    ]


def test_capture_never_calls_the_judge_or_writes_scores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A five-minute capture must not be held open by a 46-minute judge pass.

    The regression this guards is the shape, not a number: any judge call reachable
    from `driver.run` puts scoring back inside the capture loop.
    """

    async def fake_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        return [SeamRun(question="q", answer="a", trace_id="trace-1")]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("a capture must not judge or post scores")

    monkeypatch.setattr(driver, "_capture_case", fake_capture)
    monkeypatch.setattr(driver, "_dataset_mirror", lambda: (None, None))
    monkeypatch.setattr(driver, "verify_ingestion", lambda *a, **k: {"ingested": None})
    monkeypatch.setattr(harness_module, "score_seams", fail_if_called)
    monkeypatch.setattr(harness_module, "score", fail_if_called)
    _stub_fingerprint(monkeypatch)

    result = asyncio.run(driver.run([_case()], tmp_path / "run.json", pacing_seconds=0))

    assert not hasattr(driver, "_score_case")
    assert not any(
        repeat.get("scores") for repeat in result["scenarios"][_case()["id"]]["repeats"]
    )


def test_a_completed_capture_records_whether_its_traces_were_ingested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3.9. The probe recorded five trace ids that pointed at nothing."""

    async def fake_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        return [SeamRun(question="q", answer="a", trace_id=f"trace-{repeat_index}")]

    asked: list[tuple] = []

    def fake_verify(trace_id, *, dataset_run_id=None):
        asked.append((trace_id, dataset_run_id))
        return {"trace_id": trace_id, "ingested": False, "detail": "not there"}

    monkeypatch.setattr(driver, "_capture_case", fake_capture)
    monkeypatch.setattr(driver, "_dataset_mirror", lambda: (None, None))
    monkeypatch.setattr(driver, "verify_ingestion", fake_verify)
    _stub_fingerprint(monkeypatch)

    result = asyncio.run(driver.run([_case()], tmp_path / "run.json", pacing_seconds=0))

    # The last repeat captured, not the first: see `sample_verification_target`.
    assert asked == [("trace-2", None)]
    ingestion = result["manifest"]["langfuse_ingestion"]
    assert ingestion["ingested"] is False
    assert ingestion["checked_at"]


def test_one_quota_failure_does_not_end_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single 429 costs its own repeat, not the rest of the capture (D-e, R6.1).

    DeepSeek's 429 is concurrency backpressure, so the next scenario will likely
    succeed. Halting here is what turned a blip into a PARTIAL artifact.
    """

    async def one_bad_scenario(
        case: dict, repeat_index: int, pause=None
    ) -> list[SeamRun]:
        if case["id"] == "HLP-TEST-1":
            raise RuntimeError("429 quota exceeded")
        return [SeamRun(question="q", answer="a")]

    monkeypatch.setattr(driver, "_capture_case", one_bad_scenario)
    _stub_fingerprint(monkeypatch)
    cases = [_case("HLP-TEST-1"), _case("HLP-TEST-2")]

    result = asyncio.run(
        driver.run(
            cases,
            tmp_path / "run.json",
            sleep=lambda _: asyncio.sleep(0),
            pacing_seconds=0,
        )
    )

    assert result["status"] == "COMPLETE"
    assert result["scenarios"]["HLP-TEST-1"]["status"] == "INFRA"
    assert result["scenarios"]["HLP-TEST-2"]["status"] == "COMPLETE"
    # The run-level status now means "reached the end of the registry", so the
    # manifest has to say how much of it actually succeeded.
    assert result["manifest"]["scenario_status_counts"] == {"COMPLETE": 1, "INFRA": 1}


def test_scenario_status_counts_a_clean_run_and_a_halted_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tally is present on every terminal path, not just the survivable one."""

    async def always_fine(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        return [SeamRun(question="q", answer="a")]

    monkeypatch.setattr(driver, "_capture_case", always_fine)
    _stub_fingerprint(monkeypatch)

    clean = asyncio.run(
        driver.run(
            [_case("HLP-TEST-1"), _case("HLP-TEST-2")],
            tmp_path / "clean.json",
            sleep=lambda _: asyncio.sleep(0),
            pacing_seconds=0,
        )
    )

    assert clean["manifest"]["scenario_status_counts"] == {"COMPLETE": 2}

    async def always_quota(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        raise RuntimeError("429 quota exceeded")

    monkeypatch.setattr(driver, "_capture_case", always_quota)
    cases = [_case(f"HLP-TEST-{index}") for index in range(1, 6)]

    halted = asyncio.run(
        driver.run(
            cases,
            tmp_path / "halted.json",
            sleep=lambda _: asyncio.sleep(0),
            pacing_seconds=0,
        )
    )

    assert halted["status"] == "PARTIAL_QUOTA"
    # The threshold counts failed repeats, not failed scenarios, so the first
    # scenario's two repeats plus the second's first one trip it. The tally is what
    # says how far the capture got: two scenarios attempted, three never reached.
    assert halted["manifest"]["scenario_status_counts"] == {"INFRA": 2, "UNRUN": 3}


def test_consecutive_quota_failures_still_halt_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exhausted account stops at the threshold instead of burning every scenario (R6.2)."""

    async def quota_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        raise RuntimeError("429 quota exceeded")

    monkeypatch.setattr(driver, "_capture_case", quota_capture)
    _stub_fingerprint(monkeypatch)
    threshold = driver.CONSECUTIVE_QUOTA_FAILURES_BEFORE_HALT
    cases = [_case(f"HLP-TEST-{i + 1}") for i in range(threshold + 2)]

    result = asyncio.run(
        driver.run(
            cases,
            tmp_path / "run.json",
            sleep=lambda _: asyncio.sleep(0),
            pacing_seconds=0,
        )
    )

    assert result["status"] == "PARTIAL_QUOTA"
    # The threshold counts failed repeats, and a scenario carries more than one, so
    # assert on the repeats rather than on which scenario happened to be current.
    failed_repeats = [
        repeat
        for record in result["scenarios"].values()
        for repeat in record["repeats"]
        if repeat["status"] == "INFRA"
    ]
    assert len(failed_repeats) == threshold
    # The run stopped rather than burning the whole registry.
    assert result["scenarios"][cases[-1]["id"]]["status"] == "UNRUN"


def test_a_success_between_quota_failures_resets_the_halt_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The threshold counts a run of failures, not a total, so a recovering account finishes."""
    threshold = driver.CONSECUTIVE_QUOTA_FAILURES_BEFORE_HALT
    # Alternating failure and success never reaches the threshold, however long the run.
    cases = [_case(f"HLP-TEST-{i + 1}") for i in range(threshold * 2 + 2)]
    failing = {case["id"] for case in cases[::2]}

    async def alternating(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        if case["id"] in failing:
            raise RuntimeError("429 quota exceeded")
        return [SeamRun(question="q", answer="a")]

    monkeypatch.setattr(driver, "_capture_case", alternating)
    _stub_fingerprint(monkeypatch)

    result = asyncio.run(
        driver.run(
            cases,
            tmp_path / "run.json",
            sleep=lambda _: asyncio.sleep(0),
            pacing_seconds=0,
        )
    )

    assert result["status"] == "COMPLETE"
    assert not any(
        record["status"] == "UNRUN" for record in result["scenarios"].values()
    )


def test_manifest_records_tracing_only_when_langfuse_initialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An enabled environment is not tracing when initialization left no components."""
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setattr(driver, "get_langfuse_client", lambda: None)
    monkeypatch.setattr(driver, "get_langfuse_handler", lambda: None)
    _stub_fingerprint(monkeypatch)

    assert driver.build_manifest()["tracing"]["langfuse_enabled"] is False


def test_manifest_records_tracing_when_langfuse_initialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(driver, "get_langfuse_client", lambda: object())
    monkeypatch.setattr(driver, "get_langfuse_handler", lambda: object())
    _stub_fingerprint(monkeypatch)

    assert driver.build_manifest()["tracing"]["langfuse_enabled"] is True


def test_quota_backoff_honors_the_providers_own_retry_hint() -> None:
    """A TPM window outlasts the default ladder, so the provider's stated wait wins."""
    quota = RuntimeError(
        "Error code: 429 - Rate limit reached ... on tokens per minute (TPM): "
        "Limit 8000, Used 6784, Requested 3105. Please try again in 14.1675s."
    )

    assert driver._retry_delay(quota, 0) == pytest.approx(15.1675)


def _ceiling(low: float, high: float) -> float:
    """Jitter stub taking the top of the band, so a wait reads as its ceiling."""
    return high


def test_quota_backoff_without_a_hint_starts_near_one_second() -> None:
    """A hintless 429 is concurrency backpressure, not a window to outlast (R6.3).

    The retired 20s/40s ladder was sized for Groq's per-minute token window. On
    DeepSeek there is no window, so the first wait is about a second.
    """
    quota = RuntimeError("429 rate_limit_exceeded: quota exhausted")
    ceiling = _ceiling

    assert driver._retry_delay(quota, 0, jitter=ceiling) == pytest.approx(1.0)
    assert driver._retry_delay(quota, 1, jitter=ceiling) == pytest.approx(2.0)
    assert driver._retry_delay(quota, 2, jitter=ceiling) == pytest.approx(4.0)
    # The cap still binds, so a long run of retries cannot wait unboundedly.
    assert driver._retry_delay(quota, 40, jitter=ceiling) == driver.MAX_BACKOFF_SECONDS


def test_quota_backoff_jitters_within_the_equal_jitter_band() -> None:
    """Concurrent retries must not resynchronise on one instant."""
    quota = RuntimeError("429 rate_limit_exceeded: quota exhausted")

    waits = {driver._retry_delay(quota, 3) for _ in range(50)}

    assert len(waits) > 1
    assert all(4.0 <= wait <= 8.0 for wait in waits)


def test_retry_hint_is_capped_and_non_quota_errors_keep_the_short_ladder() -> None:
    assert (
        driver._retry_delay(RuntimeError("try again in 3600s"), 0)
        == driver.MAX_BACKOFF_SECONDS
    )
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
    result = asyncio.run(
        driver.run([_case()], tmp_path / "run.json", sleep=record, pacing_seconds=0)
    )

    # Two waits per repeat, and both of the scenario's repeats now run: a 429 no
    # longer ends the capture at the first one (R6.1).
    assert slept == [13.0, 13.0, 13.0, 13.0]
    assert [event["delay_seconds"] for event in result["manifest"]["retry_events"]] == [
        13.0,
        13.0,
        13.0,
        13.0,
    ]


def test_diff_reports_changed_prompt_surfaces_without_invalidating_the_others(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    payload = driver._new_run(
        {
            "run_id": "a",
            "fixture_hash": "same",
            "prompt_versions": {
                "system": "v1",
                "schema_context": "v1",
                "sql_generation": "v1",
            },
            "prompt_hashes": {
                "system": "one",
                "schema_context": "one",
                "sql_generation": "one",
            },
            "config_hash": "same",
            "scenario_registry_hash": "same",
            "worktree_state": "clean",
        }
    )
    left.write_text(json.dumps(payload), encoding="utf-8")
    payload["manifest"]["run_id"] = "b"
    payload["manifest"]["prompt_versions"]["system"] = "v2"
    payload["manifest"]["prompt_hashes"]["system"] = "two"
    right.write_text(json.dumps(payload), encoding="utf-8")

    comparison = driver.compare_runs(left, right)

    assert comparison["comparable"] is False
    assert comparison["prompt_surfaces"]["system"]["comparable"] is False
    assert comparison["prompt_surfaces"]["schema_context"]["comparable"] is True
    assert comparison["prompt_surfaces"]["sql_generation"]["comparable"] is True


def test_dirty_worktree_is_not_baseline_eligible_or_comparable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        return [
            SeamRun(
                question="q",
                answer="a",
                tools_called=[],
                tool_output=None,
                sql_text=None,
            )
        ]

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
            SeamRun(
                question="q",
                answer="a",
                tools_called=[],
                tool_output=None,
                sql_text=None,
            )
        ], None

    async def record(delay: float) -> None:
        waited.append(delay)

    monkeypatch.setattr(driver.harness, "run_conversational_case", fake_conversational)
    monkeypatch.setattr(driver, "repeat_count", lambda case: 1)
    _stub_fingerprint(monkeypatch)
    case = {**_case(), "type": "conversational", "turns": ["first", "second"]}
    asyncio.run(
        driver.run([case], tmp_path / "run.json", sleep=record, pacing_seconds=60.0)
    )

    assert paused_before_turn == [1]
    assert waited == [60.0]


def test_pacing_is_recorded_in_the_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(driver, "_git_sha", lambda: "abc123")
    monkeypatch.setattr(driver, "_worktree_state", lambda: "clean")
    _stub_fingerprint(monkeypatch)

    assert (
        driver.build_manifest()["turn_pacing_seconds"]
        == driver.load_turn_pacing_seconds()
    )


def test_provider_telemetry_preserves_reported_usage_and_finish_reason() -> None:
    callback = ProviderTelemetryCallback()
    message = SimpleNamespace(
        usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        response_metadata={"finish_reason": "stop"},
    )
    callback.on_llm_end(
        SimpleNamespace(
            llm_output={
                "token_usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                }
            },
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
            capture_repeats.append(
                {
                    "repeat": repeat["repeat"],
                    "status": "COMPLETE",
                    "turns": capture_turns,
                }
            )
        capture["scenarios"][scenario_id] = {
            "status": "COMPLETE",
            "repeats": capture_repeats,
        }
        grade["scenarios"][scenario_id] = grade_entries
    return capture, grade


def test_freeze_projects_a_capture_into_a_valid_sanitized_replay(
    tmp_path: Path,
) -> None:
    capture, grade = _capture_and_grade_from_replay()
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    driver.main(
        ["freeze", str(capture_path), "--grade", str(grade_path), "-o", str(output)]
    )
    frozen = json.loads(output.read_text(encoding="utf-8"))

    validate_replay(frozen)
    assert frozen["manifest"] == {
        "run_id": "capture-123",
        "schema_version": 3,
        "source_capture": "capture.json",
        "sanitized": True,
        "prompt_version": "v-test",
    }
    encoded = output.read_text(encoding="utf-8")
    assert "trace_id" not in encoded
    assert "latency_ms" not in encoded


def test_freeze_preserves_each_named_prompt_surface_for_a_test_only_version_change(
    tmp_path: Path,
) -> None:
    capture, grade = _capture_and_grade_from_replay()
    capture["manifest"] = {
        "run_id": "capture-123",
        "prompt_versions": {
            "system": "v12-test-only",
            "schema_context": "v11",
            "sql_generation": "v11",
        },
        "prompt_hashes": {
            "system": "one",
            "schema_context": "two",
            "sql_generation": "three",
        },
    }
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    frozen = driver.freeze_capture(capture_path, grade_path, output)

    assert frozen["manifest"]["schema_version"] == REPLAY_SCHEMA_VERSION
    assert frozen["manifest"]["prompt_versions"] == {
        "system": "v12-test-only",
        "schema_context": "v11",
        "sql_generation": "v11",
    }


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


def test_freeze_sanitizes_langfuse_metadata_and_retains_replay_evidence(
    tmp_path: Path,
) -> None:
    capture, grade = _capture_and_grade_from_replay()
    capture["manifest"]["langfuse_ingestion"] = {
        "trace_id": "live-trace",
        "ingested": True,
    }
    seams = capture["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0]["seams"]
    seams["trace_id"] = "live-trace"
    seams["tool_output"] = "Found 1 result(s) with columns: id.\n- id=7"
    seams["tool_arguments"] = [{"name": "query_clean_jobs", "arguments": {"q": "jobs"}}]
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    frozen = driver.freeze_capture(capture_path, grade_path, output)

    validate_replay(frozen)
    frozen_seams = frozen["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0]["seams"]
    assert frozen_seams == {
        "question": seams["question"],
        "answer": seams["answer"],
        "tools_called": seams["tools_called"],
        "tool_output": seams["tool_output"],
        "tool_arguments": seams["tool_arguments"],
        "sql_text": seams["sql_text"],
    }
    assert "trace_id" not in output.read_text(encoding="utf-8")
    assert "langfuse" not in output.read_text(encoding="utf-8")


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


def test_freeze_preserves_a_not_evaluated_execution_result(tmp_path: Path) -> None:
    capture, grade = _capture_and_grade_from_replay()
    grade["scenarios"]["HON-CURRENCY-1"][0]["checks"][0] = {
        "name": "execution_accuracy",
        "passed": None,
        "detail": "execution accuracy is NOT_EVALUATED",
        "outcome": "NOT_EVALUATED",
    }
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    frozen = driver.freeze_capture(capture_path, grade_path, output)

    turn = frozen["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0]
    assert turn["expected_execution_accuracy"] == "NOT_EVALUATED"


def test_freeze_preserves_a_not_evaluated_grade(tmp_path: Path) -> None:
    capture, grade = _capture_and_grade_from_replay()
    grade["scenarios"]["HON-CURRENCY-1"][0]["status"] = "NOT_EVALUATED"
    capture_path = tmp_path / "capture.json"
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "frozen.json"
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    grade_path.write_text(json.dumps(grade), encoding="utf-8")

    frozen = driver.freeze_capture(capture_path, grade_path, output)

    validate_replay(frozen)
    turn = frozen["scenarios"]["HON-CURRENCY-1"]["repeats"][0]["turns"][0]
    assert turn["expected_grade"] == "NOT_EVALUATED"


def test_freeze_derives_an_exempt_execution_result_from_the_registry(
    tmp_path: Path,
) -> None:
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


def test_freeze_projects_completed_evidence_from_a_partial_quota_capture(
    tmp_path: Path,
) -> None:
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


def test_a_resumed_capture_verifies_its_own_traces_not_the_previous_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The probe samples the newest turn, so a resume cannot inherit a stale verdict.

    Session one traced fine and stopped; session two continues into a Langfuse that
    is no longer reachable. Sampling the first recorded id would resolve session
    one's trace and report the run as ingested.
    """
    output = tmp_path / "run.json"
    output.write_text(
        json.dumps(
            {
                "status": "PARTIAL_QUOTA",
                "manifest": {"run_id": "run-1"},
                "scenarios": {
                    "COUNT-1": {
                        "status": "COMPLETE",
                        "repeats": [
                            {
                                "repeat": 1,
                                "status": "COMPLETE",
                                "dataset_run_id": "session-1-run",
                                "turns": [
                                    {"turn": 1, "seams": {"trace_id": "trace-session-1"}}
                                ],
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    async def fake_capture(case: dict, repeat_index: int, pause=None) -> list[SeamRun]:
        return [SeamRun(question="q", answer="a", trace_id="trace-session-2")]

    asked: list[tuple] = []

    def fake_verify(trace_id, *, dataset_run_id=None):
        asked.append((trace_id, dataset_run_id))
        return {"trace_id": trace_id, "ingested": False, "detail": "not there"}

    monkeypatch.setattr(driver, "_capture_case", fake_capture)
    monkeypatch.setattr(driver, "_dataset_mirror", lambda: (None, None))
    monkeypatch.setattr(driver, "verify_ingestion", fake_verify)
    _stub_fingerprint(monkeypatch)

    result = asyncio.run(
        driver.run(
            [_case(), _case("HLP-LIST-1")], output, resume=True, pacing_seconds=0
        )
    )

    assert asked == [("trace-session-2", None)]
    assert result["manifest"]["langfuse_ingestion"]["ingested"] is False
