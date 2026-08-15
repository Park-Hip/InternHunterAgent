from __future__ import annotations

from pathlib import Path

import pytest

from evals import viewer
from evals.viewer import build_viewer_html, flatten_turns


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
