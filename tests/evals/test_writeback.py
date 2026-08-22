"""No-network unit tests for `evals/writeback.py` — a fake Langfuse client
stands in for the real SDK so these run without creds or a live server."""

from __future__ import annotations

from types import SimpleNamespace

from langfuse.api import NotFoundError

from evals import writeback


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
    def __init__(self, known: set[str]) -> None:
        self.known = known
        self.asked: list[str] = []

    def get(self, trace_id: str):
        self.asked.append(trace_id)
        if trace_id not in self.known:
            raise NotFoundError(f"no trace {trace_id}")
        return {"id": trace_id}


def _client_with_traces(monkeypatch, known: set[str]) -> FakeTraceAPI:
    trace_api = FakeTraceAPI(known)
    fake = SimpleNamespace(api=SimpleNamespace(trace=trace_api))
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: object())
    monkeypatch.setattr(writeback, "get_langfuse_client", lambda: fake)
    return trace_api


def test_an_ingested_trace_verifies(monkeypatch):
    trace_api = _client_with_traces(monkeypatch, {"trace-123"})

    record = writeback.verify_ingestion("trace-123", dataset_run_id="run-9")

    assert record["ingested"] is True
    assert record["dataset_run_id"] == "run-9"
    assert trace_api.asked == ["trace-123"]


def test_a_trace_id_that_names_nothing_is_not_ingested(monkeypatch):
    """The 2026-08-21 probe recorded five ids exactly like this one."""
    _client_with_traces(monkeypatch, set())

    record = writeback.verify_ingestion("trace-123")

    assert record["ingested"] is False
    assert "no trace" in record["detail"]


def test_an_unreachable_langfuse_is_not_a_verdict(monkeypatch):
    """None and False are different findings: not asked, versus asked and absent."""

    class Exploding:
        def get(self, trace_id: str):
            raise RuntimeError("connection refused")

    fake = SimpleNamespace(api=SimpleNamespace(trace=Exploding()))
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: object())
    monkeypatch.setattr(writeback, "get_langfuse_client", lambda: fake)

    record = writeback.verify_ingestion("trace-123")

    assert record["ingested"] is None
    assert "connection refused" in record["detail"]


def test_verification_without_tracing_is_not_a_verdict(monkeypatch):
    monkeypatch.setattr(writeback, "get_langfuse_handler", lambda: None)

    assert writeback.verify_ingestion("trace-123")["ingested"] is None
    assert writeback.verify_ingestion(None)["ingested"] is None
