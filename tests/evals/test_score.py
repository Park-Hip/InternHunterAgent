"""No-network unit tests for `evals/score.py`.

The judge and Langfuse are both stubbed: these assert the shape of the offline
pass - what it scores, what it skips, what it persists, and what it posts - not
what a judge would say about an answer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import score as score_module
from evals.harness import SCORER_VERSION, SeamRun


def _artifact(**overrides) -> dict:
    repeat = {
        "repeat": 1,
        "status": "COMPLETE",
        "dataset_run_id": "dataset-run-1",
        "turns": [
            {
                "turn": 1,
                "status": "COMPLETE",
                "seams": {
                    "question": "bao nhiêu việc?",
                    "answer": "Có 12 vị trí.",
                    "tools_called": ["query_clean_jobs"],
                    "tool_output": "count=12",
                    "sql_text": "SELECT COUNT(*) FROM clean_jobs",
                    "trace_id": "trace-1",
                },
                "telemetry": {"total_tokens": 400},
            }
        ],
    }
    repeat.update(overrides)
    return {
        "manifest": {"run_id": "run-1", "langfuse_ingestion": {"trace_id": "trace-1"}},
        "status": "COMPLETE",
        "scenarios": {"COUNT-1": {"status": "COMPLETE", "repeats": [repeat]}},
    }


def _write(tmp_path: Path, artifact: dict) -> Path:
    path = tmp_path / "run.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def _case() -> dict:
    return {"id": "COUNT-1", "type": "single", "expected": "a count"}


@pytest.fixture(autouse=True)
def no_live_langfuse(monkeypatch: pytest.MonkeyPatch):
    """Keep the scoring pass off the network by default, for the same reason."""
    monkeypatch.setattr(score_module, "write_scores", lambda *a, **k: 0)
    monkeypatch.setattr(score_module, "count_trace_scores", lambda *a, **k: None)
    monkeypatch.setattr(
        score_module,
        "verify_ingestion",
        lambda trace_id, **kwargs: {
            "trace_id": trace_id,
            "ingested": None,
            "detail": "stubbed in tests",
        },
    )


@pytest.fixture
def stub_judge(monkeypatch: pytest.MonkeyPatch) -> list[tuple[dict, SeamRun]]:
    """Replace the judge with a recorder, so no test spends a judge call."""
    calls: list[tuple[dict, SeamRun]] = []

    def fake_score_seams(case: dict, final_run: SeamRun) -> dict:
        calls.append((case, final_run))
        return {"seam1_routing": {"Tool Correctness": {"score": 1.0, "reason": "ok"}}}

    monkeypatch.setattr(score_module.harness, "score_seams", fake_score_seams)
    return calls


@pytest.fixture
def posted(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    writes: list[dict] = []

    def fake_write_scores(trace_id, results):
        writes.append({"trace_id": trace_id, "results": results})
        return 1

    monkeypatch.setattr(score_module, "write_scores", fake_write_scores)
    monkeypatch.setattr(
        score_module,
        "verify_ingestion",
        lambda trace_id, *, dataset_run_id=None: {
            "trace_id": trace_id,
            "dataset_run_id": dataset_run_id,
            "ingested": True,
            "detail": "resolved in Langfuse",
        },
    )
    return writes


def test_scores_a_completed_repeat_from_what_the_capture_recorded(
    tmp_path: Path, stub_judge, posted
) -> None:
    path = _write(tmp_path, _artifact())

    summary = score_module.score_artifact(path, scenarios=[_case()])

    assert summary["scored"] == 1
    assert summary["skipped"] == 0

    case, final_run = stub_judge[0]
    assert case["id"] == "COUNT-1"
    assert final_run.answer == "Có 12 vị trí."
    assert final_run.sql_text == "SELECT COUNT(*) FROM clean_jobs"
    assert final_run.trace_id == "trace-1"

    persisted = json.loads(path.read_text(encoding="utf-8"))
    repeat = persisted["scenarios"]["COUNT-1"]["repeats"][0]
    assert repeat["scores"]["seam1_routing"]["Tool Correctness"]["score"] == 1.0
    assert repeat["scorer_version"] == SCORER_VERSION
    assert repeat["scored_at"]


def test_scores_reach_langfuse_on_the_trace_the_capture_recorded(
    tmp_path: Path, stub_judge, posted
) -> None:
    """R3.7. A score names its trace and nothing else.

    Langfuse rejects a score carrying both a trace and a dataset run. The dataset
    run still gets these scores, because its run item links this trace.
    """
    path = _write(tmp_path, _artifact())

    score_module.score_artifact(path, scenarios=[_case()])

    assert len(posted) == 1
    assert posted[0]["trace_id"] == "trace-1"


def test_a_second_pass_over_a_scored_artifact_is_a_no_op(
    tmp_path: Path, stub_judge, posted
) -> None:
    """R3.5. Re-running must be free and must not be an error."""
    path = _write(tmp_path, _artifact())

    score_module.score_artifact(path, scenarios=[_case()])
    summary = score_module.score_artifact(path, scenarios=[_case()])

    assert summary["scored"] == 0
    assert summary["skipped"] == 1
    assert len(stub_judge) == 1
    assert len(posted) == 1


def test_an_interrupted_pass_keeps_the_repeats_it_already_scored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, posted
) -> None:
    """R3.5. An interrupt at judge call 300 of 365 does not discard the 300."""
    artifact = _artifact()
    artifact["scenarios"]["HLP-1"] = {
        "status": "COMPLETE",
        "repeats": [
            json.loads(json.dumps(artifact["scenarios"]["COUNT-1"]["repeats"][0]))
        ],
    }
    path = _write(tmp_path, artifact)
    cases = [_case(), {"id": "HLP-1", "type": "single", "expected": "help"}]

    seen: list[str] = []

    def judge_then_die(case: dict, final_run: SeamRun) -> dict:
        if seen:
            raise KeyboardInterrupt("operator stopped the pass")
        seen.append(case["id"])
        return {"seam1_routing": {"Tool Correctness": {"score": 1.0, "reason": "ok"}}}

    monkeypatch.setattr(score_module.harness, "score_seams", judge_then_die)

    with pytest.raises(KeyboardInterrupt):
        score_module.score_artifact(path, scenarios=cases)

    persisted = json.loads(path.read_text(encoding="utf-8"))
    scored = [
        scenario_id
        for scenario_id, record in persisted["scenarios"].items()
        if record["repeats"][0].get("scores")
    ]
    assert scored == seen

    monkeypatch.setattr(
        score_module.harness,
        "score_seams",
        lambda case, run: {"seam1_routing": {"Tool Correctness": {"score": 1.0}}},
    )
    summary = score_module.score_artifact(path, scenarios=cases)

    assert summary["scored"] == 1
    assert summary["skipped"] == 1


def test_rescoring_measures_and_posts_again(tmp_path: Path, stub_judge, posted) -> None:
    """R3.7. A re-grade must be able to replace the scores already in Langfuse."""
    path = _write(tmp_path, _artifact())

    score_module.score_artifact(path, scenarios=[_case()])
    summary = score_module.score_artifact(path, scenarios=[_case()], rescore=True)

    assert summary["scored"] == 1
    assert len(stub_judge) == 2
    assert len(posted) == 2


def test_an_infra_repeat_is_not_scored(tmp_path: Path, stub_judge, posted) -> None:
    path = _write(tmp_path, _artifact(status="INFRA", turns=[]))

    summary = score_module.score_artifact(path, scenarios=[_case()])

    assert summary["scored"] == 0
    assert summary["unscorable"] == 1
    assert stub_judge == []


def test_a_scenario_missing_from_the_registry_is_recorded_not_skipped(
    tmp_path: Path, stub_judge, posted
) -> None:
    path = _write(tmp_path, _artifact())

    summary = score_module.score_artifact(path, scenarios=[])

    assert summary["unscorable"] == 1
    persisted = json.loads(path.read_text(encoding="utf-8"))
    repeat = persisted["scenarios"]["COUNT-1"]["repeats"][0]
    assert "registry" in repeat["scoring_error"]


def test_the_pass_records_whether_the_traces_it_scored_exist(
    tmp_path: Path, stub_judge, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3.9. Scores posted onto traces that were never ingested reach nobody."""
    monkeypatch.setattr(score_module, "write_scores", lambda *a, **k: 0)
    monkeypatch.setattr(
        score_module,
        "verify_ingestion",
        lambda trace_id, *, dataset_run_id=None: {
            "trace_id": trace_id,
            "ingested": False,
            "detail": "Langfuse has no trace with this id",
        },
    )
    path = _write(tmp_path, _artifact())

    summary = score_module.score_artifact(path, scenarios=[_case()])

    assert summary["traces_ingested"] is False
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["manifest"]["langfuse_ingestion_at_scoring"]["ingested"] is False


def test_a_repeat_whose_metrics_all_failed_is_judged_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, posted
) -> None:
    """A 429 mid-pass must not cement a null repeat.

    `harness.score` isolates a failing metric as `{"score": None, "error": ...}`,
    which is truthy. If that counted as scored, one throttled call would null the
    repeat for every later pass and the only way back would be re-spending the
    whole registry with --rescore.
    """
    attempts: list[str] = []

    def judge(case: dict, final_run: SeamRun) -> dict:
        attempts.append(case["id"])
        if len(attempts) == 1:
            return {
                "seam1_routing": {"Tool Correctness": {"score": None, "error": "429"}}
            }
        return {"seam1_routing": {"Tool Correctness": {"score": 1.0, "reason": "ok"}}}

    monkeypatch.setattr(score_module.harness, "score_seams", judge)
    path = _write(tmp_path, _artifact())

    first = score_module.score_artifact(path, scenarios=[_case()])
    second = score_module.score_artifact(path, scenarios=[_case()])

    assert first["scored"] == 1
    assert second["scored"] == 1
    assert second["skipped"] == 0
    assert attempts == ["COUNT-1", "COUNT-1"]

    persisted = json.loads(path.read_text(encoding="utf-8"))
    repeat = persisted["scenarios"]["COUNT-1"]["repeats"][0]
    assert repeat["scores"]["seam1_routing"]["Tool Correctness"]["score"] == 1.0


def test_a_post_that_never_landed_is_retried_without_re_judging(
    tmp_path: Path, stub_judge, posted
) -> None:
    """R3.7. Scores are persisted before the writeback, so an interrupt between the
    two leaves a judged repeat whose scores never reached Langfuse. Re-posting is
    cheap and idempotent; re-judging is 46 minutes of throttled calls."""
    artifact = _artifact()
    repeat = artifact["scenarios"]["COUNT-1"]["repeats"][0]
    repeat["scores"] = {"seam1_routing": {"Tool Correctness": {"score": 1.0}}}
    repeat["scorer_version"] = SCORER_VERSION
    path = _write(tmp_path, artifact)

    summary = score_module.score_artifact(path, scenarios=[_case()])

    assert summary["scored"] == 0
    assert summary["reposted"] == 1
    assert stub_judge == []
    assert len(posted) == 1
    assert posted[0]["trace_id"] == "trace-1"


def test_scoring_verifies_a_capture_taken_before_the_manifest_key_existed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stub_judge
) -> None:
    """Every artifact already on disk predates `manifest.langfuse_ingestion`.

    Reading only that key reported `traces_ingested: None` for exactly the runs an
    operator re-scores, even though their turns carry trace ids all along.
    """
    artifact = _artifact()
    del artifact["manifest"]["langfuse_ingestion"]
    path = _write(tmp_path, artifact)

    asked: list[tuple] = []

    def fake_verify(trace_id, *, dataset_run_id=None):
        asked.append((trace_id, dataset_run_id))
        return {"trace_id": trace_id, "ingested": True, "detail": "resolved"}

    counted: list[str | None] = []
    monkeypatch.setattr(score_module, "verify_ingestion", fake_verify)
    def fake_count(trace_id):
        counted.append(trace_id)
        return 3

    monkeypatch.setattr(score_module, "count_trace_scores", fake_count)

    summary = score_module.score_artifact(path, scenarios=[_case()])

    assert asked == [("trace-1", "dataset-run-1")]
    assert counted == ["trace-1"]
    assert summary["traces_ingested"] is True
    assert summary["scores_on_sampled_trace"] == 3
