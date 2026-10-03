"""The Bright Data adapter boundary, exercised without a credential and without a request.

Every test here runs a declared plan against recorded provider responses over an
`httpx.MockTransport`, so nothing reaches the network, no credential is read, and no
provider account is touched. The point of the suite is that a maintainer can read it and
conclude the adapter cannot emit a coverage claim, cannot fabricate a country value, and
cannot be made to submit anything other than the request the plan declares.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx
import pytest

from src.services.ingestion.evidence_store import ShadowPlan, declared_record_cap
from src.services.ingestion.normalize.brightdata import to_normalized_job
from src.services.ingestion.plans import build_shadow_plan
from src.services.ingestion.sources.brightdata import (
    SOURCE_ID,
    BrightDataBoundaryError,
    BrightDataSource,
    deliveries,
    shadow_run_evidence,
)
from src.services.ingestion.source_registry import (
    UnknownSourceError,
    resolve_normalizer,
    resolve_binding,
    resolve_source,
)
from tests.services.ingestion import brightdata_fixtures as recorded

SUBMIT_URL = "https://api.brightdata.com/datasets/v3/scrape"
PROGRESS_URL = f"https://api.brightdata.com/datasets/v3/progress/{recorded.SNAPSHOT_ID}"
SNAPSHOT_URL = f"https://api.brightdata.com/datasets/v3/snapshot/{recorded.SNAPSHOT_ID}"


@pytest.fixture
def plan():
    return build_shadow_plan(SOURCE_ID)


class Recorder:
    """An httpx transport that serves recorded responses in order.

    It records every request the adapter made, which is what makes "never follows an
    undeclared URL" a checkable property rather than a promise: the test asserts on the
    full list of URLs the adapter asked for.
    """

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.bodies: list[Any] = []

    @property
    def urls(self) -> list[str]:
        return [str(request.url) for request in self.requests]

    @property
    def endpoints(self) -> list[str]:
        """Every endpoint the adapter addressed, with the query string set aside.

        The full URL is kept separately, because the declared query parameters are
        part of what the adapter submitted.
        """
        return [f"{request.url.scheme}://{request.url.host}{request.url.path}"
                for request in self.requests]

    def client(self) -> httpx.Client:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            self.bodies.append(json.loads(request.content) if request.content else None)
            if not self._responses:
                raise AssertionError(f"the adapter sent an undeclared request: {request.url}")
            recorded_response = self._responses.pop(0)
            return httpx.Response(
                recorded_response["status"], json=recorded_response["body"],
                headers=recorded_response["headers"],
            )

        return httpx.Client(transport=httpx.MockTransport(handle))


def collect(plan, responses: list[dict], *, sleeps: list[float] | None = None
            ) -> tuple[Any, Recorder]:
    recorder = Recorder(responses)
    source = BrightDataSource(
        plan, client=recorder.client(), sleep=(sleeps.append if sleeps is not None else None) or
        (lambda _seconds: None),
        clock=lambda: recorded.OBSERVED_AT,
    )
    return source.collect(), recorder


# ---------------------------------------------------------------------------
# The two immediate-response branches
# ---------------------------------------------------------------------------


def test_inline_200_delivers_records_without_polling(plan):
    collection, recorder = collect(plan, recorded.inline_run())

    assert collection.delivery == "inline"
    assert len(collection.records) == 10
    assert collection.request_count == 1
    assert collection.failure_category is None
    assert collection.outcome == "incomplete"
    # The inline branch issued exactly one request, so the run has exactly one
    # attempt and no progress or download record could exist.
    assert [attempt.endpoint_name for attempt in collection.attempts] == ["submit"]
    assert recorder.endpoints == [SUBMIT_URL]


def test_202_handoff_polls_then_downloads_and_records_every_transition(plan):
    sleeps: list[float] = []
    collection, recorder = collect(
        plan, recorded.handoff_run(statuses=("starting", "running", "ready")), sleeps=sleeps,
    )

    assert collection.delivery == "snapshot"
    assert collection.snapshot_id == recorded.SNAPSHOT_ID
    assert collection.request_count == 5
    # Five requests, five attempts: the submit, one per declared progress state, and
    # the download. None of them is an entry inside a run-level document.
    assert [attempt.request_ordinal for attempt in collection.attempts] == [1, 2, 3, 4, 5]
    assert [attempt.endpoint_name for attempt in collection.attempts] == [
        "submit", "progress", "progress", "progress", "snapshot"]
    submit, *polls, download = collection.attempts
    # Every declared state the provider reported is retained, in order, including the
    # two that are not terminal. Running is not readiness.
    assert [step.provider_facts["status"] for step in polls] == ["starting", "running", "ready"]
    assert [step.provider_facts["poll"] for step in polls] == [1, 2, 3]
    assert [step.provider_facts["schema_drift"] for step in polls] == [False] * 3
    # Two of the three declared transitions are not terminal, and the row says so
    # rather than leaving a reader to join the plan to find out.
    assert [step.provider_facts["terminal"] for step in polls] == [False, False, True]
    assert polls[-1].provider_facts["records"] == 10 and polls[-1].provider_facts["errors"] == 0
    assert submit.http_status == 202
    assert submit.provider_facts["retry_after_seconds"] == recorded.HANDOFF_RETRY_AFTER_SECONDS
    # The delay was the provider's own, so the row says that rather than leaving it
    # indistinguishable from a delay the plan guessed.
    assert submit.provider_facts["retry_after_source"] == "provider"
    assert download.http_status == 200
    # The provider's own retry-after is honored, once before the first poll and once
    # before each further poll. Each wait is charged to the response that asked for
    # it, so "this response cost thirty seconds" is readable without adding anything
    # up, and the run's own total still adds up to what was actually paid.
    assert sleeps == [30.0, 30.0, 30.0]
    assert [a.provider_facts["waited_seconds"] for a in (submit, *polls[:2])] == [30.0] * 3
    assert recorder.endpoints == [SUBMIT_URL, PROGRESS_URL, PROGRESS_URL, PROGRESS_URL, SNAPSHOT_URL]


def test_a_delay_the_provider_never_announced_is_stated_as_the_plans(plan):
    """A plan default must not be recorded as something the provider said."""
    collection, _ = collect(plan, [
        recorded.response(202, recorded.handoff_202()),
        recorded.response(200, recorded.progress()),
        recorded.response(200, recorded.snapshot_records()),
    ])
    submitted, progress, _ = collection.attempts
    assert submitted.provider_facts["retry_after_seconds"] == plan.scope["default_retry_after_seconds"]
    assert submitted.provider_facts["retry_after_source"] == "plan_default"
    assert progress.provider_facts["terminal"] is True


def test_handoff_is_not_announced_by_elapsed_time(plan):
    """A 202 below the documented one-minute limit is still a handoff."""
    collection, _ = collect(plan, recorded.handoff_run())
    assert collection.attempts[0].http_status == 202
    assert collection.attempts[0].sent_at == recorded.OBSERVED_AT
    assert collection.delivery == "snapshot"


# ---------------------------------------------------------------------------
# The endpoint boundary
# ---------------------------------------------------------------------------


def test_no_undeclared_url_is_ever_requested(plan):
    """A provider-supplied URL is never followed, in a body or in a header."""
    collection, recorder = collect(plan, recorded.hostile_handoff_run())

    assert set(recorder.endpoints) == {SUBMIT_URL, PROGRESS_URL, SNAPSHOT_URL}
    assert "linkedin.com/jobs/search" not in " ".join(recorder.endpoints)
    assert "api.brightdata.com/snapshots/" not in " ".join(recorder.endpoints)
    assert len(collection.records) == 10
    # The declared endpoints are the only ones the run could have addressed.
    assert plan.endpoints["submit"] == SUBMIT_URL
    assert plan.endpoints["progress"].format(
        snapshot_id=recorded.SNAPSHOT_ID) in recorder.endpoints


def test_a_hostile_snapshot_identifier_refuses_to_build_a_url(plan):
    responses = [recorded.response(202, recorded.handoff_202(
        snapshot_id="../../datasets/v3/snapshot/other"))]
    with pytest.raises(BrightDataBoundaryError, match="snapshot identifier"):
        collect(plan, responses)


# ---------------------------------------------------------------------------
# The submitted request
# ---------------------------------------------------------------------------


def test_submitted_body_is_the_declared_body_not_the_provider_echo(plan):
    collection, recorder = collect(plan, recorded.handoff_run())

    assert recorder.bodies[0] == plan.scope["request_body"]
    assert recorder.bodies[0]["input"] == [{
        "location": "Hanoi", "keyword": "AI Engineer", "country": "VN",
        "time_range": "Past month", "selective_search": True,
    }]
    assert recorder.bodies[0]["limit_per_input"] == 10
    assert set(recorder.bodies[0]["custom_output_fields"].split("|")) == set(
        plan.requested_fields)
    # The echo of the acquisition context is never the request: the omitted filters
    # came back as empty strings, and none of them was submitted.
    echo = collection.records[0]["discovery_input"]
    assert echo["job_type"] == "" and "job_type" not in recorder.bodies[0]["input"][0]
    assert echo["country"] == "VN"


def test_retained_request_names_the_secret_location_and_no_secret(plan):
    collection, _ = collect(plan, recorded.inline_run())
    submitted = collection.attempts[0]

    assert submitted.credential_env == "BRIGHTDATA_API_KEY"
    assert submitted.method == "POST" and submitted.endpoint == SUBMIT_URL
    assert submitted.query_parameters["dataset_id"] == recorded.DATASET_ID
    assert submitted.body == plan.scope["request_body"]
    serialized = json.dumps({
        "endpoint": submitted.endpoint, "query": submitted.query_parameters,
        "body": submitted.body, "credential_env": submitted.credential_env,
    }, sort_keys=True)
    assert "Authorization" not in serialized and "Bearer" not in serialized


def test_declared_cap_must_travel_with_the_request():
    document = _document_with(body={"limit_per_input": 25})
    plan = build_shadow_plan(SOURCE_ID, config=document)
    with pytest.raises(BrightDataBoundaryError, match="cap limit_per_input"):
        BrightDataSource(plan, client=httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[]))))


def test_omitted_filters_must_stay_omitted():
    document = _document_with(
        body={"input": [dict(
            build_shadow_plan(SOURCE_ID).scope["request_body"]["input"][0], remote="On-site")]},
    )
    plan = build_shadow_plan(SOURCE_ID, config=document)
    with pytest.raises(BrightDataBoundaryError, match="omitted"):
        BrightDataSource(plan, client=httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[]))))


def test_field_selector_must_match_the_requested_fields():
    document = _document_with(body={"custom_output_fields": "url|job_title"})
    plan = build_shadow_plan(SOURCE_ID, config=document)
    with pytest.raises(BrightDataBoundaryError, match="field selector"):
        BrightDataSource(plan, client=httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[]))))


def test_a_credential_bearing_endpoint_must_be_https():
    document = _document_with()
    document["plans"][SOURCE_ID]["declared_endpoints"]["submit"] = (
        "http://api.brightdata.com/datasets/v3/scrape")
    plan = build_shadow_plan(SOURCE_ID, config=document)
    with pytest.raises(BrightDataBoundaryError, match="https"):
        BrightDataSource(plan, client=httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[]))))


def _claims(payload: Any) -> bool:
    """True if any recorded fact states that the run completed or covered a scope."""
    if isinstance(payload, dict):
        return any(
            "coverage" in str(key) or value in ("complete", "covered", "exhausted")
            for key, value in payload.items()
        ) or any(_claims(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(_claims(item) for item in payload)
    return payload in ("complete", "covered", "exhausted")


def _steps(collection: Any) -> list[Any]:
    """The run's progress-poll attempts, in the order the provider reported them."""
    return [attempt for attempt in collection.attempts if attempt.endpoint_name == "progress"]


def _document_with(*, body: dict | None = None) -> dict:
    """A copy of the loaded configuration with one request-body value overridden."""
    from copy import deepcopy

    from src.core.config import settings

    document = deepcopy(settings.ingestion_yaml)
    document["plans"][SOURCE_ID]["declared_scope"]["request_body"].update(body or {})
    return document


# ---------------------------------------------------------------------------
# The four value states, and the country regression
# ---------------------------------------------------------------------------


def test_recorded_records_satisfy_the_recorded_field_presence_matrix(plan):
    """The reconstruction is held to the facts the observation recorded, not to itself."""
    from src.services.ingestion.evidence_store import classify_field_presence

    matrix = recorded.recorded_evidence()["field_presence_matrix"]["fields"]
    records = recorded.snapshot_records()
    assert len(records) == 10
    for record in records:
        presence = classify_field_presence(plan, record)
        for field, expected in matrix.items():
            state = ("present" if expected["explicit_null"] == 0
                     else "source_missing")
            assert presence[field] == state, field
    # Each recorded claim the fixtures depend on, asserted against the records.
    assert matrix["apply_link"]["explicit_null"] == 10
    assert matrix["country_code"]["explicit_null"] == 10
    assert {record["job_seniority_level"] for record in records} == {
        "Entry level", "Mid-Senior level", "Associate"}
    assert len({record["job_seniority_level"] for record in records}) == 3
    assert {record["job_employment_type"] for record in records} == {"Full-time"}
    assert len({record["job_posting_id"] for record in records}) == 10
    assert all(record["url"].startswith("https://www.linkedin.com/")
               for record in records)
    assert all(record["job_posted_time"].endswith("ago") for record in records)
    assert all(record["job_posted_date"].endswith("Z") for record in records)
    assert all(record["application_availability"] is True for record in records)
    # The echo carried ten members: five submitted values and five omitted filters
    # rendered as empty strings, with no member for jobs_to_not_include at all.
    for record in records:
        echo = record["discovery_input"]
        assert len(echo) == 10 and "jobs_to_not_include" not in echo
        assert echo["country"] == "VN" and echo["selective_search"] == "true"
        assert {name: echo[name] for name in
                ("job_type", "experience_level", "remote", "company", "location_radius")
                } == dict.fromkeys(
                    ("job_type", "experience_level", "remote", "company", "location_radius"), "")


def test_the_request_carries_the_cap_in_the_body_and_not_only_the_query():
    """The observation required a body-level cap, because a query-level one is ignored."""
    plan_body = build_shadow_plan(SOURCE_ID).scope["request_body"]
    plan_query = build_shadow_plan(SOURCE_ID).scope["query_parameters"]
    assert plan_body["limit_per_input"] == 10
    assert "limit_per_input" not in plan_query


def test_a_plan_with_no_declared_cap_runs_without_one(plan):
    document = _document_with()
    document["plans"][SOURCE_ID]["declared_caps"] = {}
    document["plans"][SOURCE_ID]["declared_scope"]["request_body"].pop("limit_per_input")
    uncapped = build_shadow_plan(SOURCE_ID, config=document)
    collection, _ = collect(uncapped, recorded.handoff_run())

    assert uncapped.caps == {}
    assert collection.records
    assert declared_record_cap(uncapped) is None


def test_country_is_never_taken_from_the_echoed_request(plan):
    collection, _ = collect(plan, recorded.handoff_run())
    submitted_country = collection.attempts[0].body["input"][0]["country"]
    assert submitted_country == "VN"

    for record in collection.records:
        assert record["country_code"] is None
        job = to_normalized_job(record)
        # The only country-shaped value in the projection is the canonical city the
        # source itself supplied in job_location, and no output field is derived
        # from country_code or from the request.
        assert job.location == "Hanoi"
        assert "country_code" not in job.model_dump()
        assert "VN" not in json.dumps(job.model_dump(mode="json"), ensure_ascii=False)


def test_presence_states_stay_distinct_across_the_field_matrix(plan):
    from src.services.ingestion.evidence_store import classify_field_presence

    record = dict(recorded.snapshot_records()[0])
    record["apply_link"] = ""
    record["country_code"] = None
    del record["job_posted_time"]
    presence = classify_field_presence(plan, record)
    assert presence["apply_link"] == "source_empty"
    assert presence["country_code"] == "source_missing"
    assert presence["job_posted_time"] == "source_missing"
    assert presence["job_title"] == "present"
    assert all(len(json.dumps(value, sort_keys=True)) for value in presence.values())


# ---------------------------------------------------------------------------
# Cap beside observed count
# ---------------------------------------------------------------------------


def test_the_declared_cap_is_reported_beside_the_observed_count(plan):
    collection, _ = collect(plan, recorded.handoff_run())

    assert plan.caps == {"limit_per_input": 10}
    # Two values the run keeps apart: the count that came back, and the declaration
    # that bounds it. Neither is readable on its own.
    assert len(collection.records) == 10
    assert declared_record_cap(plan) == 10
    # Saturation is derived from those two values rather than recorded as a third.
    # Nothing in the run states a verdict, and the count alone says nothing: the ten
    # records and the cap of ten could equally be an exhausted scope or a truncated
    # one, which is why neither is ever reported without the other.
    stored = [attempt.provider_facts for attempt in collection.attempts]
    assert not any("cap_reached" in facts or "complete" in json.dumps(facts) for facts in stored)
    evidence = shadow_run_evidence(collection)
    assert evidence.coverage_result == "unknown"
    assert evidence.outcome == "incomplete"
    assert not _claims([attempt.provider_facts for attempt in evidence.requests])


def test_an_unsaturated_delivery_is_distinguishable_from_a_saturated_one(plan):
    collection, _ = collect(plan, recorded.handoff_run(body=recorded.snapshot_records()[:4]))
    # Read the same way as the saturated case: four observed against a declared cap of
    # ten is not saturation. There is no flag to disagree, because there is no flag.
    assert len(collection.records) == 4
    assert declared_record_cap(plan) == 10
    assert len(collection.records) < declared_record_cap(plan)
    assert not _claims([attempt.provider_facts for attempt in collection.attempts])


# ---------------------------------------------------------------------------
# Empty, partial, blocked and failed states
# ---------------------------------------------------------------------------


def test_an_empty_delivery_records_nothing_and_claims_nothing(plan):
    collection, recorder = collect(plan, recorded.handoff_run(body=[]))

    assert collection.records == ()
    assert collection.failure_category is None
    assert collection.outcome == "incomplete"
    assert collection.attempts[-1].provider_facts["records"] == 0
    assert recorder.endpoints == [SUBMIT_URL, PROGRESS_URL, SNAPSHOT_URL]
    assert deliveries(collection) == []


def test_a_partial_delivery_keeps_its_records_and_fails_the_run(plan):
    collection, _ = collect(plan, recorded.handoff_run(statuses=("ready",), errors=1))

    assert len(collection.records) == 10
    assert collection.failure_category == "page_failed"
    assert collection.outcome == "failed"
    assert _steps(collection)[-1].provider_facts["errors"] == 1
    assert shadow_run_evidence(collection).outcome == "failed"


def test_a_failed_progress_state_never_downloads(plan):
    collection, recorder = collect(plan, recorded.failed_progress_run())

    assert collection.records == ()
    assert collection.failure_category == "page_failed"
    assert collection.outcome == "failed"
    assert _steps(collection)[-1].provider_facts["status"] == "failed"
    assert recorder.endpoints == [SUBMIT_URL, PROGRESS_URL]


def test_an_undocumented_progress_state_is_recorded_not_interpreted(plan):
    """Schema drift keeps every fact observed so far and reads no meaning from it."""
    collection, recorder = collect(plan, [
        recorded.response(202, recorded.handoff_202(), {"retry-after": "30"}),
        recorded.response(200, recorded.progress("paused")),
    ])

    drift = _steps(collection)[-1]
    assert drift.provider_facts["status"] == "paused"
    assert drift.provider_facts["schema_drift"] is True
    assert drift.http_status == 200 and drift.response_digest
    assert collection.outcome == "failed" and collection.failure_category == "page_failed"
    assert collection.records == ()
    # The undocumented state is never treated as terminal and never followed.
    assert SNAPSHOT_URL not in recorder.endpoints
    assert recorder.endpoints == [SUBMIT_URL, PROGRESS_URL]


def test_the_request_must_carry_the_selector_the_plan_declares():
    document = _document_with()
    for location in ("request_body", "query_parameters"):
        document["plans"][SOURCE_ID]["declared_scope"][location].pop("custom_output_fields")
    plan = build_shadow_plan(SOURCE_ID, config=document)
    with pytest.raises(BrightDataBoundaryError, match="no output field selector"):
        BrightDataSource(plan, client=httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[]))))


def test_every_declared_endpoint_must_be_https():
    document = _document_with()
    document["plans"][SOURCE_ID]["declared_endpoints"]["snapshot"] = (
        "http://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}")
    plan = build_shadow_plan(SOURCE_ID, config=document)
    with pytest.raises(BrightDataBoundaryError, match="snapshot endpoint must be https"):
        BrightDataSource(plan, client=httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[]))))


def test_an_account_failure_is_recorded_as_an_authorization_block(plan):
    collection, recorder = collect(plan, recorded.blocked_run())

    assert collection.outcome == "authorization_blocked"
    assert collection.failure_category == "page_failed"
    assert collection.attempts[0].http_status == 400
    # The provider's own account of why it refused is retained next to the status.
    assert collection.attempts[0].provider_facts["provider_message"] == "Customer is not active"
    assert len(recorder.requests) == 1


def test_a_transport_failure_is_recorded_rather_than_raised(plan):
    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic transport failure", request=_request)

    source = BrightDataSource(
        plan, client=httpx.Client(transport=httpx.MockTransport(fail)),
        clock=lambda: recorded.OBSERVED_AT,
    )
    collection = source.collect()

    assert collection.failure_category == "transport_error"
    assert collection.outcome == "failed"
    assert collection.records == ()
    # An attempt that produced no response is still an attempt. The record says so by
    # naming the transport failure and stating no status at all, rather than inventing
    # a status code for a response that never arrived.
    assert collection.attempts[0].transport_error == "ConnectError"
    assert collection.attempts[0].http_status is None


def test_an_envelope_key_the_provider_omitted_is_not_recorded_as_zero(plan):
    """Silence is not a claim, so an absent key must not become a null or a zero."""
    # Progress envelopes the provider sent without `records` or `errors`.
    bare = {"snapshot_id": recorded.SNAPSHOT_ID}
    collection, _ = collect(plan, [
        recorded.response(202, recorded.handoff_202(), {"retry-after": "30"}),
        recorded.response(200, {**bare, "status": "running"}),
        recorded.response(200, {**bare, "status": "ready"}),
        recorded.response(200, recorded.snapshot_records()),
    ])

    polls = _steps(collection)
    assert polls[0].provider_facts == {
        "poll": 1, "status": "running", "terminal": False, "schema_drift": False,
        "waited_seconds": 30.0}
    # The run still reaches its terminal condition on what was actually sent, and an
    # absent error count is not read as a partial delivery.
    assert collection.failure_category is None
    assert len(collection.records) == 10


def test_a_bounded_poll_budget_ends_the_run_without_claiming_anything(plan):
    sleeps: list[float] = []
    collection, recorder = collect(
        plan, recorded.handoff_run(statuses=("running", "running", "running", "running")),
        sleeps=sleeps,
    )

    assert collection.failure_category == "budget_exhausted"
    assert collection.outcome == "incomplete"
    assert collection.records == ()
    assert len(_steps(collection)) == plan.scope["max_progress_polls"]
    assert recorder.endpoints.count(PROGRESS_URL) == plan.scope["max_progress_polls"]
    assert SNAPSHOT_URL not in recorder.endpoints
    # The last poll is the last request, so nothing waits after it. A wait charged to
    # a response that no further request follows would be a response fact that never
    # happened.
    assert sleeps == [30.0] * plan.scope["max_progress_polls"]
    assert not _steps(collection)[-1].provider_facts.get("waited_seconds")


def test_a_body_that_is_not_an_array_of_objects_is_refused(plan):
    collection, _ = collect(plan, recorded.inline_run(body={"errors": ["input failed"]}))

    assert collection.records == ()
    assert collection.failure_category == "page_failed"
    assert collection.attempts[0].provider_facts["shape"] == "not_an_array"
    assert collection.attempts[0].response_digest


# ---------------------------------------------------------------------------
# The authorization boundary
# ---------------------------------------------------------------------------


def test_a_body_that_cannot_be_stored_is_not_sent(plan):
    """A request the evidence store could never retain must never leave this process.

    `float("nan")` has no JSON encoding, so a body carrying one could not be written
    to a request row. The rule is that such a request is not sent at all, rather
    than sent and then found unstorable after the fact.
    """
    unstorable = ShadowPlan(**{
        **plan.__dict__,
        "scope": {**plan.scope, "request_body": {**plan.scope["request_body"],
                                                 "submitted_at": float("nan")}},
    })
    recorder = Recorder(recorded.inline_run())
    source = BrightDataSource(
        unstorable, client=recorder.client(), sleep=lambda _seconds: None,
        clock=lambda: recorded.OBSERVED_AT,
    )
    with pytest.raises(BrightDataBoundaryError, match="body cannot be stored is not sent"):
        source.collect()
    assert recorder.requests == []


def test_the_adapter_refuses_a_plan_that_is_not_its_own(plan):
    with pytest.raises(BrightDataBoundaryError, match="not a plan this adapter"):
        BrightDataSource(
            build_shadow_plan("vietnamworks"),
            client=httpx.Client(transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json=[]))),
        )


def test_the_declared_plan_is_synthetic_while_no_gate_is_met(plan):
    assert plan.authorization_revision == "synthetic:recorded-provider-responses"
    assert plan.authorization_revision.startswith("synthetic:")
    assert plan.version.startswith("synthetic-")


def test_the_source_registry_gives_this_source_no_serving_adapter():
    with pytest.raises(UnknownSourceError, match="no serving adapter"):
        resolve_source(SOURCE_ID)
    # Its normalizer still resolves, because evidence is not gated on serving.
    assert resolve_binding(SOURCE_ID).normalization_version == "brightdata-normalize-v1"
    assert resolve_normalizer(SOURCE_ID) is resolve_binding(SOURCE_ID).normalize


def test_the_undeclared_source_path_is_unchanged():
    source = resolve_source()
    assert source.source == "vietnamworks"
    assert resolve_source("vietnamworks").source == "vietnamworks"
    with pytest.raises(UnknownSourceError, match="unknown source"):
        resolve_source("not-a-declared-source")


def test_deliveries_carry_no_invented_delivery_identifier(plan):
    collection, _ = collect(plan, recorded.handoff_run())
    evidence = deliveries(collection)

    assert len(evidence) == 10
    assert [delivery.delivery_id for delivery in evidence] == [None] * 10
    # The provider's snapshot identifier is an execution reference, not a source
    # listing key, and the two never merge.
    assert {delivery.posting.external_id for delivery in evidence} == {
        record["job_posting_id"] for record in recorded.snapshot_records()
    }
    assert collection.snapshot_id not in {
        delivery.posting.external_id for delivery in evidence
    }
    assert all(
        delivery.retrieved_at == recorded.OBSERVED_AT.replace(microsecond=0)
        or delivery.retrieved_at == recorded.OBSERVED_AT
        for delivery in evidence
    )
    assert isinstance(evidence[0].retrieved_at, datetime) and evidence[0].retrieved_at.tzinfo


def test_the_evidence_a_run_records_keeps_request_and_echo_apart(plan):
    collection, _ = collect(plan, recorded.handoff_run())
    evidence = shadow_run_evidence(collection)

    assert [attempt.endpoint_name for attempt in evidence.requests] == [
        "submit", "progress", "snapshot"]
    assert all(attempt.observed_at == recorded.OBSERVED_AT for attempt in evidence.requests)
    # The submitted request is a separate fact from every response's account of
    # running it. No response's facts were ever written into a request body, which
    # is what keeps the provider echo from reading as the request.
    submitted = evidence.requests[0]
    assert submitted.body == plan.scope["request_body"]
    assert submitted.body is not collection.records[0]["discovery_input"]
    assert all(
        "discovery_input" not in json.dumps(attempt.provider_facts, sort_keys=True)
        for attempt in evidence.requests
    )


def test_every_request_the_run_issues_is_its_own_attempt(plan):
    collection, _ = collect(plan, recorded.handoff_run(statuses=("starting", "running", "ready")))

    # A retry, a second submit, or a second discovery input inside one run is its own
    # attempt with its own ordinal, not a list entry inside a single run-level
    # document, so the run stays walkable in the order it actually happened.
    assert [attempt.request_ordinal for attempt in collection.attempts] == [1, 2, 3, 4, 5]
    assert all(attempt.attempt_number == 1 for attempt in collection.attempts)
    assert collection.request_count == len(collection.attempts)
    # Each attempt names the declared endpoint it resolved from and the parameters
    # that render it, which is what makes the endpoint checkable against the plan.
    for attempt in collection.attempts:
        assert attempt.endpoint_name in plan.endpoints
        assert plan.endpoints[attempt.endpoint_name].format(**attempt.path_parameters) == attempt.endpoint


def test_a_delivery_without_a_listing_key_is_retained_not_dropped(plan):
    records = list(recorded.snapshot_records()[:1])
    records[0] = {**records[0], "job_posting_id": None}
    collection, _ = collect(plan, recorded.inline_run(body=records))

    assert len(collection.records) == 1
    assert deliveries(collection)[0].posting.external_id == ""
