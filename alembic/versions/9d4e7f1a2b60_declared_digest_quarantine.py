"""Widen the closed quarantine vocabulary with the declared-digest failure.

Revision ID: 9d4e7f1a2b60
Revises: a41d7c93be05
"""

from alembic import op

revision = "9d4e7f1a2b60"
down_revision = "a41d7c93be05"
branch_labels = None
depends_on = None

# The quarantine vocabulary as of this revision, in the order the models spell it.
#
# `declared_digest_mismatch` is new here and it is not `artifact_integrity_failed`
# wearing a second name. That one is the retained representation no longer hashing
# to the digest stored beside it, which points at what happened to the row. This
# one is the payload not hashing to the digest the adapter declared when it
# captured it, which points at what happened on the way in. Both retain the
# evidence; they are read and remediated apart, so the code for each stays
# distinct.
#
# Deliberately a local literal rather than an import from
# src.services.ingestion.models, for the same reason the shadow-evidence revision
# keeps its own table roster: a migration is the historical record of one revision
# and must reproduce it even after the models move on.
_REASONS = (
    "identity_absent", "listing_key_absent", "artifact_integrity_failed",
    "declared_digest_mismatch", "adapter_contract_violated", "shape_unparseable",
    "display_field_invalid", "unauthorized_field",
)

_TABLE = "normalization_results"
_CONSTRAINT = "ck_normalization_results_values"


def _values_condition(reasons: tuple[str, ...]) -> str:
    """The one conditional check a quarantined result has to satisfy.

    Built from the vocabulary rather than pasted per direction, because the two
    directions of this revision must differ in the reasons and in nothing else.
    A downgrade that silently changed any other clause would be indistinguishable
    from a data-loss bug when it ran against a database with retained rows.
    """
    vocabulary = ", ".join(f"'{reason}'" for reason in reasons)
    return (
        "(outcome <> 'quarantined' OR (quarantine_reason_code IS NOT NULL AND "
        f"quarantine_reason_code IN ({vocabulary}))) AND "
        "(outcome = 'quarantined' OR quarantine_reason_code IS NULL) AND "
        "(outcome <> 'succeeded' OR (output_digest IS NOT NULL AND output_values IS NOT NULL))"
    )


def _replace(reasons: tuple[str, ...]) -> None:
    # Dropping and re-adding is a catalog edit, so the append-only trigger never
    # fires and no retained result row is rewritten.
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(_CONSTRAINT, _TABLE, _values_condition(reasons))


def upgrade() -> None:
    _replace(_REASONS)


def downgrade() -> None:
    # Narrowing is refused by the database if a retained row already records the
    # reason this revision added, which is the correct answer: dropping the code
    # would silently orphan the evidence of a capture that failed its own claim.
    _replace(tuple(reason for reason in _REASONS if reason != "declared_digest_mismatch"))
