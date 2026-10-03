"""Offline guards for the shadow-only evidence boundary."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.services.ingestion.evidence_store import (
    RequestAttempt, RunEvidence, ShadowPlan, _declared_endpoint, _normalize, _retrieved_at,
    classify_field_presence, content_digest, stored_request_digest, write_shadow_run,
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
    artifact = RawArtifact(id=1, content_digest=content_digest(payload))
    observation = RawObservation(id=1, source_listing_key="1", field_presence={})
    session = MagicMock()

    def broken(_):
        raise KeyError("jobTitle")

    result = _normalize(session, observation, artifact, payload, _plan(), broken, {}, "v1", 1,
                        datetime.now(UTC), 2, declared_digest=artifact.content_digest)
    assert result.outcome == "quarantined"
    assert result.quarantine_reason_code == "shape_unparseable"
    assert result.output_values is None
    assert session.add.call_count == 1

    def invalid_value(_):
        raise ValueError("invalid value")

    invalid = _normalize(session, observation, artifact, payload, _plan(), invalid_value, {},
                         "v2", 1, datetime.now(UTC), 2,
                         declared_digest=artifact.content_digest)
    assert invalid.outcome == "quarantined"
    assert invalid.quarantine_reason_code == "shape_unparseable"


def test_a_declared_digest_that_disagrees_is_refused_before_the_normalizer_runs():
    """The claim is checked at the boundary, so no value can be invented from it."""
    payload = {"jobId": "1", "jobTitle": "Data Engineer", "companyName": "Example"}
    artifact = RawArtifact(id=1, content_digest=content_digest(payload))
    observation = RawObservation(id=1, source_listing_key="1", field_presence={})
    session = MagicMock()
    normalizer = MagicMock()

    result = _normalize(session, observation, artifact, payload, _plan(), normalizer, {}, "v1", 1,
                        datetime.now(UTC), 2, declared_digest="not-the-payloads-digest")
    assert result.outcome == "quarantined"
    assert result.quarantine_reason_code == "declared_digest_mismatch"
    assert result.output_values is None and result.output_digest is None
    # The declared claim is kept, because the recomputed digest is already on the
    # artifact and only the two together explain the failure.
    assert result.warnings == ["declared_content_hash:not-the-payloads-digest"]
    normalizer.assert_not_called()

    # A payload that no longer hashes to the digest stored beside it is a
    # different failure, and the stored one is reported first because a caller
    # cannot be blamed for a row that changed after it wrote it.
    corrupted = RawArtifact(id=1, content_digest=content_digest({"other": "payload"}))
    stored = _normalize(session, observation, corrupted, payload, _plan(), normalizer, {}, "v1",
                        1, datetime.now(UTC), 2,
                        declared_digest=content_digest(payload))
    assert stored.quarantine_reason_code == "artifact_integrity_failed"
    assert stored.warnings == []
    normalizer.assert_not_called()


def test_field_presence_keeps_four_value_states_distinct():
    """Absent, explicitly null, and empty are three different statements."""
    plan = ShadowPlan(
        "synthetic", "v1", {}, {},
        {"present_field": "present", "null_field": "null", "empty_field": "empty",
         "absent_field": "absent", "unsupported_field": "unsupported"},
        "never", {}, "second", "synthetic:local",
    )
    presence = classify_field_presence(plan, {
        "present_field": "a value",
        "null_field": None,
        "empty_field": [],
        "unsupported_field": None,
    })
    assert presence == {
        "present_field": "present",
        "null_field": "source_missing",
        "empty_field": "source_empty",
        "absent_field": "source_missing",
        "unsupported_field": "source_missing",
    }
    # Only a declaration may record `unsupported`, and a value the provider did
    # send outranks the declaration.
    declared = ShadowPlan(
        "synthetic", "v2", {}, {},
        {"carried": "c", "dropped": {"meaning": "d", "support": "unsupported"}},
        "never", {}, "second", "synthetic:local",
    )
    assert classify_field_presence(declared, {"carried": "x"}) == {
        "carried": "present", "dropped": "unsupported",
    }
    assert classify_field_presence(declared, {"carried": "x", "dropped": "y"}) == {
        "carried": "present", "dropped": "present",
    }


# ---------------------------------------------------------------------------
# The request-attempt record
# ---------------------------------------------------------------------------


def _attempt_plan() -> ShadowPlan:
    return ShadowPlan(
        "synthetic", "v1", {}, {},
        {"title": "display title"}, "never", {"search": "https://api.example.test/scrape/{job_id}"},
        "second", "synthetic:local",
    )


def _attempt(**overrides) -> RequestAttempt:
    return RequestAttempt(**{
        "request_ordinal": 1, "attempt_number": 1, "adapter_id": "fixture",
        "endpoint_name": "search", "endpoint": "https://api.example.test/scrape/7",
        "method": "POST", "path_parameters": {"job_id": "7"}, "query_parameters": {},
        "body": {"input": []}, "credential_env": "FIXTURE_API_KEY",
        "sent_at": datetime(2026, 1, 1, tzinfo=UTC),
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "http_status": 202, "transport_error": None,
        "response_digest": content_digest({"ok": True}), "provider_facts": {},
        **overrides,
    })


def test_a_body_that_cannot_be_stored_is_refused_before_it_is_sent():
    """Digesting is the storage check, so an unstorable body never gets past it."""
    assert stored_request_digest({"a": 1}) == content_digest({"a": 1})
    for body, expected in (
        ({"when": float("nan")}, "cannot be stored as JSON"),
        ({"when": object()}, "cannot be stored as JSON"),
        ([], "must be a mapping"),
    ):
        with pytest.raises(ValueError, match=expected):
            stored_request_digest(body)


def test_a_transport_failure_records_no_status_it_never_received():
    """A response carries a status and no transport failure; a failure carries neither."""
    attempt = _attempt()
    assert attempt.http_status == 202 and attempt.transport_error is None
    with pytest.raises(ValueError, match="exactly one of http_status and transport_error"):
        replace(attempt, http_status=None)
    with pytest.raises(ValueError, match="exactly one of http_status and transport_error"):
        replace(attempt, transport_error="ConnectError", http_status=202)
    failed = replace(attempt, http_status=None, transport_error="ConnectError")
    assert failed.transport_error == "ConnectError" and failed.http_status is None


def test_a_request_attempt_must_be_well_formed():
    with pytest.raises(ValueError, match="request_ordinal counts from 1"):
        _attempt(request_ordinal=0)
    with pytest.raises(ValueError, match="attempt_number counts from 1"):
        _attempt(attempt_number=0)
    with pytest.raises(ValueError, match="must record a endpoint"):
        _attempt(endpoint="  ")
    with pytest.raises(ValueError, match="needs a body mapping"):
        _attempt(body=[])
    with pytest.raises(ValueError, match="sent_at must be a timezone-aware instant"):
        _attempt(sent_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="credential_env must name a secret location"):
        _attempt(credential_env="Bearer sk-value")


def test_a_recorded_response_fact_is_added_once_and_never_replaced():
    """A provider cannot say two different things about one response."""
    attempt = _attempt()
    attempt.note(poll=1, status="running")
    assert attempt.provider_facts == {"poll": 1, "status": "running"}
    with pytest.raises(ValueError, match="already recorded 'status'"):
        attempt.note(status="ready")
    assert attempt.provider_facts["status"] == "running"


def test_run_evidence_is_numbered_from_one_without_gaps():
    """A run nobody can read in order is not evidence of what it sent."""
    attempts = (
        _attempt(request_ordinal=1),
        _attempt(request_ordinal=2, endpoint="https://api.example.test/scrape/8",
                 path_parameters={"job_id": "8"}),
    )
    assert RunEvidence(requests=attempts).outcome == "incomplete"
    for bad in ((), (_attempt(request_ordinal=2),), (_attempt(request_ordinal=1),
                                                    _attempt(request_ordinal=1))):
        with pytest.raises(ValueError):
            RunEvidence(requests=bad)
    with pytest.raises(ValueError, match="request attempts and nothing else"):
        RunEvidence(requests=({"method": "POST"},))


def test_an_endpoint_must_resolve_from_the_executed_plan():
    """The blueprint's rule: a request may only address a declared endpoint."""
    plan = _attempt_plan()
    assert _declared_endpoint(plan, _attempt()) == "https://api.example.test/scrape/7"
    with pytest.raises(ValueError, match="which the executed plan does not declare"):
        _declared_endpoint(plan, _attempt(endpoint_name="snapshot"))
    with pytest.raises(ValueError, match="cannot render the declared"):
        _declared_endpoint(plan, _attempt(path_parameters={}))
    with pytest.raises(ValueError, match="which is not the declared"):
        _declared_endpoint(plan, _attempt(endpoint="https://api.example.test/scrape/9"))
    # An endpoint declared by another plan is not declared by this one.
    with pytest.raises(ValueError, match="which the executed plan does not declare"):
        _declared_endpoint(replace(plan, endpoints={}), _attempt())
