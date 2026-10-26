"""Committed milestone runs: lineage plus evidence a reviewer can re-score.

A milestone run is one directory, ``evals/runs/<date>-<label>/``, holding three
files:

``manifest.yaml``
    The lineage of the run: the commit, the prompt versions, the model and
    temperature, the relevant settings, the dataset digest, and the snapshot
    manifest checksum (#756).
``captures.json``
    The evidence scoring reads: for a baseline text-to-SQL run, one generation
    record per question.
``scores.json``
    The scores the run recorded, grouped by metric exactly as the CLI prints
    them.

The manifest binds the other two files by digest, so a mismatch is a refusal
rather than a silent re-score of different evidence.

**Content rights (#757).** The full production snapshot cannot be committed
(#756), and a baseline run stores only the SQL the model generated, never the
rows it returned. The decision is recorded in each manifest under ``retention``
so a reviewer does not have to infer it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

import yaml

from evals._paths import ROOT

SCHEMA_VERSION = 1
RUNS_ROOT = ROOT / "evals" / "runs"
MANIFEST_NAME = "manifest.yaml"
CAPTURES_NAME = "captures.json"
SCORES_NAME = "scores.json"

RUNNER_BASELINE_SQL = "baseline_sql"
BASELINE_METRICS = ("sql_accuracy",)

# End on a letter or digit: Windows silently drops a trailing dot, so a label
# like "v1." would name a different directory than the manifest claims.
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9_-])?$")


class MilestoneError(RuntimeError):
    """A milestone run is malformed, already exists, or no longer matches its manifest."""


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_sha256(payload: Any) -> str:
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise MilestoneError(f"evidence is not serializable: {exc}") from exc
    return hashlib.sha256(encoded).hexdigest()


def _git(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_state() -> dict[str, Any]:
    """Name the tree the run was produced from, including an uncommitted state."""
    status = _git("status", "--porcelain")
    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status),
    }


def _config_yaml() -> dict[str, Any]:
    path = ROOT / "config" / "settings.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def settings_snapshot() -> dict[str, Any]:
    """The settings that change a score, with connection strings left out.

    The fixture and snapshot DSNs are local detail, not lineage: a re-score on
    another machine must not look like a different run because its port moved.
    """
    config = _config_yaml()
    agent = config.get("agent") or {}
    return {
        "agent": {
            "stream_turn_timeout_seconds": agent.get("stream_turn_timeout_seconds"),
            "memory": agent.get("memory"),
            "query": agent.get("query"),
            "prompts": agent.get("prompts"),
        },
    }


def models_snapshot() -> dict[str, Any]:
    """Return the model and generation settings for each agent surface."""
    config = _config_yaml()
    agent = config.get("agent") or {}
    providers = agent.get("providers") or {}
    snapshot: dict[str, Any] = {"source": "live"}
    for surface in ("react", "sql_generation"):
        profile = agent.get(surface) or {}
        deployment = providers.get(profile.get("deployment")) or {}
        snapshot[surface] = {
            "deployment": profile.get("deployment"),
            "model": deployment.get("model"),
            "temperature": profile.get("temperature"),
            "max_tokens": profile.get("max_tokens"),
            "timeout": profile.get("timeout"),
            "max_attempts": profile.get("max_attempts"),
            "streaming": profile.get("streaming"),
            "provider_options": profile.get("provider_options") or {},
        }
    return snapshot


def dataset_identity(name: str, path: Path) -> dict[str, Any]:
    """Identify the dataset by digest, not only by a mutable registry name."""
    count: int | None = None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            count = len(payload)
    except (OSError, yaml.YAMLError):
        count = None
    return {
        "name": name,
        "path": _relative(path),
        "sha256": file_sha256(path) if path.exists() else None,
        "record_count": count,
    }


def snapshot_manifest_identity() -> dict[str, Any]:
    """The committed snapshot identity a baseline run is scored against (#756)."""
    from evals import snapshot_manifest

    candidates = [path for path in snapshot_manifest.MANIFEST_PATHS if path.exists()]
    path = candidates[0] if candidates else snapshot_manifest.MANIFEST_PATH
    payload = snapshot_manifest.load_manifest()
    return {
        "manifest": _relative(path),
        "manifest_sha256": file_sha256(path) if path.exists() else None,
        "snapshot": payload.get("snapshot"),
        "capture_date": payload.get("capture_date"),
        "row_count": payload.get("row_count"),
        "checksum": payload.get("checksum"),
        "migration_revision": payload.get("migration_revision"),
    }


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _scores_payload(metrics: list[str], by_metric: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "metrics": metrics, "by_metric": by_metric}


def _run_id(label: str, run_date: date | None) -> tuple[str, str]:
    if _LABEL.fullmatch(label) is None:
        raise MilestoneError(
            f"label {label!r} must be lowercase letters, digits, '.', '_' or '-', "
            "and must not end with '.'"
        )
    day = (run_date or datetime.now(timezone.utc).date()).isoformat()
    return day, f"{day}-{label}"


def _base_manifest(
    *,
    label: str,
    run_id: str,
    dataset_name: str,
    dataset_path: Path,
    capture_source: str,
    prompt_versions: Any,
    prompt_versions_source: str,
    metrics: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "label": label,
        "runner": RUNNER_BASELINE_SQL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": git_state(),
        "dataset": dataset_identity(dataset_name, dataset_path),
        "capture": {
            "source": capture_source,
            "sanitized": False,
        },
        "prompts": {
            "versions": prompt_versions,
            "source": prompt_versions_source,
        },
        "models": models_snapshot(),
        "settings": settings_snapshot(),
        "snapshot": snapshot_manifest_identity(),
        "metrics": metrics,
        "evidence": {
            "captures": CAPTURES_NAME,
            "scores": SCORES_NAME,
        },
        "retention": {
            "answers": "not_collected",
            "tool_output": "not_collected",
            "decision": (
                "A baseline run stores the generated SQL only; the full scraped "
                "snapshot stays private (#756)."
            ),
        },
    }


def _write_run_dir(
    *,
    run_dir: Path,
    manifest: dict[str, Any],
    captures: dict[str, Any],
    scores: dict[str, Any],
) -> Path:
    if run_dir.exists():
        raise MilestoneError(f"milestone run already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    _write_json(run_dir / CAPTURES_NAME, captures)
    _write_json(run_dir / SCORES_NAME, scores)
    manifest = dict(manifest)
    evidence = dict(manifest["evidence"])
    evidence["captures_sha256"] = payload_sha256(captures)
    evidence["scores_sha256"] = payload_sha256(scores)
    manifest["evidence"] = evidence
    manifest["status"] = "scored" if any(scores.get("by_metric", {}).values()) else "generated"
    _write_manifest(run_dir / MANIFEST_NAME, manifest)
    return run_dir


def write_baseline_run(
    generations: dict[str, Any],
    label: str,
    *,
    root: Path = RUNS_ROOT,
    run_date: date | None = None,
) -> Path:
    """Write one text-to-SQL generation pass as a gen-only milestone run.

    ``score`` fills ``scores.json`` when the snapshot is available, so generate
    and score can be days apart without losing the lineage.
    """
    from evals import baseline_sql

    day, run_id = _run_id(label, run_date)
    manifest = _base_manifest(
        label=label,
        run_id=run_id,
        dataset_name="baseline",
        dataset_path=baseline_sql.DATASET,
        capture_source="live",
        prompt_versions=generations.get("prompt_versions"),
        prompt_versions_source="live",
        metrics=[],
    )
    manifest["generation"] = {
        "created_at": generations.get("created_at"),
        "model": generations.get("model"),
        "records": len(generations.get("records") or []),
    }
    captures = {
        "schema_version": SCHEMA_VERSION,
        "runner": RUNNER_BASELINE_SQL,
        "records": generations.get("records") or [],
    }
    return _write_run_dir(
        run_dir=root / run_id,
        manifest=manifest,
        captures=captures,
        scores=_scores_payload([], {}),
    )


def read_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / MANIFEST_NAME
    if not path.exists():
        raise MilestoneError(f"not a milestone run: {path} is missing")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MilestoneError(f"manifest is not an object: {path}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise MilestoneError(
            f"unsupported milestone schema {payload.get('schema_version')!r}; expected {SCHEMA_VERSION}"
        )
    return payload


def read_captures(run_dir: Path) -> dict[str, Any]:
    path = run_dir / CAPTURES_NAME
    if not path.exists():
        raise MilestoneError(f"capture evidence is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MilestoneError(f"capture evidence is not an object: {path}")
    return payload


def read_scores(run_dir: Path) -> dict[str, Any]:
    path = run_dir / SCORES_NAME
    if not path.exists():
        raise MilestoneError(f"score evidence is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MilestoneError(f"score evidence is not an object: {path}")
    return payload


def verify_evidence(manifest: dict[str, Any], captures: dict[str, Any], scores: dict[str, Any]) -> None:
    evidence = manifest.get("evidence") or {}
    expected_captures = evidence.get("captures_sha256")
    expected_scores = evidence.get("scores_sha256")
    if expected_captures != payload_sha256(captures):
        raise MilestoneError("captures.json does not match the manifest digest")
    if expected_scores != payload_sha256(scores):
        raise MilestoneError("scores.json does not match the manifest digest")


def write_scores(
    run_dir: Path,
    *,
    metrics: list[str],
    by_metric: dict[str, list[dict[str, Any]]],
) -> None:
    """Persist scores into an existing run and re-bind the manifest digest."""
    manifest = read_manifest(run_dir)
    scores = _scores_payload(metrics, by_metric)
    _write_json(run_dir / SCORES_NAME, scores)
    manifest["metrics"] = metrics
    manifest["status"] = "scored" if any(by_metric.values()) else "generated"
    evidence = dict(manifest.get("evidence") or {})
    evidence["scores_sha256"] = payload_sha256(scores)
    manifest["evidence"] = evidence
    _write_manifest(run_dir / MANIFEST_NAME, manifest)


def flat_rows(by_metric: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for rows in by_metric.values() for row in rows]


def _row_key(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (row.get("scenario_id"), row.get("turn"), row.get("metric"))


def _row_fingerprint(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": row.get("score"),
        "reason": row.get("reason"),
        "details": row.get("details"),
        "error": row.get("error"),
    }


def compare_scores(
    recorded: list[dict[str, Any]],
    reproduced: list[dict[str, Any]],
    *,
    metrics: list[str],
) -> list[str]:
    """Return one message per recorded score the re-score did not reproduce."""
    wanted = set(metrics)
    recorded_rows = {_row_key(row): row for row in recorded if row.get("metric") in wanted}
    reproduced_rows = {_row_key(row): row for row in reproduced if row.get("metric") in wanted}
    mismatches: list[str] = []
    for key in sorted(recorded_rows, key=lambda item: tuple(str(part) for part in item)):
        label = f"{key[2]}[{key[0]}] turn {key[1]}"
        if key not in reproduced_rows:
            mismatches.append(f"{label}: recorded, but the re-score produced no row")
            continue
        if _row_fingerprint(recorded_rows[key]) != _row_fingerprint(reproduced_rows[key]):
            mismatches.append(
                f"{label}: recorded {_row_fingerprint(recorded_rows[key])!r}, "
                f"re-scored {_row_fingerprint(reproduced_rows[key])!r}"
            )
    for key in sorted(reproduced_rows, key=lambda item: tuple(str(part) for part in item)):
        if key not in recorded_rows:
            mismatches.append(
                f"{key[2]}[{key[0]}] turn {key[1]}: produced by the re-score, absent from the run"
            )
    return mismatches


def _reproducible_metrics(metrics: list[str]) -> list[str]:
    """The recorded metrics the baseline can recompute without a model."""
    return [name for name in metrics if name in BASELINE_METRICS]


def rescore(run_dir: Path, *, database_url: str | None = None) -> dict[str, Any]:
    """Re-score a committed baseline run from its own evidence.

    Every deterministic row must match the recorded score, reason, and details
    exactly. A metric outside the baseline contract is reported as skipped
    rather than claimed as reproduced.
    """
    manifest = read_manifest(run_dir)
    captures = read_captures(run_dir)
    scores = read_scores(run_dir)
    verify_evidence(manifest, captures, scores)

    if manifest.get("runner") != RUNNER_BASELINE_SQL:
        raise MilestoneError(f"unknown milestone runner: {manifest.get('runner')!r}")

    metrics = list(manifest.get("metrics") or [])
    reproducible = _reproducible_metrics(metrics)
    if not reproducible:
        raise MilestoneError("the run records no deterministic metric to re-score")

    from evals import baseline_sql
    from evals.reporting import group_by_metric

    records = captures.get("records")
    if not isinstance(records, list):
        raise MilestoneError("baseline run evidence has no records list")
    database_url = database_url or os.environ.get("BASELINE_DATABASE_URL")
    if not database_url:
        raise MilestoneError("baseline re-scoring needs --database-url or BASELINE_DATABASE_URL")
    reproduced = group_by_metric(baseline_sql.metric_rows(records, database_url))

    mismatches = compare_scores(flat_rows(scores.get("by_metric") or {}), flat_rows(reproduced), metrics=reproducible)
    return {
        "run_id": manifest.get("run_id"),
        "run_dir": str(run_dir),
        "metrics": reproducible,
        "skipped_metrics": [name for name in metrics if name not in reproducible],
        "recorded_rows": len(flat_rows(scores.get("by_metric") or {})),
        "reproduced_rows": len(flat_rows(reproduced)),
        "mismatches": mismatches,
    }
