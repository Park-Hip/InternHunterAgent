"""Per-question regression diff and absolute floors (#762).

The tests build score rows directly for the pure comparison and floor logic.
Two committed Layer 1 runs exercise the file contract and the CLI; no model or
database is called.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest
import yaml

from evals import baseline_dataset, baseline_sql, milestone, regression
from evals.regression import RowKey


def _row(
    scenario_id: str,
    metric: str = "execution_accuracy",
    score: float | None = 1.0,
    *,
    turn: int = 1,
    repeat: int = 1,
    reason: str | None = None,
) -> dict:
    return {
        "scenario_id": scenario_id,
        "turn": turn,
        "repeat": repeat,
        "metric": metric,
        "score": score,
        "reason": reason,
        "details": {},
    }


def _put(rows: dict[RowKey, dict], row: dict) -> None:
    key = RowKey(
        scenario_id=row["scenario_id"],
        turn=row["turn"],
        metric=row["metric"],
        repeat=row["repeat"],
    )
    rows[key] = row


def _run(*rows: dict) -> dict[RowKey, dict]:
    keyed: dict[RowKey, dict] = {}
    for row in rows:
        _put(keyed, row)
    return keyed


def _data_points(
    metric: str, total: int, passed: int, *, prefix: str, split: str, splits: dict[str, str]
) -> dict[RowKey, dict]:
    rows: dict[RowKey, dict] = {}
    for index in range(total):
        scenario_id = f"{prefix}{index:02d}"
        splits[scenario_id] = split
        score = 1.0 if index < passed else 0.0
        _put(rows, _row(scenario_id, metric, score, reason=None if score else "FAIL"))
    return rows


def _floor_fixture(
    *,
    held_out_total: int = 30,
    held_out_passed: int = 30,
    faithfulness_failed: int = 0,
    communicated_failed: int = 0,
    safety_failed: int = 0,
) -> tuple[dict[RowKey, dict], dict[str, str]]:
    splits: dict[str, str] = {}
    rows = _data_points(
        "execution_accuracy",
        held_out_total,
        held_out_passed,
        prefix="H",
        split="held-out",
        splits=splits,
    )
    rows.update(
        _data_points(
            "answer_faithfulness",
            100,
            100 - faithfulness_failed,
            prefix="F",
            split="dev",
            splits=splits,
        )
    )
    rows.update(
        _data_points(
            "result_communicated",
            100,
            100 - communicated_failed,
            prefix="C",
            split="dev",
            splits=splits,
        )
    )
    rows.update(
        _data_points(
            "safety_refusal",
            4,
            4 - safety_failed,
            prefix="S",
            split="safety",
            splits=splits,
        )
    )
    return rows, splits


def _generations() -> dict:
    question = baseline_sql.scored_questions()[0]
    return {
        "created_at": "2026-10-26T00:00:00+00:00",
        "model": "deepseek/deepseek-flash",
        "prompt_versions": {"system": "system-hash", "sql_generation": "sql-hash"},
        "records": [
            {
                "id": question["id"],
                "question": question["turns"][0],
                "sql": question["reference_sql"][0],
                "error": None,
            }
        ],
    }


def _agent_rows(*, held_out_passed: int = 30) -> dict[RowKey, dict]:
    rows: dict[RowKey, dict] = {}
    for index in range(1, 31):
        scenario_id = f"H{index:02d}"
        score = 1.0 if index <= held_out_passed else 0.0
        _put(
            rows,
            _row(
                scenario_id,
                "execution_accuracy",
                score,
                reason=None if score else "FAIL",
            ),
        )
    for case in baseline_dataset.load_cases():
        if case["split"] == "dev":
            _put(rows, _row(case["id"], "answer_faithfulness", 1.0))
            _put(rows, _row(case["id"], "result_communicated", 1.0))
        elif case["split"] == "safety":
            _put(rows, _row(case["id"], "safety_refusal", 1.0))
    return rows


def _write_agent_run(
    root: Path, label: str, run_date: date, rows: dict[RowKey, dict]
) -> Path:
    run_dir = root / f"{run_date.isoformat()}-{label}"
    run_dir.mkdir()
    captures = {"schema_version": 1, "runner": "agent", "records": []}
    by_metric: dict[str, list[dict]] = {}
    for row in rows.values():
        by_metric.setdefault(row["metric"], []).append(row)
    scores = {
        "schema_version": 1,
        "metrics": [name for name in milestone.AGENT_METRICS if name in by_metric],
        "by_metric": by_metric,
    }
    manifest = {
        "schema_version": milestone.SCHEMA_VERSION,
        "run_id": run_dir.name,
        "label": label,
        "runner": milestone.RUNNER_AGENT,
        "dataset": milestone.baseline_identity(),
        "snapshot": milestone.snapshot_manifest_identity(),
        "metrics": scores["metrics"],
        "evidence": {
            "captures": milestone.CAPTURES_NAME,
            "scores": milestone.SCORES_NAME,
            "captures_sha256": milestone.payload_sha256(captures),
            "scores_sha256": milestone.payload_sha256(scores),
        },
        "status": "scored",
    }
    (run_dir / milestone.CAPTURES_NAME).write_text(
        json.dumps(captures), encoding="utf-8"
    )
    (run_dir / milestone.SCORES_NAME).write_text(json.dumps(scores), encoding="utf-8")
    (run_dir / milestone.MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return run_dir


def _write_scored_run(
    root: Path, label: str, run_date: date, *, score: float
) -> Path:
    run_dir = milestone.write_baseline_run(
        _generations(), label, root=root, run_date=run_date
    )
    question = baseline_sql.scored_questions()[0]
    row = {
        "scenario_id": question["id"],
        "turn": 1,
        "metric": "sql_accuracy",
        "score": score,
        "reason": None if score == 1.0 else "FAIL",
        "details": {},
    }
    milestone.write_scores(
        run_dir, metrics=["sql_accuracy"], by_metric={"sql_accuracy": [row]}
    )
    return run_dir


def test_a_pass_that_becomes_a_fail_is_a_regression() -> None:
    before = _run(_row("H01"))
    after = _run(_row("H01", score=0.0, reason="wrong_ids"))

    question = regression.diff_rows(before, after, {"H01": "held-out"})[0]

    assert question.verdict == "REGRESSED"
    assert question.blocks
    assert question.before == "PASS"
    assert question.after == "FAIL"
    assert question.transitions[0].after_reason == "wrong_ids"


def test_a_fail_that_becomes_a_pass_is_an_improvement() -> None:
    before = _run(_row("H01", score=0.0, reason="wrong_ids"))
    after = _run(_row("H01"))

    question = regression.diff_rows(before, after, {"H01": "held-out"})[0]

    assert question.verdict == "IMPROVED"
    assert not question.blocks


def test_losing_one_turn_blocks_even_when_another_turn_still_passes() -> None:
    before = _run(
        _row("001", metric="answer_faithfulness", turn=1),
        _row("001", metric="answer_faithfulness", turn=2),
    )
    after = _run(_row("001", metric="answer_faithfulness", turn=1))

    question = regression.diff_rows(before, after, {"001": "dev"})[0]

    assert question.verdict == "REGRESSED"
    assert question.before == "PASS"
    assert question.after == "PASS"
    assert question.blocks


def test_a_lost_check_that_was_not_applicable_is_not_a_regression_but_a_lost_pass_is() -> None:
    before = _run(
        _row("H01", metric="execution_accuracy", score=1.0, turn=1),
        _row("H01", metric="execution_accuracy", score=None, turn=2),
    )
    after = _run(_row("H01", metric="execution_accuracy", score=1.0, turn=1))

    question = regression.diff_rows(before, after, {"H01": "held-out"})[0]
    assert question.verdict == "UNCHANGED"
    assert not question.blocks

    before = _run(_row("H01", metric="execution_accuracy", score=1.0, turn=1))
    after = _run(_row("H01", metric="execution_accuracy", score=None, turn=1))
    assert regression.diff_rows(before, after, {"H01": "held-out"})[0].blocks


def test_a_failure_cannot_be_hidden_by_making_the_check_not_apply() -> None:
    before = _run(_row("H01", metric="answer_faithfulness", score=0.0, reason="ungrounded_answer"))
    after = _run(_row("H01", metric="answer_faithfulness", score=None))

    question = regression.diff_rows(before, after, {"H01": "held-out"})[0]

    assert question.verdict == "REGRESSED"
    assert question.blocks


def test_a_missing_question_blocks_and_a_new_question_does_not() -> None:
    before = _run(_row("H01"), _row("H02"))
    after = _run(_row("H01"), _row("H03", score=0.0, reason="new_failure"))

    questions = {q.scenario_id: q for q in regression.diff_rows(before, after, {})}

    assert questions["H02"].verdict == "MISSING"
    assert questions["H02"].blocks
    assert questions["H03"].verdict == "NEW"
    assert not questions["H03"].blocks


def test_a_missing_question_with_only_not_applicable_rows_is_reported_but_not_blocking() -> None:
    before = _run(_row("H01", score=None))
    after = _run()

    question = regression.diff_rows(before, after, {})[0]

    assert question.verdict == "MISSING"
    assert question.changed
    assert not question.blocks


def test_the_floor_bars_are_the_ones_the_behavior_document_states() -> None:
    assert [
        (floor.bar, floor.metric, floor.split, floor.minimum_percent)
        for floor in regression.FLOORS
    ] == [
        ("B2", "execution_accuracy", "held-out", 85),
        ("B3", "answer_faithfulness", None, 100),
        ("B4", "result_communicated", None, 100),
        ("safety", "safety_refusal", None, 100),
    ]


def test_b2_is_85_percent_of_held_out_not_of_every_split() -> None:
    rows, splits = _floor_fixture()
    results = regression.check_floors(
        rows, splits, runner=milestone.RUNNER_AGENT
    )
    assert [result.status for result in results] == ["MET", "MET", "MET", "MET"]

    rows, splits = _floor_fixture(held_out_passed=26)
    results = regression.check_floors(
        rows, splits, runner=milestone.RUNNER_AGENT
    )
    assert results[0].status == "MET"
    assert results[0].passed == 26
    assert results[0].scored == 30

    rows, splits = _floor_fixture(held_out_passed=25)
    results = regression.check_floors(
        rows, splits, runner=milestone.RUNNER_AGENT
    )
    assert results[0].status == "BELOW FLOOR"


def test_b3_b4_and_safety_must_each_be_perfect() -> None:
    rows, splits = _floor_fixture(
        faithfulness_failed=1, communicated_failed=1, safety_failed=1
    )
    results = regression.check_floors(
        rows, splits, runner=milestone.RUNNER_AGENT
    )

    assert [result.status for result in results] == [
        "MET",
        "BELOW FLOOR",
        "BELOW FLOOR",
        "BELOW FLOOR",
    ]


def test_a_floor_with_no_scored_rows_is_not_measured() -> None:
    rows, splits = _floor_fixture(held_out_total=0)

    results = regression.check_floors(
        rows, splits, runner=milestone.RUNNER_AGENT
    )

    assert results[0].status == "NOT MEASURED"
    assert results[0].rate is None


def test_a_layer_1_run_has_no_agent_floors() -> None:
    rows, splits = _floor_fixture()

    assert (
        regression.check_floors(
            rows, splits, runner=milestone.RUNNER_BASELINE_SQL
        )
        == []
    )


def test_two_runners_or_two_snapshots_are_not_comparable() -> None:
    baseline = regression.ScoredRun(
        "a", milestone.RUNNER_BASELINE_SQL, {}, {}, "digest", "snapshot"
    )
    other_runner = regression.ScoredRun(
        "b", milestone.RUNNER_AGENT, {}, {}, "digest", "snapshot"
    )
    other_snapshot = regression.ScoredRun(
        "c", milestone.RUNNER_BASELINE_SQL, {}, {}, "other", "snapshot"
    )

    with pytest.raises(regression.RegressionError, match="different runners"):
        regression.verify_comparable(baseline, other_runner)
    with pytest.raises(regression.RegressionError, match="different snapshot manifests"):
        regression.verify_comparable(baseline, other_snapshot)


def test_a_scored_run_loads_and_its_evidence_is_checked(tmp_path: Path) -> None:
    run_dir = _write_scored_run(
        tmp_path, "baseline-diff", date(2026, 10, 26), score=1.0
    )

    loaded = regression.load_run(run_dir)
    assert loaded.runner == milestone.RUNNER_BASELINE_SQL
    assert loaded.question_count == 1

    scores = json.loads((run_dir / milestone.SCORES_NAME).read_text(encoding="utf-8"))
    scores["by_metric"]["sql_accuracy"][0]["score"] = 0.0
    (run_dir / milestone.SCORES_NAME).write_text(json.dumps(scores), encoding="utf-8")
    with pytest.raises(milestone.MilestoneError, match="digest"):
        regression.load_run(run_dir)


def test_a_later_dataset_edit_does_not_make_a_run_undiffable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _write_scored_run(
        tmp_path, "baseline-dataset-edit", date(2026, 10, 26), score=1.0
    )

    def refuse(_manifest: dict) -> None:
        raise AssertionError("the diff must not re-verify the current dataset")

    monkeypatch.setattr(milestone, "verify_dataset", refuse)

    assert regression.load_run(run_dir).question_count == 1


def test_the_committed_run_is_a_valid_diff_source() -> None:
    committed = milestone.ROOT / "evals" / "runs" / "2026-10-19-baseline-v1"

    loaded = regression.load_run(committed)
    questions = regression.diff_rows(loaded.rows, loaded.rows, loaded.splits)

    assert questions
    assert all(not question.changed for question in questions)


def test_the_cli_blocks_a_regression_until_the_pr_explains_it(tmp_path: Path) -> None:
    from evals.__main__ import main

    question = baseline_sql.scored_questions()[0]["id"]
    baseline = _write_scored_run(
        tmp_path, "baseline-before", date(2026, 10, 26), score=1.0
    )
    candidate = _write_scored_run(
        tmp_path, "baseline-after", date(2026, 10, 27), score=0.0
    )

    assert main(["--diff", str(baseline), str(candidate)]) == 1
    assert (
        main(["--diff", str(baseline), str(candidate), "--explained", question]) == 0
    )


def test_the_cli_refuses_the_same_run_twice(tmp_path: Path) -> None:
    from evals.__main__ import main

    run_dir = _write_scored_run(
        tmp_path, "baseline-same", date(2026, 10, 26), score=1.0
    )

    assert main(["--diff", str(run_dir), str(run_dir)]) == 2


def test_the_cli_refuses_explained_without_a_diff() -> None:
    from evals.__main__ import main

    with pytest.raises(SystemExit):
        main(["--explained", "001"])


def test_an_agent_run_meeting_the_floors_passes(tmp_path: Path) -> None:
    baseline = _write_agent_run(
        tmp_path, "agent-before", date(2026, 10, 26), _agent_rows()
    )
    candidate = _write_agent_run(
        tmp_path, "agent-after", date(2026, 10, 27), _agent_rows()
    )

    report = regression.run_diff(baseline, candidate)

    assert report["counts"]["unchanged"] == report["counts"]["total"]
    assert report["blocking"] == []
    assert report["floor_breaches"] == []
    assert report["blocked"] is False


def test_an_agent_run_below_a_floor_is_blocked_without_a_diff(tmp_path: Path) -> None:
    baseline = _write_agent_run(
        tmp_path, "agent-before", date(2026, 10, 26), _agent_rows(held_out_passed=25)
    )
    candidate = _write_agent_run(
        tmp_path, "agent-after", date(2026, 10, 27), _agent_rows(held_out_passed=25)
    )

    report = regression.run_diff(baseline, candidate)

    assert report["blocking"] == []
    assert report["floor_breaches"] == ["execution_accuracy"]
    assert report["blocked"] is True
    assert report["floors"][0].status == "BELOW FLOOR"


def test_the_report_names_the_floor_breach(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = _write_agent_run(
        tmp_path, "agent-before", date(2026, 10, 26), _agent_rows(held_out_passed=25)
    )
    candidate = _write_agent_run(
        tmp_path, "agent-after", date(2026, 10, 27), _agent_rows(held_out_passed=25)
    )

    regression.print_report(regression.run_diff(baseline, candidate))
    output = capsys.readouterr().out

    assert "execution_accuracy" in output
    assert "BELOW FLOOR" in output
    assert "BLOCKED" in output


def test_a_dataset_change_is_reported_but_not_refused(tmp_path: Path) -> None:
    baseline = _write_agent_run(
        tmp_path, "agent-before", date(2026, 10, 26), _agent_rows()
    )
    candidate = _write_agent_run(
        tmp_path, "agent-after", date(2026, 10, 27), _agent_rows()
    )
    manifest_path = candidate / milestone.MANIFEST_NAME
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["dataset"]["files_sha256"] = "0" * 64
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    report = regression.run_diff(baseline, candidate)

    assert report["dataset_changed"] is True
    assert report["blocked"] is False

