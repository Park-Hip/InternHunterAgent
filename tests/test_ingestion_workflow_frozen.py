from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ingestion.yml"


def test_ingestion_workflow_has_no_scheduled_trigger() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for line in text.splitlines():
        assert line.strip() != "schedule:", "the schedule trigger must be removed"
    assert "- cron:" not in text


def test_ingestion_workflow_keeps_manual_dispatch() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch: {}" in text