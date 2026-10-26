"""Identity of the frozen production snapshot used by the baseline evals.

The baseline questions in ``evals/datasets/baseline.yaml`` are scored against a
frozen copy of production ``clean_jobs``.  That copy is not committed to the
public repository, but its identity is: this module's manifest records the row
count, a checksum over the contract columns, the Alembic migration revision, and
the capture date.  Scoring refuses to run unless the database it is pointed at
matches that identity.

The dump itself lives in a private location (see ``docs/how-to/evaluate.md``).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import yaml

from src.core.column_contract import VISIBLE_COLUMN_NAMES

MANIFEST_PATHS = [
    Path(__file__).parent / "datasets" / "baseline_manifest.yaml",
    Path(__file__).parent / "snapshot_manifest.yaml",
    Path(__file__).parent / "manifest.yaml",
]
MANIFEST_PATH = MANIFEST_PATHS[0]

CONTRACT_COLUMNS = list(VISIBLE_COLUMN_NAMES)


class SnapshotMismatch(Exception):
    """Raised when a database does not match the committed snapshot manifest."""


def _find_manifest_path() -> Path:
    for path in MANIFEST_PATHS:
        if path.exists():
            return path
    return MANIFEST_PATH


def load_manifest() -> dict[str, Any]:
    path = _find_manifest_path()
    if not path.exists():
        raise FileNotFoundError(f"snapshot manifest not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def manifest() -> dict[str, Any]:
    return load_manifest()


MANIFEST = load_manifest() if MANIFEST_PATH.exists() else {}


def _connect(database_url: str):
    import psycopg

    # Accept SQLAlchemy-style URLs.
    url = database_url
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return psycopg.connect(url)


def compute_checksum(rows: list[tuple[Any, ...]]) -> str:
    hasher = hashlib.sha256()
    for row in rows:
        for value in row:
            hasher.update(repr(value).encode("utf-8"))
            hasher.update(b"|")
        hasher.update(b"\n")
    return hasher.hexdigest()


def snapshot_identity(database_url: str) -> tuple[int, str, str | None]:
    """Return (row_count, checksum, migration_revision) for *database_url*."""
    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM clean_jobs")
            row_count = int(cur.fetchone()[0])
            columns = ", ".join(f'"{c}"' for c in CONTRACT_COLUMNS)
            cur.execute(f"SELECT {columns} FROM clean_jobs ORDER BY id")
            rows = cur.fetchall()
            checksum = compute_checksum(rows)
            revision = None
            try:
                cur.execute("SELECT version_num FROM alembic_version")
                revision = cur.fetchone()[0]
            except Exception:
                revision = None
    return row_count, checksum, revision


def verify_snapshot(database_url: str) -> None:
    """Raise :class:`SnapshotMismatch` if *database_url* does not match the manifest."""
    m = load_manifest()
    row_count, checksum, revision = snapshot_identity(database_url)

    expected_row_count = m.get("row_count")
    if expected_row_count is not None and row_count != int(expected_row_count):
        raise SnapshotMismatch(
            f"row count mismatch: database has {row_count}, manifest expects {expected_row_count}"
        )

    expected_checksum = m.get("checksum")
    if expected_checksum is not None and expected_checksum not in ("", None, "UNSET"):
        if checksum != str(expected_checksum).removeprefix("sha256:"):
            raise SnapshotMismatch(
                f"checksum mismatch: database {checksum}, manifest {expected_checksum}"
            )

    expected_revision = m.get("migration_revision") or m.get("migration") or m.get("revision")
    if expected_revision is not None and expected_revision not in ("", None, "UNSET"):
        if revision != expected_revision:
            raise SnapshotMismatch(
                f"migration revision mismatch: database {revision}, manifest {expected_revision}"
            )


# Aliases for compatibility with callers that use other names.
verify_manifest = verify_snapshot
check_snapshot = verify_snapshot
assert_snapshot_matches_manifest = verify_snapshot
load_manifest_file = load_manifest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Verify a snapshot database against the manifest.")
    parser.add_argument("--database-url", default=os.environ.get("BASELINE_DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("needs --database-url or BASELINE_DATABASE_URL")
    verify_snapshot(args.database_url)
    print("snapshot matches manifest")


if __name__ == "__main__":
    main()
