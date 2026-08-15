from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import viewer
from evals.viewer import build_viewer_html, flatten_turns


def _manifest() -> dict:
    return {
        "run_id": "run-123",
        "git_sha": "abc1234",
        "baseline_eligible": True,
        "providers": {"react": "deepseek", "sql_generation": "deepseek"},
        "models": {"react": "deepseek-chat", "sql_generation": "deepseek-chat"},
        "sampling": {
            "react": {"temperature": 0.2, "max_tokens": 900, "reasoning_effort": None, "thinking": "off"},
            "sql_generation": {"temperature": 0, "max_tokens": 400, "reasoning_effort": None, "thinking": "off"},
        },
    }


def _grade(status: str = "FAIL") -> dict:
    return {
        "run_id": "run-123",
        "scenarios": {
            "HLP-COUNT-1": [
                {
                    "repeat": 1,
                    "turn": 1,
                    "scenario_id": "HLP-COUNT-1",
                    "status": status,
                    "tier": "structural",
                    "checks": [
                        {"name": "required_tool_called", "passed": True, "detail": "required ('query_clean_jobs',)", "tier": "structural"},
                        {"name": "execution_accuracy", "passed": None, "detail": "T0025.5 result is absent", "tier": "structural"},
                        {"name": "required_substance_1", "passed": False, "detail": "none of ('per year',) present", "tier": "textual"},
                    ],
                },
                # A scenario-level verdict carries no turn number and joins to nothing.
                {"scenario_id": "HLP-COUNT-1", "status": "UNRUN", "tier": "structural", "checks": []},
            ]
        },
        "summary": {"counts": {status: 1}},
    }


def _run() -> dict:
    return {
        "manifest": {"run_id": "run-123"},
        "status": "COMPLETE",
        "scenarios": {
            "HLP-COUNT-1": {
                "repeats": [
                    {
                        "repeat": 1,
                        "turns": [
                            {
                                "turn": 1,
                                "status": "COMPLETE",
                                "seams": {
                                    "question": "How many jobs?",
                                    "tools_called": ["query_clean_jobs"],
                                    "sql_text": "SELECT COUNT(*) FROM clean_jobs",
                                    "tool_output": "Found 1 result(s) with columns: count.\n- count=2",
                                    "answer": "There are 2 jobs.",
                                    "trace_id": "trace-1",
                                },
                            }
                        ],
                    }
                ]
            }
        },
    }


def test_flatten_turns_preserves_three_seams() -> None:
    turns = flatten_turns(_run(), [{"id": "HLP-COUNT-1", "name": "Count jobs"}])

    assert turns[0]["scenario_name"] == "Count jobs"
    assert turns[0]["routing"] == "query_clean_jobs"
    assert turns[0]["sql"] == "SELECT COUNT(*) FROM clean_jobs"
    assert turns[0]["rows"] == {
        "kind": "table",
        "count": 1,
        "headers": ["count"],
        "rows": [["2"]],
        "note": "Found 1 result(s) with columns: count.",
    }
    assert turns[0]["answer"] == "There are 2 jobs."


def test_rows_parses_the_tools_real_prose_output() -> None:
    """The tool returns prose, not a Python literal; the table model must read it."""
    output = (
        "Found 2 result(s) with columns: id, title, company.\n"
        "- id=1, title=AI Engineer, company=Acme\n"
        "- id=2, title=Data Analyst, company=Beta"
    )

    assert viewer._rows(output) == {
        "kind": "table",
        "count": 2,
        "headers": ["id", "title", "company"],
        "rows": [["1", "AI Engineer", "Acme"], ["2", "Data Analyst", "Beta"]],
        "note": "Found 2 result(s) with columns: id, title, company.",
    }


def test_rows_splits_values_containing_commas_and_equals() -> None:
    """Free-text columns carry the row separators themselves, so anchor on column names."""
    output = (
        "Found 1 result(s) with columns: title, description.\n"
        "- title=ML Engineer, Senior, description=Owns a=b pipelines, and reporting"
    )

    assert viewer._rows(output)["rows"] == [
        ["ML Engineer, Senior", "Owns a=b pipelines, and reporting"]
    ]


def test_rows_keeps_truncation_caveat_as_a_note() -> None:
    """The truncation caveat is the evidence for judging seam 3's honesty."""
    output = (
        "Showing the first 1 results - there are more matches. "
        "Narrow your search to see the rest. Columns: id.\n"
        "- id=7"
    )
    rows = viewer._rows(output)

    assert rows["headers"] == ["id"]
    assert rows["rows"] == [["7"]]
    assert "more matches" in rows["note"]


def test_rows_falls_back_to_text_for_non_table_tool_output() -> None:
    message = "I couldn't retrieve the requested data due to a database error. Please try again later."

    assert viewer._rows(message) == {"kind": "text", "text": message}


def test_viewer_is_standalone_and_persists_notes() -> None:
    document = build_viewer_html(_run(), [{"id": "HLP-COUNT-1", "name": "Count jobs"}])

    assert 'id="run-data"' in document
    assert "query_clean_jobs" in document
    assert "Generated SQL" in document
    assert "Rows returned" in document
    assert "localStorage" in document
    assert "earliest wrong seam only" in document
    assert "navigation still works" in document
    assert "rowsBlock" in document
    assert "http://" not in document


def test_viewer_escapes_embedded_script_boundary() -> None:
    run = _run()
    run["scenarios"]["HLP-COUNT-1"]["repeats"][0]["turns"][0]["seams"]["answer"] = "</script><script>alert(1)</script>"

    document = build_viewer_html(run)

    assert "</script><script>alert(1)</script>" not in document
    assert "\\u003c/script>" in document


def test_grade_joins_per_turn_and_places_checks_beside_their_seam() -> None:
    turns = flatten_turns(_run(), None, _grade())

    turn = turns[0]
    assert turn["grade_status"] == "FAIL"
    assert turn["grade_tier"] == "structural"
    # The passing check is not drawn; the two that did not pass are, and they are
    # distinguished because an unavailable judgement is what makes a turn INFRA.
    assert [(check["name"], check["seam"], check["outcome"]) for check in turn["checks"]] == [
        ("execution_accuracy", "sql", "UNAVAILABLE"),
        ("required_substance_1", "answer", "FAILED"),
    ]
    assert turn["checks"][1]["detail"] == "none of ('per year',) present"


def test_ungraded_turns_are_labelled_rather_than_assumed_to_pass() -> None:
    turn = flatten_turns(_run())[0]

    assert turn["grade_status"] == "UNGRADED"
    assert turn["checks"] == []
    # Capture status and grade status are separate fields and never collide.
    assert turn["status"] == "COMPLETE"


def test_scenario_level_verdicts_join_to_no_captured_turn() -> None:
    index = viewer.index_grades(_grade())

    assert list(index) == ["HLP-COUNT-1/1/1"]


def test_run_header_names_the_provider_and_sampling_per_profile() -> None:
    header = viewer.run_header(_manifest())

    assert header["headers"] == ["Profile", "Provider", "Model", "Temperature", "Max tokens", "Reasoning effort", "Thinking"]
    assert header["rows"][0] == ["react", "deepseek", "deepseek-chat", "0.2", "900", "not recorded", "off"]
    assert header["facts"] == [["Git SHA", "abc1234"], ["Baseline eligible", "True"]]


def test_run_header_survives_a_manifest_without_a_provider_block() -> None:
    header = viewer.run_header({"run_id": "sanitized"})

    assert header["rows"] == []
    assert header["facts"] == [["Git SHA", "not recorded"], ["Baseline eligible", "not recorded"]]


def test_telemetry_becomes_labelled_fields_not_one_blob() -> None:
    run = _run()
    run["scenarios"]["HLP-COUNT-1"]["repeats"][0]["turns"][0]["telemetry"] = {
        "latency_ms": 1500,
        "provider_token_usage": {
            "calls": [
                {"input_tokens": 800, "output_tokens": 30, "total_tokens": 830, "finish_reason": "tool_calls"},
                {"input_tokens": 900, "output_tokens": 40, "total_tokens": 940, "finish_reason": "stop"},
            ],
            "aggregate": {"input_tokens": 1700, "output_tokens": 70, "total_tokens": 1770},
        },
        "finish_reasons": ["tool_calls", "stop"],
    }

    telemetry = flatten_turns(run)[0]["telemetry"]

    assert telemetry["latency_ms"] == "1500"
    assert telemetry["total_tokens"] == "1770"
    assert telemetry["finish_reasons"] == "tool_calls, stop"
    assert telemetry["calls"][1] == ["2", "900", "40", "940", "stop"]


def test_telemetry_absent_from_the_record_is_reported_as_absent() -> None:
    assert flatten_turns(_run())[0]["telemetry"] == {"available": False}


def test_viewer_renders_the_verdict_the_run_and_a_grade_filter() -> None:
    document = build_viewer_html(_run(), None, _grade())

    assert "deepseek" not in document  # the run above carries the bare manifest
    assert "grade-filter" in document
    # The detail is what makes a verdict explicable: it names the substring the rule wanted.
    assert "none of ('per year',) present" in document
    assert "What produced this capture" in document
    assert "Finish reasons" in document
    assert "http://" not in document


def test_viewer_header_names_the_arm_that_produced_the_capture() -> None:
    run = _run()
    run["manifest"] = _manifest()

    document = build_viewer_html(run, None, _grade())

    assert "deepseek-chat" in document
    assert "abc1234" in document


def test_grade_cli_reports_a_missing_file_with_the_command_that_makes_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = tmp_path / "run.json"
    run.write_text(json.dumps(_run()), encoding="utf-8")

    with pytest.raises(SystemExit) as raised:
        viewer.main([str(run), "--grade", str(tmp_path / "missing-grade.json")])

    assert raised.value.code == 2
    assert "evals.grader" in capsys.readouterr().err


def test_grade_cli_rejects_a_file_that_is_not_a_grader_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = tmp_path / "run.json"
    run.write_text(json.dumps(_run()), encoding="utf-8")
    grade = tmp_path / "grade.json"
    grade.write_text(json.dumps({"summary": {}}), encoding="utf-8")

    with pytest.raises(SystemExit) as raised:
        viewer.main([str(run), "--grade", str(grade)])

    assert raised.value.code == 2
    assert "not a grader report" in capsys.readouterr().err


def test_sample_run_provides_two_turns_without_quota() -> None:
    turns = flatten_turns(viewer.sample_run())

    assert len(turns) == 2
    assert turns[1]["rows"]["rows"] == [["Acme"], ["Beta"]]


def test_missing_run_has_actionable_cli_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(SystemExit) as raised:
        viewer.main([str(missing)])

    assert raised.value.code == 2
    message = capsys.readouterr().err
    assert "run artifact not found" in message
    assert "evals.driver" in message


def test_sample_cli_writes_html(tmp_path: Path) -> None:
    output = tmp_path / "sample.html"

    viewer.main(["--sample", "--output", str(output)])

    assert output.exists()
    assert "Sample trace viewer run" in output.read_text(encoding="utf-8")
