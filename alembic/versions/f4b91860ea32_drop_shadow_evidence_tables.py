"""Drop the shadow-evidence tables and their trigger function (ADR-0058).

The upgrade refuses to run while any evidence table holds a row. The downgrade
replays the three revisions that created the tables, so it restores the exact
schema those revisions produced.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f4b91860ea32"
down_revision = "9d4e7f1a2b60"
branch_labels = None
depends_on = None

_EVIDENCE_TABLES = (
    "field_provenance",
    "normalization_results",
    "duplicate_deliveries",
    "raw_observations",
    "raw_artifacts",
    "collection_request_executions",
    "collection_request_bodies",
    "collection_runs",
    "collection_plans",
)
_FUNCTION = "reject_ingestion_evidence_mutation"
_CREATING_REVISIONS = (
    "e51a8c07d942_shadow_evidence.py",
    "a41d7c93be05_request_evidence.py",
    "9d4e7f1a2b60_declared_digest_quarantine.py",
)


def upgrade() -> None:
    bind = op.get_bind()
    occupied = [
        table for table in _EVIDENCE_TABLES
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar()
    ]
    if occupied:
        raise RuntimeError(
            f"refusing to drop non-empty evidence tables {occupied}; export or "
            "inspect them first (ADR-0058)"
        )
    for table in _EVIDENCE_TABLES:
        op.drop_table(table)
    op.execute(f"DROP FUNCTION {_FUNCTION}()")


def _load(filename: str):
    path = Path(__file__).resolve().parent / filename
    spec = spec_from_file_location(f"_replayed_{filename.split('_', 1)[0]}", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def downgrade() -> None:
    for filename in _CREATING_REVISIONS:
        _load(filename).upgrade()