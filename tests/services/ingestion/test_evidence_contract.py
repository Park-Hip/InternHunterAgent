"""Executable contract fixtures against an isolated PostgreSQL schema.

Set SCRATCH_DATABASE_URL to a disposable database. Never point it at production.
"""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from src.services.ingestion import evidence_store
from src.services.ingestion.models import (
    Base, CleanJob, CollectionPlan, CollectionRequestBody, CollectionRequestExecution,
    CollectionRun, DuplicateDelivery, FieldProvenance, NormalizationResult, NormalizedJob,
    RawArtifact, RawObservation, RawPosting,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("SCRATCH_DATABASE_URL"), reason="requires disposable SCRATCH_DATABASE_URL"
)


@pytest.fixture
def db(monkeypatch):
    schema = "shadow_" + uuid4().hex
    url = os.environ["SCRATCH_DATABASE_URL"]
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    factory = sessionmaker(isolated, expire_on_commit=False)
    monkeypatch.setattr(evidence_store, "session_factory", factory)
    try:
        yield factory
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def plan():
    return evidence_store.ShadowPlan(
        source_id="vietnamworks", version="synthetic-v1",
        scope={"queries": ["data engineer"], "pages": [0]},
        caps={"max_jobs": 150}, requested_fields={
            "jobId": "listing key", "jobTitle": "title", "companyName": "company",
        }, completion_rule="terminal_page_observed",
        endpoints={"search": "synthetic://vietnamworks/search"},
        retrieval_precision="second", authorization_revision="synthetic:fixture-only",
    )


def posting(key="1", title="Data Engineer"):
    payload = {"jobId": key, "jobTitle": title, "companyName": "Example"}
    return evidence_store.ShadowDelivery(
        RawPosting(source="vietnamworks", external_id=key, source_url=None,
                   raw_payload=payload, content_hash=evidence_store.content_digest(payload)),
        retrieved_at=datetime.now(UTC),
    )


def normalize(payload):
    return NormalizedJob(
        source="vietnamworks", external_id=payload["jobId"],
        title=payload.get("jobTitle") or "", company=payload.get("companyName") or "",
        role="Data Engineer", is_internship=False, is_salary_negotiable=False,
    )


PATHS = {
    "source": ("@plan.source_id", "copy"), "external_id": ("jobId", "copy"),
    "title": ("jobTitle", "copy"), "company": ("companyName", "copy"),
    "role": ("jobTitle", "derive"), "is_internship": ("jobTitle", "derive"),
    "is_salary_negotiable": ("jobTitle", "derive"),
    "technical_seniority": ("unavailable", "unavailable"),
    "leadership_scope": ("unavailable", "unavailable"),
}


def write(plan, deliveries, **options):
    return evidence_store.write_shadow_run(
        plan, deliveries, run_key=options.pop("run_key", uuid4().hex),
        normalizer=normalize, provenance_paths=PATHS,
        normalization_version="fixture-v1", retention_until=datetime.now(UTC) + timedelta(days=1),
        terminal_condition_met=options.pop("terminal_condition_met", True),
        request_count=options.pop("request_count", 1), **options,
    )


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def _attempt(plan, **overrides) -> evidence_store.RequestAttempt:
    """One well-formed request attempt, for the writer-level boundary checks."""
    return evidence_store.RequestAttempt(**{
        "request_ordinal": 1, "attempt_number": 1, "adapter_id": "fixture-adapter",
        "endpoint_name": "search", "endpoint": plan.endpoints["search"], "method": "GET",
        "path_parameters": {}, "query_parameters": {}, "body": {}, "credential_env": None,
        "sent_at": datetime.now(UTC), "observed_at": datetime.now(UTC),
        "http_status": 200, "transport_error": None,
        "response_digest": evidence_store.content_digest({"ok": True}), "provider_facts": {},
        **overrides,
    })


def _recorded_client(responses: list[dict]) -> httpx.Client:
    """An httpx client that replays recorded provider responses, in order.

    Nothing reaches the network and no credential exists, which is what lets a
    recorded response be written as evidence on a disposable database.
    """
    queue = list(responses)

    def handle(request: httpx.Request) -> httpx.Response:
        if not queue:
            raise AssertionError(f"an undeclared request was sent: {request.url}")
        recorded = queue.pop(0)
        return httpx.Response(
            recorded["status"], json=recorded["body"], headers=recorded["headers"],
        )

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_duplicate_delivery(db, plan):
    first = posting()
    first = evidence_store.ShadowDelivery(first.posting, first.retrieved_at, delivery_id="delivery-1")
    run_id = write(plan, [first, first], run_key="delivery-run")
    with db() as session:
        assert count(session, RawObservation) == 1
        assert count(session, RawArtifact) == 1
        assert count(session, NormalizationResult) == 1
        duplicate = session.scalar(select(DuplicateDelivery))
        original = session.scalar(select(RawObservation))
        assert duplicate.existing_observation_id == original.id
    assert write(plan, [first, first], run_key="delivery-run") == run_id
    with pytest.raises(ValueError, match="different evidence"):
        write(plan, [first], run_key="delivery-run")
    with db() as session:
        assert count(session, RawObservation) == 1
        assert count(session, DuplicateDelivery) == 1


def test_incomplete_coverage(db, plan):
    run_id = write(plan, [posting()], terminal_condition_met=False,
                   failure_category="page_failed")
    with db() as session:
        run = session.get(CollectionRun, run_id)
        assert run.outcome == "failed" and run.coverage_result == "partial"
        assert run.declared_record_cap == 150 and run.observed_record_count == 1
        assert run.declared_scope_digest == evidence_store.content_digest(plan.scope)
        assert count(session, CleanJob) == 0
    # Even an asserted terminal response at a saturated cap is not complete coverage.
    saturated = evidence_store.ShadowPlan(**{**plan.__dict__, "caps": {"max_jobs": 1}, "version": "cap-v1"})
    saturated_id = write(saturated, [posting("2")])
    with db() as session:
        assert session.get(CollectionRun, saturated_id).outcome == "incomplete"
        assert count(session, CleanJob) == 0


def test_mid_stream_failure_records_partial_run(db, plan):
    def interrupted():
        yield posting("seen")
        raise OSError("synthetic transport disconnect")

    run_id = write(plan, interrupted())
    with db() as session:
        run = session.get(CollectionRun, run_id)
        assert run.outcome == "failed"
        assert run.coverage_result == "partial"
        assert run.failure_category == "transport_error"
        assert run.observed_record_count == 1
        assert count(session, RawObservation) == 1
        assert count(session, CleanJob) == 0


def test_replay(db, plan):
    original = write(plan, [posting()])
    replay_id = evidence_store.replay_shadow_run(
        plan, original_run_id=original, run_key="replay-1", reason="rule_correction",
        normalizer=normalize, provenance_paths=PATHS, normalization_version="fixture-v2",
    )
    with db() as session:
        replay = session.get(CollectionRun, replay_id)
        assert replay.run_kind == "replay" and replay.replay_reason == "rule_correction"
        assert replay.replay_of_run_id == original and replay.request_count == 0
        assert replay.coverage_result == "unknown" and replay.observed_record_count == 0
        assert count(session, RawArtifact) == 1
        assert count(session, RawObservation) == 1
        results = session.scalars(select(NormalizationResult).order_by(NormalizationResult.id)).all()
        assert [result.collection_run_id for result in results] == [original, replay_id]
        assert count(session, CleanJob) == 0


def test_rule_correction(db, plan):
    original = write(plan, [posting()])

    def corrected(payload):
        return normalize({**payload, "jobTitle": "Corrected title"})

    corrected_run = evidence_store.replay_shadow_run(
        plan, original_run_id=original, run_key="corrected", reason="rule_correction",
        normalizer=corrected, provenance_paths=PATHS, normalization_version="fixture-v2",
    )
    report = evidence_store.correction_report(original, corrected_run)
    assert report == evidence_store.CorrectionReport(
        input_artifact_count=1, selected_result_count=1, changed_field_count=1,
        quarantine_count=0, changed_rule_versions=("fixture-v1", "fixture-v2"),
    )
    with db() as session:
        results = session.scalars(select(NormalizationResult).order_by(NormalizationResult.id)).all()
        assert [result.normalization_version for result in results] == ["fixture-v1", "fixture-v2"]
        assert results[0].output_values["title"] == "Data Engineer"
        assert results[1].output_values["title"] == "Corrected title"
        changed_fields = {
            field for field in results[0].output_values
            if results[0].output_values[field] != results[1].output_values[field]
        }
        assert changed_fields == {"title"}
        assert {result.rule_version for result in results} == {"fixture-v1", "fixture-v2"}
        assert sum(result.outcome == "quarantined" for result in results) == 0
        assert results[0].output_digest != results[1].output_digest
        assert count(session, FieldProvenance) == 2 * len(PATHS)
        assert results[0].output_values["technical_seniority"] == "unknown"
        assert count(session, CleanJob) == 0


def test_quarantine_and_serving_projection_untouched(db, plan):
    with db() as session:
        session.add_all([
            CleanJob(source="vietnamworks", external_id=f"legacy-{i}",
                     title=f"Title {i}", company="Example", role="Data Engineer",
                     is_internship=False, is_salary_negotiable=False, is_active=i < 105)
            for i in range(308)
        ])
        session.commit()
        before = session.execute(select(CleanJob).order_by(CleanJob.id)).scalars().all()
        baseline = [tuple(getattr(row, column.name) for column in CleanJob.__table__.columns)
                    for row in before]
        assert len(baseline) == 308 and sum(row.is_active for row in before) == 105
    broken = posting("3", "")
    write(plan, [broken])
    with db() as session:
        result = session.scalar(select(NormalizationResult))
        assert result.outcome == "quarantined"
        assert result.quarantine_reason_code == "display_field_invalid"
        assert result.output_values is None
        assert count(session, RawObservation) == 1
        after = session.scalars(select(CleanJob).order_by(CleanJob.id)).all()
        assert [tuple(getattr(row, column.name) for column in CleanJob.__table__.columns)
                for row in after] == baseline


def test_declared_vietnamworks_fixture_plan_is_shadow_only(db):
    from src.core.config import settings
    from src.services.ingestion.normalize.vietnamworks import to_normalized_job
    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.source_registry import resolve_binding

    plan = build_shadow_plan("vietnamworks")
    assert plan.scope["queries"] == settings.ingestion_yaml["queries"]
    assert plan.caps["max_jobs"] == settings.ingestion_yaml["max_jobs"]
    assert plan.endpoints["search"] == settings.ingestion_yaml["api"]["url"]
    item = posting("88")
    run_id = evidence_store.write_shadow_run(
        plan, [item], run_key="configured-fixture", normalizer=to_normalized_job,
        provenance_paths=resolve_binding("vietnamworks").provenance_paths,
        normalization_version=resolve_binding("vietnamworks").normalization_version,
        retention_until=datetime.now(UTC) + timedelta(days=1),
        # A fixture run attests the plan's terminal condition by hand, which is the
        # only way any run may read complete.
        terminal_condition_met=True, request_count=1,
    )
    with db() as session:
        assert session.get(CollectionRun, run_id).outcome == "complete"
        assert count(session, FieldProvenance) > 0
        assert count(session, CleanJob) == 0


def _brightdata_run(plan, responses: list[dict]):
    """Run one recorded provider response sequence through the adapter."""
    from src.services.ingestion.sources.brightdata import BrightDataSource
    from tests.services.ingestion import brightdata_fixtures as recorded

    return BrightDataSource(
        plan, client=_recorded_client(responses), sleep=lambda _seconds: None,
        clock=lambda: recorded.OBSERVED_AT,
    ).collect()


def test_brightdata_handoff_records_every_request_and_no_coverage(db):
    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.sources.brightdata import (
        SOURCE_ID, deliveries, record_shadow_collection,
    )
    from tests.services.ingestion import brightdata_fixtures as recorded

    plan = build_shadow_plan(SOURCE_ID)
    collection = _brightdata_run(plan, recorded.handoff_run())
    run_id = record_shadow_collection(
        plan, collection, run_key="brightdata-handoff",
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )

    with db() as session:
        run = session.get(CollectionRun, run_id)
        # The declared cap and the observed count are two columns, and a run that
        # reached its cap still records no coverage and no completeness.
        assert run.declared_record_cap == 10 and run.observed_record_count == 10
        assert run.coverage_result == "unknown"
        assert run.outcome == "incomplete" and run.failure_category == "terminal_not_observed"
        assert run.request_count == 3
        assert run.declared_scope_digest == evidence_store.content_digest(plan.scope)
        # The run's input digest covers the requests this adapter submitted, not the
        # provider's echo of any of them.
        assert run.input_digest == evidence_store.content_digest({
            "requests": [
                [attempt.request_ordinal, attempt.attempt_number, attempt.adapter_id,
                 attempt.endpoint_name, attempt.endpoint, attempt.method,
                 dict(attempt.query_parameters), dict(attempt.body)]
                for attempt in collection.attempts
            ],
            "deliveries": [
                [delivery.posting.external_id,
                 evidence_store.content_digest(delivery.posting.raw_payload),
                 delivery.retrieved_at.isoformat(), delivery.delivery_id]
                for delivery in deliveries(collection)
            ],
        })
        assert run.input_digest != evidence_store.content_digest(
            collection.records[0]["discovery_input"])

        stored_plan = session.get(CollectionPlan, run.plan_id)
        assert stored_plan.source_id == SOURCE_ID
        assert stored_plan.plan_version == plan.version
        assert stored_plan.authorization_revision == "synthetic:recorded-provider-responses"
        assert stored_plan.requested_fields == plan.requested_fields
        assert stored_plan.declared_caps == {"limit_per_input": 10}

        assert count(session, CleanJob) == 0
        assert count(session, RawObservation) == 10
        assert count(session, NormalizationResult) == 10


def test_every_request_attempt_is_a_first_class_record(db):
    """The submitted request and the provider's account of it are two records a row."""
    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.sources.brightdata import (
        SOURCE_ID, record_shadow_collection,
    )
    from tests.services.ingestion import brightdata_fixtures as recorded

    plan = build_shadow_plan(SOURCE_ID)
    run_id = record_shadow_collection(
        plan, _brightdata_run(plan, recorded.handoff_run()), run_key="brightdata-requests",
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )

    with db() as session:
        # One row per request attempt, keyed and ordered, rather than one document
        # per run: the submit, the single progress poll, and the download.
        requests = session.scalars(select(CollectionRequestBody).where(
            CollectionRequestBody.collection_run_id == run_id,
        ).order_by(CollectionRequestBody.request_ordinal)).all()
        assert [row.request_ordinal for row in requests] == [1, 2, 3]
        assert [row.endpoint_name for row in requests] == ["submit", "progress", "snapshot"]
        assert all(row.adapter_id == "brightdata-linkedin-jobs-v1" for row in requests)
        assert [row.method for row in requests] == ["POST", "GET", "GET"]
        assert all(row.attempt_number == 1 for row in requests)

        submit, progress, download = requests
        # Every endpoint resolves from the executed plan's declared set, which the
        # writer re-renders rather than trusting.
        assert submit.endpoint == plan.endpoints["submit"]
        assert progress.endpoint == plan.endpoints["progress"].format(
            snapshot_id=recorded.SNAPSHOT_ID)
        assert progress.path_parameters == {"snapshot_id": recorded.SNAPSHOT_ID}
        assert download.endpoint == plan.endpoints["snapshot"].format(
            snapshot_id=recorded.SNAPSHOT_ID)

        # The body is stored exactly as it was submitted, with omitted parameters
        # absent rather than rendered back as empty strings by a provider echo.
        assert submit.body == plan.scope["request_body"]
        assert "job_type" not in submit.body["input"][0]
        assert submit.body_digest == evidence_store.content_digest(submit.body)
        assert submit.query_parameters["dataset_id"] == recorded.DATASET_ID
        # A follow-up GET carries no body, and the stored row says so rather than
        # leaving it absent.
        assert progress.body == {} and download.body == {}
        assert progress.body_digest == evidence_store.content_digest({})

        # The plan's declarations travel on the row, so one row is self-describing,
        # and a credential is referenced by name and never by value.
        for row in requests:
            assert row.declared_caps == plan.caps
            assert row.requested_fields == plan.requested_fields
            assert row.sent_at.tzinfo is not None
        assert submit.credential_env == "BRIGHTDATA_API_KEY"
        assert progress.credential_env is None

        executions = session.scalars(select(CollectionRequestExecution).where(
            CollectionRequestExecution.collection_run_id == run_id,
        ).order_by(CollectionRequestExecution.request_body_id)).all()
        assert len(executions) == len(requests)
        # The handoff, the progress envelope, and the terminal delivery are readable
        # per attempt, and each is the provider's account of running one request.
        handoff, poll, delivered = executions
        assert handoff.http_status == 202 and handoff.transport_error is None
        assert handoff.response_digest
        assert handoff.provider_facts["snapshot_id"] == recorded.SNAPSHOT_ID
        assert handoff.provider_facts["delivery"] == "snapshot"
        assert handoff.provider_facts["retry_after_seconds"] == 30
        assert handoff.provider_facts["retry_after_source"] == "provider"
        assert handoff.provider_facts["waited_seconds"] == 30
        assert poll.http_status == 200
        assert poll.provider_facts == {
            "poll": 1, "status": "ready", "terminal": True, "records": 10, "errors": 0,
            "schema_drift": False,
        }
        assert delivered.http_status == 200
        assert delivered.provider_facts == {"records": 10, "shape": "array_of_objects"}
        assert all(row.observed_at.tzinfo is not None for row in executions)

        # No execution row echoes the request: the account of a response is never
        # the request that produced it.
        assert "discovery_input" not in json.dumps(
            [row.provider_facts for row in executions], ensure_ascii=False)


def test_the_retired_execution_representation_stays_readable_and_is_not_written_again(db):
    """`provider-execution-v1` rows already written survive; no run adds another."""
    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.sources.brightdata import (
        SOURCE_ID, record_shadow_collection,
    )
    from tests.services.ingestion import brightdata_fixtures as recorded

    plan = build_shadow_plan(SOURCE_ID)
    run_id = record_shadow_collection(
        plan, _brightdata_run(plan, recorded.handoff_run()), run_key="brightdata-retired",
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )
    with db() as session:
        representations = {row.representation_version for row in session.scalars(
            select(RawArtifact).where(RawArtifact.collection_run_id == run_id)
        ).all()}
        # The provider's execution trace is no longer a retained representation of a
        # retrieval, so it no longer lands in `raw_artifacts` at all.
        assert representations == {"synthetic-json-v1"}
        assert count(session, RawArtifact) == 10

        # A row written under the retired representation is left exactly as it is.
        # `raw_artifacts` is append-only, so it could not have been rewritten anyway,
        # and that is the reason the retirement stops at "stops being written".
        legacy = {
            "record": "provider-execution",
            "request_digest": evidence_store.content_digest({"method": "POST"}),
            "execution": {"submit": {"http_status": 202},
                          "observed_at": recorded.OBSERVED_AT.isoformat()},
        }
        now = datetime.now(UTC)
        session.add(RawArtifact(
            collection_run_id=run_id, content_digest=evidence_store.content_digest(legacy),
            representation_version="provider-execution-v1", media_type="application/json",
            byte_length=1, storage_locator="in-row", representation=legacy, acquired_at=now,
            retention_disposition="retained_full", retention_until=now + timedelta(days=1),
            authorization_revision="synthetic:legacy", redaction_rules=None, created_at=now,
        ))
        session.commit()

    with db() as session:
        readable = session.scalars(select(RawArtifact).where(
            RawArtifact.representation_version == "provider-execution-v1",
        )).all()
        assert len(readable) == 1
        assert readable[0].representation == legacy
        # And a fresh run of the same shape still adds none.
        record_shadow_collection(
            plan, _brightdata_run(plan, recorded.handoff_run()), run_key="brightdata-retired-2",
            retention_until=datetime.now(UTC) + timedelta(days=1),
        )
    with db() as session:
        assert count(session, CollectionRequestBody) == 6


def test_a_transport_failure_still_records_an_attempt_and_its_execution(db):
    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.sources.brightdata import (
        SOURCE_ID, BrightDataSource, record_shadow_collection,
    )
    from tests.services.ingestion import brightdata_fixtures as recorded

    plan = build_shadow_plan(SOURCE_ID)

    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic transport failure", request=_request)

    collection = BrightDataSource(
        plan, client=httpx.Client(transport=httpx.MockTransport(fail)),
        sleep=lambda _seconds: None, clock=lambda: recorded.OBSERVED_AT,
    ).collect()
    run_id = record_shadow_collection(
        plan, collection, run_key="brightdata-transport",
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )

    with db() as session:
        run = session.get(CollectionRun, run_id)
        assert run.outcome == "failed" and run.failure_category == "transport_error"
        assert run.observed_record_count == 0 and run.request_count == 1
        # The attempt happened, so both its records exist even though nothing came
        # back, and the response account names the failure instead of a status.
        request = session.scalar(select(CollectionRequestBody))
        execution = session.scalar(select(CollectionRequestExecution))
        assert request.collection_run_id == run_id and request.request_ordinal == 1
        assert execution.request_body_id == request.id
        assert execution.http_status is None
        assert execution.transport_error == "ConnectError"
        assert execution.response_digest


def test_a_run_whose_request_counter_disagrees_with_its_records_is_refused(db, plan):
    """The counter and the rows that record those requests are one count, stated twice."""
    attempts = (_attempt(plan), _attempt(plan, request_ordinal=2))
    with pytest.raises(ValueError, match="the counter and the request records have to be"):
        write(plan, [], run_key="miscounted", request_count=5,
              run_evidence=evidence_store.RunEvidence(requests=attempts))
    write(plan, [], run_key="counted", request_count=2,
          run_evidence=evidence_store.RunEvidence(requests=attempts))
    with db() as session:
        assert count(session, CollectionRequestBody) == 2
        assert session.get(CollectionRun, 1).request_count == 2
def test_a_request_naming_an_undeclared_endpoint_is_refused(db, plan):
    """The blueprint's endpoint rule, enforced by the writer rather than the adapter."""
    attempt = _attempt(plan, endpoint_name="not-declared")
    with pytest.raises(ValueError, match="which the executed plan does not declare"):
        write(plan, [], run_key="undeclared-endpoint",
              run_evidence=evidence_store.RunEvidence(requests=(attempt,)))
    with db() as session:
        assert count(session, CollectionRun) == 0
        assert count(session, CollectionRequestBody) == 0


def test_an_address_the_plan_does_not_render_to_is_refused(db):
    plan = evidence_store.ShadowPlan(
        source_id="vietnamworks", version="synthetic-v1",
        scope={"queries": ["data engineer"], "pages": [0]}, caps={"max_jobs": 150},
        requested_fields={"jobId": "listing key"}, completion_rule="terminal_page_observed",
        endpoints={"search": "https://api.example.test/scrape/{job_id}"},
        retrieval_precision="second", authorization_revision="synthetic:fixture-only",
    )
    rendered = "https://api.example.test/scrape/7"

    # A provider redirect, a cursor, or a hand-edited row could all name an address the
    # plan's own template does not render to. Retaining one would be evidence nobody
    # could check against the plan, so the run is refused instead.
    with pytest.raises(ValueError, match="which is not the declared"):
        write(plan, [], run_key="mismatched-endpoint", run_evidence=evidence_store.RunEvidence(
            requests=(_attempt(plan, endpoint=f"{rendered}?page=2",
                               path_parameters={"job_id": "7"}),)))
    with pytest.raises(ValueError, match="cannot render the declared"):
        write(plan, [], run_key="unrenderable-endpoint", run_evidence=evidence_store.RunEvidence(
            requests=(_attempt(plan, endpoint=rendered),)))
    # The address the declared template does render to is the one that gets stored.
    write(plan, [], run_key="rendered-endpoint", run_evidence=evidence_store.RunEvidence(
        requests=(_attempt(plan, endpoint=rendered, path_parameters={"job_id": "7"}),)))
    with db() as session:
        stored = session.scalars(select(CollectionRequestBody)).all()
        assert [row.endpoint for row in stored] == [rendered]


def test_a_credential_is_stored_only_as_a_named_location(db, plan):
    """The retained request says where a credential comes from and never carries it.

    Two separate guarantees, and only the second is the database's. A retained
    request has no header column at all, so there is nowhere for a credential to
    land; what the database enforces is the other half, that the credential is
    referenced by a location and not by a value.
    """
    attempt = _attempt(plan, credential_env="FIXTURE_API_KEY")
    assert attempt.credential_env == "FIXTURE_API_KEY"
    assert not hasattr(CollectionRequestBody, "headers")
    with pytest.raises(ValueError, match="must name a secret location, never a value"):
        replace(attempt, credential_env="Bearer sk-not-a-location")

    write(plan, [], run_key="credential-location",
          run_evidence=evidence_store.RunEvidence(requests=(attempt,)))
    with pytest.raises(DBAPIError, match="ck_collection_request_bodies_credential"):
        with db() as session:
            stored = session.scalar(select(CollectionRequestBody))
            assert stored.credential_env == "FIXTURE_API_KEY"
            stored.credential_env = "Bearer sk-not-a-location"
            session.commit()


def test_brightdata_country_stays_null_and_is_never_filled_from_the_request(db):
    import json

    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.sources.brightdata import (
        SOURCE_ID, record_shadow_collection,
    )
    from tests.services.ingestion import brightdata_fixtures as recorded

    plan = build_shadow_plan(SOURCE_ID)
    collection = _brightdata_run(plan, recorded.handoff_run())
    run_id = record_shadow_collection(
        plan, collection, run_key="brightdata-country",
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )

    with db() as session:
        observations = session.scalars(select(RawObservation).where(
            RawObservation.collection_run_id == run_id,
        )).all()
        assert len(observations) == 10
        for observation in observations:
            presence = observation.field_presence
            # Explicitly null is the provider asserting there is no value, and it is
            # recorded under its own field path rather than as a filled-in country.
            assert presence["country_code"] == "source_missing"
            assert presence["apply_link"] == "source_missing"
            assert presence["url"] == "present"
            assert presence["job_title"] == "present"
            assert observation.source_urls["url"].startswith("https://www.linkedin.com/")

            artifact = session.get(RawArtifact, observation.raw_artifact_id)
            assert artifact.representation["country_code"] is None
            result = session.scalar(select(NormalizationResult).where(
                NormalizationResult.observation_id == observation.id,
            ))
            assert result.outcome == "succeeded"
            # The submitted filter said VN, the echo repeated it, and neither reached
            # the projection. The only country-shaped value came from job_location.
            assert result.output_values["location"] == "Hanoi"
            assert "VN" not in json.dumps(result.output_values, ensure_ascii=False)
            assert result.output_values["technical_seniority"] == "unknown"
            assert result.output_values["leadership_scope"] == "unknown"
            provenance = {
                row.output_field: (row.source_field, row.value_state)
                for row in session.scalars(select(FieldProvenance).where(
                    FieldProvenance.normalization_result_id == result.id,
                )).all()
            }
            assert provenance["location"] == ("job_location", "present")
            assert "country_code" not in provenance
            assert provenance["is_salary_negotiable"] == ("unavailable", "unavailable")
            assert provenance["technical_seniority"] == ("unavailable", "unknown")
            assert provenance["leadership_scope"] == ("unavailable", "unknown")
            # A reader of the output values alone can still tell which of them are
            # answers and which are the canonical shape demanding a value.
            assert result.warnings == ["no_source_field:is_salary_negotiable"]


def test_brightdata_a_record_without_a_listing_key_is_quarantined_not_dropped(db):
    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.sources.brightdata import (
        SOURCE_ID, record_shadow_collection,
    )
    from tests.services.ingestion import brightdata_fixtures as recorded

    plan = build_shadow_plan(SOURCE_ID)
    keyless = {**recorded.snapshot_records()[0], "job_posting_id": None}
    collection = _brightdata_run(plan, recorded.inline_run(body=[keyless]))
    run_id = record_shadow_collection(
        plan, collection, run_key="brightdata-no-key",
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )

    with db() as session:
        # The observation is retained, so the evidence is not lost, and the
        # normalization is quarantined rather than projected under a placeholder.
        observation = session.scalar(select(RawObservation))
        assert observation is not None
        assert observation.source_listing_key == ""
        result = session.scalar(select(NormalizationResult))
        assert result.outcome == "quarantined"
        assert result.quarantine_reason_code == "listing_key_absent"
        assert result.output_values is None
        assert count(session, FieldProvenance) == 0
        assert session.get(CollectionRun, run_id).observed_record_count == 1
        assert count(session, CleanJob) == 0


def test_brightdata_evidence_is_idempotent_per_run_key(db):
    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.sources.brightdata import (
        SOURCE_ID, record_shadow_collection,
    )
    from tests.services.ingestion import brightdata_fixtures as recorded

    plan = build_shadow_plan(SOURCE_ID)
    retention = datetime.now(UTC) + timedelta(days=1)
    first = record_shadow_collection(
        plan, _brightdata_run(plan, recorded.handoff_run()), run_key="brightdata-repeat",
        retention_until=retention,
    )
    again = record_shadow_collection(
        plan, _brightdata_run(plan, recorded.handoff_run()), run_key="brightdata-repeat",
        retention_until=retention,
    )
    assert first == again
    with db() as session:
        assert count(session, CollectionRun) == 1
        assert count(session, RawObservation) == 10
        # Ten retained records, and no run-level execution document any more.
        assert count(session, RawArtifact) == 10
        assert count(session, CollectionRequestBody) == 3
        assert count(session, CollectionRequestExecution) == 3


def test_brightdata_empty_and_failed_runs_record_no_completion(db):
    from src.services.ingestion.plans import build_shadow_plan
    from src.services.ingestion.sources.brightdata import (
        SOURCE_ID, record_shadow_collection,
    )
    from tests.services.ingestion import brightdata_fixtures as recorded

    plan = build_shadow_plan(SOURCE_ID)
    retention = datetime.now(UTC) + timedelta(days=1)
    empty = record_shadow_collection(
        plan, _brightdata_run(plan, recorded.handoff_run(body=[])), run_key="brightdata-empty",
        retention_until=retention,
    )
    failed = record_shadow_collection(
        plan, _brightdata_run(plan, recorded.failed_progress_run()),
        run_key="brightdata-failed", retention_until=retention,
    )
    blocked = record_shadow_collection(
        plan, _brightdata_run(plan, recorded.blocked_run()), run_key="brightdata-blocked",
        retention_until=retention,
    )

    with db() as session:
        assert session.get(CollectionRun, empty).observed_record_count == 0
        assert session.get(CollectionRun, empty).outcome == "incomplete"
        assert session.get(CollectionRun, failed).outcome == "failed"
        assert session.get(CollectionRun, failed).failure_category == "page_failed"
        assert session.get(CollectionRun, blocked).outcome == "authorization_blocked"
        assert {run.coverage_result for run in session.scalars(
            select(CollectionRun).where(CollectionRun.id.in_((empty, failed, blocked)))
        ).all()} == {"unknown"}
        assert count(session, CleanJob) == 0


def test_field_presence_and_changed_digest_are_new_evidence(db, plan):
    first = posting("4")
    newer = posting("4", "New title")
    write(plan, [first])
    write(plan, [newer])
    with db() as session:
        observations = session.scalars(select(RawObservation).order_by(RawObservation.id)).all()
        assert len(observations) == 2
        assert observations[0].source_listing_key == observations[1].source_listing_key
        assert observations[0].raw_artifact_id != observations[1].raw_artifact_id
        assert observations[0].field_presence == {
            "jobId": "present", "jobTitle": "present", "companyName": "present",
        }
        assert count(session, NormalizationResult) == 2


def test_real_collection_is_not_activated(db, plan):
    unapproved = evidence_store.ShadowPlan(**{
        **plan.__dict__, "authorization_revision": "adr-0034",
    })
    with pytest.raises(ValueError, match="synthetic fixtures"):
        write(unapproved, [posting()])
    with db() as session:
        assert count(session, CollectionRun) == 0
