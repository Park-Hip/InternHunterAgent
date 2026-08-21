"""No-network unit tests for `evals/writeback.py` — a fake Langfuse client
stands in for the real SDK so these run without creds or a live server."""

from __future__ import annotations

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
