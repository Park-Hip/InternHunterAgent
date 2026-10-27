"""Committed milestone runs: lineage, evidence digests, and baseline re-scoring.

The tests never call a provider. A baseline run stubs the snapshot comparison,
so the tests exercise the artifact contract rather than a database.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import subprocess

import pytest

from evals import baseline_sql, milestone

RUN_DATE = date(2026, 10, 26)


def _generations(*, sql: str | None = None) -> dict:
    question = baseline_sql.scored_questions()[0]
    return {
        "created_at": "2026-10-26T00:00:00+00:00",
        "model": "deepseek/deepseek-flash",
        "prompt_versions": {"system": "system-hash", "sql_generation": "sql-hash"},
        "records": [
            {
                "id": question["id"],
                "question": question["turns"][0],
                "sql": question["reference_sql"][0] if sql is None else sql,
                "error": None,
            }
        ],
    }


def _write(tmp_path: Path, label: str = "baseline-unit") -> Path:
    return milestone.write_baseline_run(_generations(), label, root=tmp_path, run_date=RUN_DATE)


def test_a_baseline_run_writes_the_folder_and_its_lineage_manifest(tmp_path: Path) -> None:
    run_dir = _write(tmp_path)

    assert run_dir == tmp_path / "2026-10-26-baseline-unit"
    assert {path.name for path in run_dir.iterdir()} == {
        milestone.MANIFEST_NAME,
        milestone.CAPTURES_NAME,
        milestone.SCORES_NAME,
    }

    manifest = milestone.read_manifest(run_dir)
    assert manifest["schema_version"] == milestone.SCHEMA_VERSION
    assert manifest["run_id"] == "2026-10-26-baseline-unit"
    assert manifest["runner"] == milestone.RUNNER_BASELINE_SQL
    assert manifest["git"]["commit"]
    assert manifest["dataset"] == {
        "name": "baseline",
        "path": "evals/datasets/baseline.yaml",
        "sha256": manifest["dataset"]["sha256"],
        "record_count": 36,
    }
    assert manifest["prompts"] == {
        "versions": {"system": "system-hash", "sql_generation": "sql-hash"},
        "source": "live",
    }
    assert manifest["models"]["sql_generation"]["model"]
    assert manifest["settings"]["agent"]["query"]["max_rows"] == 20
    assert manifest["snapshot"]["checksum"]
    assert manifest["snapshot"]["manifest_sha256"]
    assert manifest["snapshot"]["row_count"] == 367
    assert manifest["evidence"]["captures_sha256"]
    assert manifest["evidence"]["scores_sha256"]
    assert manifest["retention"]["answers"] == "not_collected"
    assert manifest["retention"]["tool_output"] == "not_collected"
    assert manifest["status"] == "generated"


def test_a_run_is_immutable_and_a_label_must_be_path_safe(tmp_path: Path) -> None:
    _write(tmp_path)
    with pytest.raises(milestone.MilestoneError, match="already exists"):
        _write(tmp_path)
    with pytest.raises(milestone.MilestoneError, match="label"):
        milestone.write_baseline_run(_generations(), "../escape", root=tmp_path, run_date=RUN_DATE)
    with pytest.raises(milestone.MilestoneError, match="label"):
        milestone.write_baseline_run(_generations(), "v1.", root=tmp_path, run_date=RUN_DATE)


def test_a_baseline_run_keeps_only_the_generated_sql(tmp_path: Path) -> None:
    run_dir = _write(tmp_path)

    captures = milestone.read_captures(run_dir)

    assert captures["runner"] == milestone.RUNNER_BASELINE_SQL
    assert captures["records"][0]["sql"]
    assert set(captures["records"][0]) == {"id", "question", "sql", "error"}


def test_evidence_tampering_is_refused_before_scoring(tmp_path: Path) -> None:
    run_dir = _write(tmp_path)
    captures = milestone.read_captures(run_dir)
    captures["records"][0]["sql"] = "SELECT 1"
    (run_dir / milestone.CAPTURES_NAME).write_text(json.dumps(captures), encoding="utf-8")

    with pytest.raises(milestone.MilestoneError, match="digest"):
        milestone.rescore(run_dir, database_url="postgresql://unused")


def test_every_committed_run_matches_its_manifest() -> None:
    manifests = sorted(milestone.RUNS_ROOT.glob("*/manifest.yaml"))
    assert manifests, "the repository has no committed milestone run"

    for path in manifests:
        run_dir = path.parent
        manifest = milestone.read_manifest(run_dir)
        assert manifest["run_id"] == run_dir.name
        assert manifest["runner"] in (
            milestone.RUNNER_BASELINE_SQL,
            milestone.RUNNER_AGENT,
        )
        captures = milestone.read_captures(run_dir)
        scores = milestone.read_scores(run_dir)
        milestone.verify_evidence(manifest, captures, scores)


def test_a_changed_dataset_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "baseline.yaml"
    dataset.write_text("- id: '001'\n", encoding="utf-8")
    manifest = {
        "dataset": {
            "path": "baseline.yaml",
            "sha256": milestone.canonical_file_sha256(dataset),
        }
    }
    monkeypatch.setattr(milestone, "ROOT", tmp_path)

    milestone.verify_dataset(manifest)

    dataset.write_text("- id: '002'\n", encoding="utf-8")
    with pytest.raises(milestone.MilestoneError, match="changed"):
        milestone.verify_dataset(manifest)


def test_a_dataset_digest_ignores_line_endings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "baseline.yaml"
    dataset.write_bytes(b"- id: '001'\n")
    manifest = {
        "dataset": {
            "path": "baseline.yaml",
            "sha256": milestone.canonical_file_sha256(dataset),
        }
    }
    monkeypatch.setattr(milestone, "ROOT", tmp_path)

    dataset.write_bytes(b"- id: '001'\r\n")

    milestone.verify_dataset(manifest)


def test_a_legacy_crlf_dataset_digest_still_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "baseline.yaml"
    dataset.write_bytes(b"- id: '001'\r\n")
    manifest = {
        "dataset": {
            "path": "baseline.yaml",
            "sha256": milestone.file_sha256(dataset),
        }
    }
    monkeypatch.setattr(milestone, "ROOT", tmp_path)

    dataset.write_bytes(b"- id: '001'\n")

    milestone.verify_dataset(manifest)


def test_a_dated_milestone_directory_is_not_gitignored() -> None:
    committed = subprocess.run(
        ["git", "check-ignore", "-q", "evals/runs/2026-10-26-unit/manifest.yaml"],
        cwd=milestone.ROOT,
    )
    local = subprocess.run(
        ["git", "check-ignore", "-q", "evals/runs/local/report.json"],
        cwd=milestone.ROOT,
    )

    assert committed.returncode == 1
    assert local.returncode == 0


def test_baseline_score_then_rescore_reproduces_the_recorded_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _write(tmp_path, "baseline-score")
    monkeypatch.setattr(baseline_sql, "verify_snapshot", lambda _url: None)
    monkeypatch.setattr(baseline_sql, "verify_reader_role", lambda _url: None)
    monkeypatch.setattr(
        baseline_sql,
        "compare_result_sets",
        lambda *_args, **_kwargs: {"status": "PASS", "reference_count": 1, "actual_count": 1},
    )

    baseline_sql.score(run_dir, "postgresql://unused")
    manifest = milestone.read_manifest(run_dir)
    assert manifest["status"] == "scored"
    assert manifest["metrics"] == ["sql_accuracy"]
    assert milestone.rescore(run_dir, database_url="postgresql://unused")["mismatches"] == []


def test_rescore_reports_a_changed_score_as_a_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _write(tmp_path, "baseline-mismatch")
    monkeypatch.setattr(baseline_sql, "verify_snapshot", lambda _url: None)
    monkeypatch.setattr(baseline_sql, "verify_reader_role", lambda _url: None)
    monkeypatch.setattr(
        baseline_sql,
        "compare_result_sets",
        lambda *_args, **_kwargs: {"status": "PASS", "reference_count": 1, "actual_count": 1},
    )
    baseline_sql.score(run_dir, "postgresql://unused")
    monkeypatch.setattr(
        baseline_sql,
        "compare_result_sets",
        lambda *_args, **_kwargs: {"status": "FAIL", "reference_count": 2, "actual_count": 1},
    )

    result = milestone.rescore(run_dir, database_url="postgresql://unused")

    assert len(result["mismatches"]) == 1
    assert "sql_accuracy[" in result["mismatches"][0]


def test_baseline_score_through_the_shared_metric_shape_is_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline_sql, "verify_snapshot", lambda _url: None)
    monkeypatch.setattr(baseline_sql, "verify_reader_role", lambda _url: None)
    monkeypatch.setattr(
        baseline_sql,
        "compare_result_sets",
        lambda *_args, **_kwargs: {"status": "FAIL", "reference_count": 2, "actual_count": 1},
    )
    question = baseline_sql.scored_questions()[0]
    rows = baseline_sql.metric_rows(
        [{"id": question["id"], "question": "q", "sql": question["reference_sql"][0], "error": None}],
        "postgresql://unused",
    )

    assert rows[0]["scenario_id"] == question["id"]
    assert rows[0]["metric"] == "sql_accuracy"
    assert rows[0]["score"] == 0.0
    assert rows[0]["reason"] == "FAIL"
