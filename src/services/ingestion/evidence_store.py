"""Synthetic-only shadow evidence writer. No serving projection is imported or written.

The public entry point is deliberately not wired into the production loader. A
real source requires a reviewed G2 retention boundary before this path can be
activated; fixtures can exercise the contract against a disposable database.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from src.core.config import settings
from src.core.db import session_factory
from src.services.ingestion.models import (
    CollectionPlan,
    CollectionRun,
    DuplicateDelivery,
    FieldProvenance,
    NormalizationResult,
    NormalizedJob,
    RawArtifact,
    RawObservation,
    RawPosting,
)

Normalizer = Callable[[dict], NormalizedJob]
# Each populated output names a source path and its transform. A derived value
# may name several paths, separated by commas, but never an invented source field.
ProvenancePaths = Mapping[str, tuple[str, str]]


@dataclass(frozen=True)
class ShadowPlan:
    source_id: str
    version: str
    scope: dict
    caps: dict
    requested_fields: dict
    completion_rule: str
    endpoints: dict
    retrieval_precision: str
    authorization_revision: str


@dataclass(frozen=True)
class ShadowDelivery:
    posting: RawPosting
    retrieved_at: datetime
    # None invokes the exact four-part run-local key in the blueprint.
    delivery_id: str | None = None


@dataclass(frozen=True)
class CorrectionReport:
    input_artifact_count: int
    selected_result_count: int
    changed_field_count: int
    quarantine_count: int
    changed_rule_versions: tuple[str, ...]


def _bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _digest(value: dict) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _retrieved_at(value: datetime, precision: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError("retrieval time must have a timezone")
    value = value.astimezone(UTC)
    if precision == "second":
        return value.replace(microsecond=0)
    if precision == "millisecond":
        return value.replace(microsecond=value.microsecond // 1000 * 1000)
    if precision == "microsecond":
        return value
    raise ValueError("unsupported retrieval precision")


def _plan_facts(plan: ShadowPlan) -> dict:
    return {
        "source_id": plan.source_id,
        "plan_version": plan.version,
        "declared_scope": plan.scope,
        "declared_caps": plan.caps,
        "requested_fields": plan.requested_fields,
        "declared_completion_rule": plan.completion_rule,
        "declared_endpoint_set": plan.endpoints,
        "retrieval_precision": plan.retrieval_precision,
        "authorization_revision": plan.authorization_revision,
    }


def vietnamworks_fixture_plan() -> ShadowPlan:
    """Describe the existing VietnamWorks search, without sending any request."""
    cfg = settings.ingestion_yaml
    scope = {
        "queries": cfg["queries"], "pages_per_query": cfg["api"]["pages_per_query"],
        "hits_per_page": cfg["api"]["hits_per_page"],
        "job_function": cfg["job_function"],
    }
    fields = {
        "jobId": "source listing key", "jobUrl": "source URL",
        "jobTitle": "display title", "companyName": "display company",
        "jobDescription": "description", "jobRequirement": "requirements",
        "jobLevel": "source level", "jobLevelVI": "source level VI",
        "skills": "source skills", "address": "source address",
        "workingLocations": "source locations", "benefits": "source benefits",
        "expiredOn": "source expiry",
        "createdOn": "source creation", "salaryMin": "salary minimum",
        "salaryMax": "salary maximum", "salaryCurrency": "salary currency",
        "isSalaryVisible": "salary visibility", "jobFunction": "source job function",
    }
    facts = {"scope": scope, "caps": {"max_jobs": cfg["max_jobs"]},
             "fields": fields, "endpoints": {"search": cfg["api"]["url"]}}
    return ShadowPlan(
        source_id="vietnamworks", version="synthetic-" + _digest(facts)[:16],
        scope=scope, caps=facts["caps"], requested_fields=fields,
        completion_rule="every declared page succeeded and the search reached its terminal bound",
        endpoints=facts["endpoints"], retrieval_precision="microsecond",
        authorization_revision="synthetic:fixture-only",
    )


def vietnamworks_provenance_paths() -> dict[str, tuple[str, str]]:
    """Candidate field lineage for the unchanged VietnamWorks normalizer."""
    return {
        "source": ("@plan.source_id", "copy"),
        "external_id": ("jobId", "copy"),
        "source_url": ("jobUrl", "copy"),
        "title": ("jobTitle", "copy"),
        "company": ("companyName", "copy"),
        "role": ("jobTitle,jobFunction", "derive"),
        "description": ("jobDescription,jobRequirement,benefits", "normalize"),
        "tech_stack": ("skills,jobDescription,jobRequirement", "derive"),
        "job_level": ("jobLevel,jobLevelVI", "copy"),
        "location": ("address,workingLocations", "normalize"),
        "listing_expires_on": ("expiredOn", "parse"),
        "created_on": ("createdOn", "parse"),
        "is_internship": ("jobLevel,jobLevelVI", "derive"),
        "salary_min": ("salaryMin,isSalaryVisible", "normalize"),
        "salary_max": ("salaryMax,isSalaryVisible", "normalize"),
        "salary_currency": ("salaryCurrency,isSalaryVisible", "normalize"),
        "is_salary_negotiable": ("isSalaryVisible", "derive"),
        "technical_seniority": ("unavailable", "unavailable"),
        "leadership_scope": ("unavailable", "unavailable"),
    }


def _runtime_digest(plan: ShadowPlan, version: str, paths: ProvenancePaths) -> str:
    return _digest({"plan": _plan_facts(plan), "normalization_version": version,
                    "provenance_paths": dict(paths)})


def _normalize(
    session, observation: RawObservation, artifact: RawArtifact,
    payload: dict, normalizer: Normalizer, paths: ProvenancePaths,
    version: str, attempt: int, now: datetime, processing_run_id: int,
) -> NormalizationResult:
    if _digest(payload) != artifact.content_digest:
        outcome, reason, values = "quarantined", "artifact_integrity_failed", None
    elif not observation.source_listing_key:
        outcome, reason, values = "quarantined", "listing_key_absent", None
    else:
        try:
            job = normalizer(payload)
        except Exception:
            outcome, reason, values = "quarantined", "shape_unparseable", None
        else:
            if job.source != observation.source_id or job.external_id != observation.source_listing_key:
                outcome, reason, values = "quarantined", "adapter_contract_violated", None
            elif not job.title.strip() or not job.company.strip():
                outcome, reason, values = "quarantined", "display_field_invalid", None
            else:
                values = job.model_dump(mode="json")
                values["technical_seniority"] = "unknown"
                values["leadership_scope"] = "unknown"
                populated = {field for field, value in values.items() if value is not None}
                if not populated <= set(paths):
                    raise ValueError("each populated output needs a source-path rule")
                outcome, reason = "succeeded", None

    result = NormalizationResult(
        observation_id=observation.id, collection_run_id=processing_run_id,
        normalization_version=version,
        attempt_number=attempt, outcome=outcome, quarantine_reason_code=reason,
        rule_version=version, output_digest=_digest(values) if values is not None else None,
        output_values=values, warnings=[], evaluator_metadata=None, created_at=now,
    )
    session.add(result)
    session.flush()
    if values is not None:
        for field in sorted(field for field, value in values.items() if value is not None):
            source_field, transform = paths[field]
            states = [observation.field_presence.get(path) for path in source_field.split(",")]
            state = "unknown" if field in ("technical_seniority", "leadership_scope") else (
                "present" if source_field == "@plan.source_id" or "present" in states else
                "source_empty" if "source_empty" in states else
                "source_missing" if "source_missing" in states else "unavailable"
            )
            session.add(FieldProvenance(
                normalization_result_id=result.id, output_field=field,
                source_field=source_field, locale=None, observation_id=observation.id,
                artifact_digest=artifact.content_digest, rule_version=version,
                transform=transform, value_state=state, review_status="automatic",
                created_at=now,
            ))
    return result


def write_shadow_run(
    plan: ShadowPlan, deliveries: Iterable[ShadowDelivery], *,
    run_key: str, normalizer: Normalizer, provenance_paths: ProvenancePaths,
    normalization_version: str, retention_until: datetime,
    terminal_condition_met: bool, request_count: int, failure_category: str | None = None,
) -> int:
    """Commit one synthetic run and its evidence atomically, never touching serving.

    Neither count nor an HTTP success establishes completeness. The fixture
    adapter must attest its declared terminal condition explicitly. Real
    collection is prohibited here until a separate G2-approved activation.
    """
    if not plan.authorization_revision.startswith("synthetic:"):
        raise ValueError("shadow evidence is restricted to synthetic fixtures until G2 approval")
    if request_count < 0 or not run_key or not normalization_version:
        raise ValueError("invalid run metadata")
    now = datetime.now(UTC)
    if retention_until.tzinfo is None or retention_until.astimezone(UTC) <= now:
        raise ValueError("an explicit future fixture retention boundary is required")
    if plan.retrieval_precision not in ("second", "millisecond", "microsecond"):
        raise ValueError("invalid retrieval precision")
    captured: list[ShadowDelivery] = []
    try:
        for delivery in deliveries:
            captured.append(delivery)
    except OSError:
        # The partial result is evidence, never a complete-scope claim.
        failure_category = "transport_error"
        terminal_condition_met = False
    deliveries = captured
    for delivery in deliveries:
        if delivery.posting.source != plan.source_id:
            raise ValueError("delivery source does not match declared plan")
    input_digest = _digest({"deliveries": [
        [delivery.posting.external_id, _digest(delivery.posting.raw_payload),
         _retrieved_at(delivery.retrieved_at, plan.retrieval_precision).isoformat(),
         delivery.delivery_id] for delivery in deliveries
    ]})
    runtime_digest = _runtime_digest(plan, normalization_version, provenance_paths)
    cap = plan.caps.get("max_jobs")
    if cap is not None and (type(cap) is not int or cap < 0):
        raise ValueError("invalid declared cap")
    if failure_category not in (None, "transport_error", "page_failed", "budget_exhausted", "terminal_not_observed"):
        raise ValueError("unknown failure category")
    if terminal_condition_met and failure_category:
        raise ValueError("a failed run cannot claim a terminal condition")
    # A saturated safety cap cannot prove that the declared scope was exhausted.
    if cap is not None and len(deliveries) >= cap:
        terminal_condition_met = False
    outcome = "complete" if terminal_condition_met else (
        "failed" if failure_category else "incomplete"
    )
    failure = None if outcome == "complete" else (failure_category or "terminal_not_observed")
    coverage = "complete" if terminal_condition_met else "partial"
    facts = _plan_facts(plan)
    with session_factory() as session:
        existing_run = session.scalar(select(CollectionRun).where(CollectionRun.idempotency_key == run_key))
        if existing_run is not None:
            if (existing_run.configuration_digest != runtime_digest or
                    existing_run.input_digest != input_digest or
                    existing_run.outcome != outcome or
                    existing_run.failure_category != failure or
                    existing_run.request_count != request_count):
                raise ValueError("run key reused with different evidence or rules")
            return existing_run.id
        stored_plan = session.scalar(select(CollectionPlan).where(
            CollectionPlan.source_id == plan.source_id,
            CollectionPlan.plan_version == plan.version,
        ))
        if stored_plan is None:
            stored_plan = CollectionPlan(**facts, configuration_digest=_digest(facts), created_at=now)
            session.add(stored_plan)
            session.flush()
        elif stored_plan.configuration_digest != _digest(facts):
            raise ValueError("plan version changed without a new version")
        run = CollectionRun(
            plan_id=stored_plan.id, idempotency_key=run_key, run_kind="manual",
            started_at=now, finished_at=now, outcome=outcome,
            coverage_result=coverage, declared_record_cap=cap,
            observed_record_count=len(deliveries), declared_scope_digest=_digest(plan.scope),
            request_count=request_count, failure_category=failure,
            configuration_digest=runtime_digest, input_digest=input_digest,
            replay_of_run_id=None, replay_reason=None, created_at=now,
        )
        session.add(run)
        session.flush()
        local_keys: dict[str, int] = {}
        for delivery in deliveries:
            payload = delivery.posting.raw_payload
            retrieved_at = _retrieved_at(delivery.retrieved_at, plan.retrieval_precision)
            digest = _digest(payload)
            if delivery.delivery_id:
                key = _digest({"source": plan.source_id, "delivery_id": delivery.delivery_id})
                existing = session.scalar(select(RawObservation).where(
                    RawObservation.source_id == plan.source_id,
                    RawObservation.delivery_id == delivery.delivery_id,
                ))
            else:
                key = _digest({"tuple": [run.id, delivery.posting.external_id, digest, retrieved_at.isoformat()]})
                existing = session.scalar(select(RawObservation).where(RawObservation.idempotency_key == key))
            if key in local_keys or existing is not None:
                original_id = local_keys[key] if key in local_keys else existing.id
                if existing is not None:
                    prior_artifact = session.get(RawArtifact, existing.raw_artifact_id)
                    if prior_artifact is None or prior_artifact.content_digest != digest:
                        raise ValueError("delivery identifier reused for different content")
                session.add(DuplicateDelivery(
                    collection_run_id=run.id, existing_observation_id=original_id,
                    created_at=now,
                ))
                continue
            artifact = RawArtifact(
                collection_run_id=run.id, content_digest=digest,
                representation_version="synthetic-json-v1", media_type="application/json",
                byte_length=len(_bytes(payload)), storage_locator="in-row",
                representation=payload, acquired_at=retrieved_at,
                retention_disposition="retained_full", retention_until=retention_until,
                authorization_revision=plan.authorization_revision,
                redaction_rules=None, created_at=now,
            )
            session.add(artifact)
            session.flush()
            presence = {
                field: "source_missing" if field not in payload else (
                    "source_empty" if payload[field] is None or payload[field] in ("", [], {})
                    else "present"
                ) for field in plan.requested_fields
            }
            observation = RawObservation(
                collection_run_id=run.id, raw_artifact_id=artifact.id,
                source_id=plan.source_id, source_listing_key=delivery.posting.external_id,
                provider_listing_key=None, delivery_id=delivery.delivery_id,
                retrieved_at=retrieved_at,
                source_urls={"jobUrl": delivery.posting.source_url} if delivery.posting.source_url else {},
                field_presence=presence, idempotency_key=key, created_at=now,
            )
            session.add(observation)
            session.flush()
            local_keys[key] = observation.id
            _normalize(session, observation, artifact, payload, normalizer,
                       provenance_paths, normalization_version, 1, now, run.id)
        session.commit()
        return run.id


def correction_report(original_run_id: int, replay_run_id: int) -> CorrectionReport:
    """Compare a fixed artifact set with its versioned replay without publication."""
    with session_factory() as session:
        replay = session.get(CollectionRun, replay_run_id)
        if replay is None or replay.replay_of_run_id != original_run_id or replay.replay_reason != "rule_correction":
            raise ValueError("not a correction replay of the specified run")
        observations = session.scalars(select(RawObservation).where(
            RawObservation.collection_run_id == original_run_id
        )).all()
        observation_ids = {item.id for item in observations}
        results = session.scalars(select(NormalizationResult).where(
            NormalizationResult.collection_run_id.in_((original_run_id, replay_run_id))
        )).all()
        before = {item.observation_id: item for item in results
                  if item.collection_run_id == original_run_id}
        after = {item.observation_id: item for item in results
                 if item.collection_run_id == replay_run_id}
        if set(after) != observation_ids or set(before) != observation_ids:
            raise ValueError("correction did not process the fixed observation set")
        changed = sum(
            (old.output_values or {}).get(field) != (new.output_values or {}).get(field)
            for observation_id, new in after.items()
            for old in (before[observation_id],)
            for field in set(old.output_values or {}) | set(new.output_values or {})
        )
        return CorrectionReport(
            input_artifact_count=len({item.raw_artifact_id for item in observations}),
            selected_result_count=len(after), changed_field_count=changed,
            quarantine_count=sum(item.outcome == "quarantined" for item in after.values()),
            changed_rule_versions=tuple(sorted({version
                for item in after.values()
                for version in (before[item.observation_id].rule_version, item.rule_version)
                if before[item.observation_id].rule_version != item.rule_version})),
        )


def replay_shadow_run(
    plan: ShadowPlan, *, original_run_id: int, run_key: str, reason: str,
    normalizer: Normalizer, provenance_paths: ProvenancePaths, normalization_version: str,
) -> int:
    """Process retained observations without acquiring artifacts or claiming new retrieval."""
    if not plan.authorization_revision.startswith("synthetic:"):
        raise ValueError("real replay requires a separately approved retention gate")
    if reason not in ("rule_correction", "verification", "recovery"):
        raise ValueError("invalid replay reason")
    now = datetime.now(UTC)
    runtime_digest = _runtime_digest(plan, normalization_version, provenance_paths)
    with session_factory() as session:
        original = session.get(CollectionRun, original_run_id)
        if original is None:
            raise ValueError("unknown original run")
        stored_plan = session.get(CollectionPlan, original.plan_id)
        if stored_plan is None or stored_plan.configuration_digest != _digest(_plan_facts(plan)):
            raise ValueError("replay plan does not match retained evidence")
        existing = session.scalar(select(CollectionRun).where(CollectionRun.idempotency_key == run_key))
        if existing is not None:
            if (existing.replay_of_run_id != original_run_id or
                    existing.replay_reason != reason or
                    existing.configuration_digest != runtime_digest):
                raise ValueError("replay key reused with different evidence or rules")
            return existing.id
        observations = session.scalars(select(RawObservation).where(
            RawObservation.collection_run_id == original_run_id
        )).all()
        run = CollectionRun(
            plan_id=stored_plan.id, idempotency_key=run_key, run_kind="replay",
            started_at=now, finished_at=now, outcome="complete", coverage_result="unknown",
            declared_record_cap=original.declared_record_cap,
            observed_record_count=0, declared_scope_digest=original.declared_scope_digest,
            request_count=0, failure_category=None,
            configuration_digest=runtime_digest,
            input_digest=_digest({"original_run_id": original_run_id}),
            replay_of_run_id=original_run_id, replay_reason=reason,
            created_at=now,
        )
        session.add(run)
        session.flush()
        for observation in observations:
            artifact = session.get(RawArtifact, observation.raw_artifact_id)
            if artifact is None or artifact.representation is None or artifact.retention_until is None or artifact.retention_until <= now:
                raise ValueError("retained representation unavailable for replay")
            attempts = session.scalars(select(NormalizationResult).where(
                NormalizationResult.observation_id == observation.id,
                NormalizationResult.normalization_version == normalization_version,
            )).all()
            _normalize(session, observation, artifact, artifact.representation,
                       normalizer, provenance_paths, normalization_version,
                       max((item.attempt_number for item in attempts), default=0) + 1, now, run.id)
        session.commit()
        return run.id
