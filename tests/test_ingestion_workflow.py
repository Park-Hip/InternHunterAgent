"""Guards on the armed posture of the nightly ingestion workflow.

The schedule was removed on 2026-09-18 under the frozen-data portfolio release
and re-armed on 2026-10-05 under #605, after two green `workflow_dispatch` runs
proved the path. These assertions encode the posture that re-arm established, so
a later edit that silently disarms the trigger, drops the manual escape hatch, or
lets the unattended job touch production schema fails here rather than on the
next 02:00 UTC window.

Parsed as text on purpose: PyYAML is not a declared dependency, and an
unattended job must not gain one through a test.
"""

from __future__ import annotations

from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ingestion.yml"
)
NIGHTLY_CRON = "- cron: '0 2 * * *'"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def workflow_body() -> str:
    """The workflow with comments and blank lines removed.

    The re-arm record above `on:` discusses `schedule:` and `alembic` in prose,
    so a naive substring search over the raw file passes on the comment that
    says the opposite of what the assertion claims. Only the lines GitHub
    actually executes can answer a question about the armed posture.
    """
    lines = (raw.strip() for raw in workflow_text().splitlines())
    return "\n".join(line for line in lines if line and not line.startswith("#"))


def test_ingestion_workflow_arms_the_nightly_schedule() -> None:
    body = workflow_body()

    assert "schedule:" in body, "the nightly schedule must stay armed"
    assert NIGHTLY_CRON in body, (
        "the schedule must stay the 02:00 UTC (09:00 ICT) nightly slot"
    )
    assert body.count("- cron:") == 1, "exactly one schedule entry, or a run is doubled"


def test_ingestion_workflow_keeps_manual_dispatch() -> None:
    assert "workflow_dispatch: {}" in workflow_body(), (
        "the armed schedule must not cost the manual escape hatch"
    )


def test_ingestion_workflow_never_migrates_production() -> None:
    assert "alembic" not in workflow_body(), (
        "an unattended job must never migrate a production database; a schema "
        "change is a deliberate maintainer-run `alembic upgrade head`"
    )


def test_ingestion_workflow_records_its_revocation_condition() -> None:
    assert "REVOCATION CONDITION" in workflow_text(), (
        "a trigger that fires unattended must say in the file what disarms it"
    )
