"""Offline guards for the shadow-only evidence boundary."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.services.ingestion.evidence_store import (
    ShadowPlan, _digest, _normalize, _retrieved_at, write_shadow_run,
)
from src.services.ingestion.models import RawArtifact, RawObservation


def _plan():
    return ShadowPlan(
        "vietnamworks", "v1", {"query": "x"}, {"max_jobs": 150},
        {"jobId": "source key"}, "terminal page", {"search": "fixture"},
        "millisecond", "synthetic:local",
    )


def test_no_real_retention_without_g2():
    plan = ShadowPlan(**{**_plan().__dict__, "authorization_revision": "adr-0034"})
    with patch("src.services.ingestion.evidence_store.session_factory") as db:
        with pytest.raises(ValueError, match="synthetic fixtures"):
            write_shadow_run(
                plan, [], run_key="x", normalizer=MagicMock(), provenance_paths={},
                normalization_version="v1", retention_until=datetime.now(UTC) + timedelta(days=1),
                terminal_condition_met=True, request_count=0,
            )
        db.assert_not_called()


def test_retrieval_time_is_floored_never_rounded_up():
    at = datetime(2026, 1, 1, 0, 0, 0, 999999, tzinfo=UTC)
    assert _retrieved_at(at, "second").microsecond == 0
    assert _retrieved_at(at, "millisecond").microsecond == 999000
    with pytest.raises(ValueError):
        _retrieved_at(at.replace(tzinfo=None), "second")


def test_invalid_payload_quarantines_without_fabricating_values():
    payload = {"jobId": "1"}
    artifact = RawArtifact(id=1, content_digest=_digest(payload))
    observation = RawObservation(id=1, source_listing_key="1", field_presence={})
    session = MagicMock()

    def broken(_):
        raise KeyError("jobTitle")

    result = _normalize(session, observation, artifact, payload, broken, {}, "v1", 1, datetime.now(UTC), 2)
    assert result.outcome == "quarantined"
    assert result.quarantine_reason_code == "shape_unparseable"
    assert result.output_values is None
    assert session.add.call_count == 1

    def invalid_value(_):
        raise ValueError("invalid value")

    invalid = _normalize(session, observation, artifact, payload,
                         invalid_value, {}, "v2", 1, datetime.now(UTC), 2)
    assert invalid.outcome == "quarantined"
    assert invalid.quarantine_reason_code == "shape_unparseable"
