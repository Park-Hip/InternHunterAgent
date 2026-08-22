"""No-network unit tests for `evals/writeback.py` — a fake Langfuse client
stands in for the real SDK so these run without creds or a live server."""

from __future__ import annotations

from types import SimpleNamespace

from langfuse.api import NotFoundError

from evals import writeback

flushes: list[int] = []


class FakeLangfuseClient:
    def __init__(self) -> None:
        self.scores: list[dict] = []
        self.flush_calls = 0

    def create_score(self, **kwargs) -> None:
        self.scores.append(kwargs)

    def flush(self) -> None:
        self.flush_calls += 1


def _enable_fake_langfuse(monkeypatch, fake: FakeLangfuseClient) -> None:
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: object())
    monkeypatch.setattr(writeback, "get_langfuse_client", lambda: fake)


def test_writes_every_non_none_score(monkeypatch):
    fake = FakeLangfuseClient()
    _enable_fake_langfuse(monkeypatch, fake)

    results = {
        "seam1_routing": {"Tool Correctness": {"score": 1.0, "reason": "ok"}},
        "seam3_synthesis": {"Faithfulness": {"score": 0.8, "reason": None}},
    }

    written = writeback.write_scores("trace-123", results)

    assert written == 2
    names = {call["name"] for call in fake.scores}
    assert names == {"seam1_routing/Tool Correctness", "seam3_synthesis/Faithfulness"}
    for call in fake.scores:
        assert call["data_type"] == "NUMERIC"
        assert call["trace_id"] == "trace-123"


def test_skips_none_scored_metrics(monkeypatch):
    fake = FakeLangfuseClient()
    _enable_fake_langfuse(monkeypatch, fake)

    results = {
        "seam1_routing": {"Argument Correctness": {"score": None, "error": "boom"}}
    }

    written = writeback.write_scores("trace-123", results)

    assert written == 0
    assert fake.scores == []


def test_trace_id_none_is_a_noop(monkeypatch):
    fake = FakeLangfuseClient()
    _enable_fake_langfuse(monkeypatch, fake)

    written = writeback.write_scores(None, {"seam1_routing": {"X": {"score": 1.0}}})

    assert written == 0
    assert fake.scores == []
    assert fake.flush_calls == 0


def test_disabled_langfuse_is_a_noop(monkeypatch):
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: None)

    written = writeback.write_scores(
        "trace-123", {"seam1_routing": {"X": {"score": 1.0}}}
    )

    assert written == 0


def test_same_metric_name_across_seams_gets_distinct_score_ids(monkeypatch):
    fake = FakeLangfuseClient()
    _enable_fake_langfuse(monkeypatch, fake)

    results = {
        "seam1_routing": {"Argument Correctness": {"score": 1.0}},
        "seam2_nl_to_sql": {"Argument Correctness": {"score": 0.5}},
    }

    writeback.write_scores("trace-abc", results)

    score_ids = {call["score_id"] for call in fake.scores}
    assert len(score_ids) == 2


def test_flush_called_once_when_scores_written(monkeypatch):
    fake = FakeLangfuseClient()
    _enable_fake_langfuse(monkeypatch, fake)

    writeback.write_scores("trace-123", {"seam1_routing": {"X": {"score": 1.0}}})

    assert fake.flush_calls == 1


class FakeTraceAPI:
    def __init__(self, known: set[str], *, appears_on_attempt: int = 1) -> None:
        self.known = known
        self.appears_on_attempt = appears_on_attempt
        self.asked: list[str] = []

    def get(self, trace_id: str):
        self.asked.append(trace_id)
        if trace_id not in self.known or len(self.asked) < self.appears_on_attempt:
            raise NotFoundError(f"no trace {trace_id}")
        return {"id": trace_id}


def _client_with_traces(monkeypatch, known: set[str], **kwargs) -> FakeTraceAPI:
    trace_api = FakeTraceAPI(known, **kwargs)
    fake = SimpleNamespace(
        api=SimpleNamespace(trace=trace_api), flush=lambda: flushes.append(1)
    )
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: object())
    monkeypatch.setattr(writeback, "get_langfuse_client", lambda: fake)
    return trace_api


def test_an_ingested_trace_verifies(monkeypatch):
    trace_api = _client_with_traces(monkeypatch, {"trace-123"})

    record = writeback.verify_ingestion(
        "trace-123", dataset_run_id="run-9", sleep=lambda _: None
    )

    assert record["ingested"] is True
    assert record["dataset_run_id"] == "run-9"
    assert trace_api.asked == ["trace-123"]


def test_a_trace_id_that_names_nothing_is_not_ingested(monkeypatch):
    """The 2026-08-21 probe recorded five ids exactly like this one."""
    _client_with_traces(monkeypatch, set())

    record = writeback.verify_ingestion("trace-123", sleep=lambda _: None)

    assert record["ingested"] is False
    assert "no trace" in record["detail"]


def test_an_unreachable_langfuse_is_not_a_verdict(monkeypatch):
    """None and False are different findings: not asked, versus asked and absent."""

    class Exploding:
        def get(self, trace_id: str):
            raise RuntimeError("connection refused")

    fake = SimpleNamespace(api=SimpleNamespace(trace=Exploding()), flush=lambda: None)
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: object())
    monkeypatch.setattr(writeback, "get_langfuse_client", lambda: fake)

    record = writeback.verify_ingestion("trace-123", sleep=lambda _: None)

    assert record["ingested"] is None
    assert "connection refused" in record["detail"]


def test_verification_without_tracing_is_not_a_verdict(monkeypatch):
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: None)

    assert writeback.verify_ingestion("trace-123")["ingested"] is None
    assert writeback.verify_ingestion(None)["ingested"] is None


def test_verification_flushes_and_waits_for_asynchronous_ingestion(monkeypatch):
    """Export is batched and Cloud ingestion is not synchronous with the API call.

    A two-scenario capture finishes in seconds, well inside that window, so a probe
    that asked once without draining would report a healthy run as un-ingested.
    """
    flushes.clear()
    waits: list[float] = []
    trace_api = _client_with_traces(monkeypatch, {"trace-123"}, appears_on_attempt=3)

    record = writeback.verify_ingestion("trace-123", sleep=waits.append)

    assert record["ingested"] is True
    assert flushes == [1]
    assert len(trace_api.asked) == 3
    assert waits == [2.0, 5.0]


def test_verification_gives_up_after_the_ladder(monkeypatch):
    flushes.clear()
    waits: list[float] = []
    trace_api = _client_with_traces(monkeypatch, set())

    record = writeback.verify_ingestion("trace-123", sleep=waits.append)

    assert record["ingested"] is False
    assert len(trace_api.asked) == len(writeback._INGESTION_RETRY_DELAYS)
    assert waits == [2.0, 5.0]


def test_a_score_names_its_trace_and_nothing_else(monkeypatch):
    """Langfuse 400s a score carrying both a trace and a dataset run.

    The SDK reports that rejection asynchronously on its own logger, so passing
    both wrote nothing while every counter said it had worked.
    """
    fake = FakeLangfuseClient()
    _enable_fake_langfuse(monkeypatch, fake)

    writeback.write_scores(
        "trace-123", {"seam1_routing": {"Tool Correctness": {"score": 1.0}}}
    )

    assert fake.scores[0]["trace_id"] == "trace-123"
    assert "dataset_run_id" not in fake.scores[0]


def test_counting_scores_reports_what_langfuse_kept(monkeypatch):
    class Scores:
        def get_many(self, trace_id: str):
            assert trace_id == "trace-123"
            return SimpleNamespace(data=[object(), object()])

    fake = SimpleNamespace(api=SimpleNamespace(scores=Scores()))
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: object())
    monkeypatch.setattr(writeback, "get_langfuse_client", lambda: fake)

    assert writeback.count_trace_scores("trace-123") == 2


def test_counting_scores_without_tracing_is_not_a_count(monkeypatch):
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: None)

    assert writeback.count_trace_scores("trace-123") is None
    assert writeback.count_trace_scores(None) is None


def _artifact(*scenarios) -> dict:
    """Build a capture artifact from (scenario_id, dataset_run_id, [trace ids])."""
    return {
        "scenarios": {
            scenario_id: {
                "status": "COMPLETE",
                "repeats": [
                    {
                        "repeat": 1,
                        "status": "COMPLETE",
                        "dataset_run_id": dataset_run_id,
                        "turns": [
                            {"turn": index + 1, "seams": {"trace_id": trace_id}}
                            for index, trace_id in enumerate(trace_ids)
                        ],
                    }
                ],
            }
            for scenario_id, dataset_run_id, trace_ids in scenarios
        }
    }


def test_the_sampled_trace_is_the_newest_one_not_the_first():
    """A resume exports through a client this process built, not the previous one.

    Sampling the first id would verify the interrupted session's trace and call a
    capture ingested when everything it just exported went nowhere.
    """
    artifact = _artifact(
        ("COUNT-1", "run-session-1", ["trace-old"]),
        ("HLP-LIST-1", "run-session-2", ["trace-mid", "trace-new"]),
    )

    assert writeback.sample_verification_target(artifact) == (
        "trace-new",
        "run-session-2",
    )


def test_sampling_skips_turns_that_recorded_no_trace():
    artifact = _artifact(("COUNT-1", "run-1", ["trace-1"]))
    artifact["scenarios"]["COUNT-1"]["repeats"][0]["turns"].append(
        {"turn": 2, "seams": {}}
    )

    assert writeback.sample_verification_target(artifact) == ("trace-1", "run-1")


def test_sampling_an_artifact_with_no_traces_is_no_target():
    assert writeback.sample_verification_target({"scenarios": {}}) == (None, None)
    assert writeback.sample_verification_target(
        _artifact(("COUNT-1", None, []))
    ) == (None, None)
