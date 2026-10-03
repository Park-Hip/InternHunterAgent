"""Offline guards for the shadow-only evidence boundary."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.services.ingestion.evidence_store import (
    RequestAttempt,
    RunEvidence,
    ShadowPlan,
    SubmittedRequest,
    _normalize,
    _recorded_at,
    classify_field_presence,
    content_digest,
    validate_request_attempt,
    write_shadow_run,
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


def test_a_recorded_instant_is_floored_never_rounded_up():
    at = datetime(2026, 1, 1, 0, 0, 0, 999999, tzinfo=UTC)
    assert _recorded_at(at, "second", "sent_at").microsecond == 0
    assert _recorded_at(at, "millisecond", "sent_at").microsecond == 999000
    assert _recorded_at(at, "microsecond", "sent_at") == at
    with pytest.raises(ValueError, match="sent_at"):
        _recorded_at(at.replace(tzinfo=None), "second", "sent_at")


def test_invalid_payload_quarantines_without_fabricating_values():
    payload = {"jobId": "1"}
    artifact = RawArtifact(id=1, content_digest=content_digest(payload))
    observation = RawObservation(id=1, source_listing_key="1", field_presence={})
    session = MagicMock()

    def broken(_):
        raise KeyError("jobTitle")

    result = _normalize(session, observation, artifact, payload, _plan(), broken, {}, "v1", 1,
                        datetime.now(UTC), 2)
    assert result.outcome == "quarantined"
    assert result.quarantine_reason_code == "shape_unparseable"
    assert result.output_values is None
    assert session.add.call_count == 1

    def invalid_value(_):
        raise ValueError("invalid value")

    invalid = _normalize(session, observation, artifact, payload, _plan(), invalid_value, {},
                         "v2", 1, datetime.now(UTC), 2)
    assert invalid.outcome == "quarantined"
    assert invalid.quarantine_reason_code == "shape_unparseable"


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
# What may be sent, and what a run may record about it
# ---------------------------------------------------------------------------


def _request(**overrides) -> SubmittedRequest:
    return SubmittedRequest(**{
        "method": "GET", "endpoint": "https://provider.test/v3/progress/abc123",
        "endpoint_name": "progress", "query": {"format": "json"}, "body": None, **overrides})


def _attempt(ordinal: int, attempt_number: int = 1, **overrides) -> RequestAttempt:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    return RequestAttempt(**{
        "ordinal": ordinal, "attempt_number": attempt_number, "phase": "progress",
        "request": _request(), "sent_at": at, "observed_at": at,
        "response_digest": content_digest({"poll": ordinal}), "http_status": 200, **overrides})


def test_an_undeclared_endpoint_is_refused_before_it_is_sent_or_stored():
    plan = ShadowPlan(
        "synthetic", "v1", {}, {}, {}, "never",
        {"progress": "https://provider.test/v3/progress/{snapshot_id}"},
        "second", "synthetic:local",
    )
    validate_request_attempt(plan, _request())

    # A name the plan never declared.
    with pytest.raises(ValueError, match="declared endpoint set"):
        validate_request_attempt(plan, _request(endpoint_name="download"))
    # A name it declared, reached by a URL the template does not authorise.
    for endpoint in (
        "https://provider.test/v3/snapshot/abc123",
        "https://other.test/v3/progress/abc123",
        "https://provider.test/v3/progress/abc123/extra",
        "https://provider.test/v3/progress/abc123?format=json",
    ):
        with pytest.raises(ValueError):
            validate_request_attempt(plan, _request(endpoint=endpoint))


def test_a_request_whose_body_cannot_be_stored_is_not_sent():
    plan = ShadowPlan(
        "synthetic", "v1", {}, {}, {}, "never", {"submit": "https://provider.test/v3/scrape"},
        "second", "synthetic:local",
    )
    # A value the evidence could not be written as, a credential travelling in the
    # body rather than being named by its location, and a credential named under its
    # own conventional key all stop the attempt.
    for body, message in (
        ({"limit": float("nan")}, "cannot be stored"),
        ({"BRIGHTDATA_API_KEY": "secret"}, "retained by its named location"),
        ({"headers": {"Authorization": "Bearer secret"}}, "retained by its named location"),
        ({"api_key": "secret"}, "retained by its named location"),
    ):
        with pytest.raises(ValueError, match=message):
            validate_request_attempt(plan, _request(
                method="POST", endpoint="https://provider.test/v3/scrape",
                endpoint_name="submit", query={}, body=body, credential_env="BRIGHTDATA_API_KEY",
            ))
    # A method that carries a body cannot record an absent one, which is the same
    # rule the stored record is checked against.
    with pytest.raises(ValueError, match="carries a body by definition"):
        validate_request_attempt(plan, _request(
            method="POST", endpoint="https://provider.test/v3/scrape", endpoint_name="submit",
            query={}, body=None,
        ))
    with pytest.raises(ValueError, match="uppercase"):
        _request(method="get")


def test_a_credential_key_is_refused_even_when_no_location_is_named():
    """A plan that travels a credential without saying so is the worse case."""
    plan = ShadowPlan(
        "synthetic", "v1", {}, {}, {}, "never", {"submit": "https://provider.test/v3/scrape"},
        "second", "synthetic:local",
    )
    for key in ("Authorization", "x-api-key", "password"):
        with pytest.raises(ValueError, match="retained by its named location"):
            validate_request_attempt(plan, _request(
                method="POST", endpoint="https://provider.test/v3/scrape",
                endpoint_name="submit", query={}, body={key: "secret"},
            ))


def test_a_retry_is_a_second_attempt_not_an_edit_of_the_first():
    attempts = (_attempt(1), _attempt(1, attempt_number=2), _attempt(2))
    evidence = RunEvidence(attempts=attempts, adapter_id="fixture-adapter-v1")

    # The key is (ordinal, attempt), so a retry keeps its own row and the positions
    # of the requests stay gapless.
    assert [(item.ordinal, item.attempt_number) for item in evidence.attempts] == [
        (1, 1), (1, 2), (2, 1)]
    with pytest.raises(ValueError, match="position and a retry number"):
        RunEvidence(attempts=(_attempt(1), _attempt(1)), adapter_id="fixture-adapter-v1")
    with pytest.raises(ValueError, match="no gap"):
        RunEvidence(attempts=(_attempt(1), _attempt(3)), adapter_id="fixture-adapter-v1")
    # A third attempt with no first or second would be a retry history the run never
    # had, and the key alone cannot show that.
    with pytest.raises(ValueError, match="retry count starts at 1"):
        RunEvidence(attempts=(_attempt(1, attempt_number=3),), adapter_id="fixture-adapter-v1")


def test_an_attempt_records_a_status_or_the_reason_none_arrived():
    with pytest.raises(ValueError, match="observed a status"):
        _attempt(1, http_status=None)
    with pytest.raises(ValueError, match="at least 100"):
        _attempt(1, http_status=0)
    with pytest.raises(ValueError, match="at least 100"):
        _attempt(1, http_status=-1)
    # A transport failure is evidence too: it has a reason and a digest, and no
    # status, because the provider never answered.
    failed = _attempt(1, http_status=None, transport_error="ConnectError")
    assert failed.transport_error == "ConnectError" and failed.response_digest
