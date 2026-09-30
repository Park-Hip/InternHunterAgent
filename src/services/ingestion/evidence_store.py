"""Synthetic-only shadow evidence writer. No serving projection is imported or written.

The public entry point is deliberately not wired into the production loader. A
real source requires a reviewed G2 retention boundary before this path can be
activated; fixtures can exercise the contract against a disposable database.

An adapter may attach `RunEvidence` to a run: the request it actually submitted,
the provider's account of running it, and the weakest outcome and coverage the run
may record. Everything else in a run is derived here, so an adapter cannot widen
what a run claims.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

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

# Stated once, because the plan factory and the writer both enforce it and a
# declaration with two caps must read the same way wherever it is refused.
RECORD_CAP_RULE = (
    "a plan declares at most one record cap, because a run records exactly one beside the count "
    "the source returned; a request parameter that merely travels in the body belongs in the body"
)


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
class RunEvidence:
    """Run-level facts that only the adapter can supply.

    `submitted_request` is the request exactly as submitted, before it was sent.
    It is never reconstructed from a provider echo, a redirect, or a retry log.
    `provider_execution` is what the provider reported while running it: the
    immediate response, every declared progress transition, and the terminal
    delivery. The two are kept apart on purpose, because the echo of a submitted
    request is not the submitted request.

    `coverage_result` and `outcome` are the weakest claim an adapter may record.
    Neither may read "complete": only the declared terminal condition may do
    that, and a provider that returns no completeness signal can never satisfy
    one.
    """

    submitted_request: dict
    provider_execution: dict
    coverage_result: str = "unknown"
    outcome: str = "incomplete"

    def __post_init__(self) -> None:
        if not isinstance(self.submitted_request, Mapping) or not self.submitted_request:
            raise ValueError("a run must record the request it actually submitted")
        if not isinstance(self.provider_execution, Mapping) or not self.provider_execution:
            raise ValueError("a run must record the provider execution it observed")
        if self.coverage_result not in ("partial", "unknown"):
            raise ValueError("an adapter may only weaken the coverage a run records")
        if self.outcome not in ("incomplete", "failed", "authorization_blocked", "aborted"):
            raise ValueError("only the declared terminal condition may complete a run")


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


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def content_digest(value: object) -> str:
    """SHA-256 over the canonical JSON encoding of a value.

    Canonical means sorted keys, no insignificant whitespace, no NaN, and no
    ASCII escaping, so the same facts always produce the same digest whatever
    order or encoding they arrived in.
    """
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


def declared_record_cap(plan: ShadowPlan) -> int | None:
    """The record cap the plan declared, or None when it declared none.

    A plan declares at most one record cap, keyed by whatever parameter name the
    source uses for it, so a provider-side cap and a client-side cap are recorded
    the same way. Null means no cap was declared, which is a different fact from
    a cap of zero.
    """
    if len(plan.caps) > 1:
        raise ValueError(
            f"plan {plan.source_id!r} declares {sorted(plan.caps)}: {RECORD_CAP_RULE}"
        )
    cap = next(iter(plan.caps.values()), None)
    if cap is not None and (type(cap) is not int or cap < 0):
        raise ValueError("invalid declared cap")
    return cap


def _runtime_digest(plan: ShadowPlan, version: str, paths: ProvenancePaths) -> str:
    return content_digest({"plan": _plan_facts(plan), "normalization_version": version,
                           "provenance_paths": dict(paths)})


def _declared_unsupported(declaration: object) -> bool:
    """True when a plan declares that the provider does not carry a field."""
    return isinstance(declaration, Mapping) and declaration.get("support") == "unsupported"


def classify_field_presence(plan: ShadowPlan, payload: dict) -> dict[str, str]:
    """Map every requested field path of one payload to exactly one value state.

    The four states stay distinct, because collapsing any two of them invents a
    fact the source did not state:

    `present`
        the key is present and carries a value.
    `source_empty`
        the key is present and its value is an empty string, list, or mapping.
        The source emitted a value and that value was empty, which is a
        different statement from the source having no value at all.
    `source_missing`
        the source asserts there is no value: either the key is absent, or the
        key is present and explicitly null. The two are indistinguishable in
        this map and must stay so, because the retained artifact is what
        separates them, and an explicit null is a provider assertion of absence
        rather than silence. Neither is ever filled from request context.
    `unsupported`
        the plan itself declares that the provider does not carry this field.
        It is a declaration and never an inference from absence, so a record
        that does carry a value still records as `present`: evidence outranks a
        declaration.
    """
    presence: dict[str, str] = {}
    for field, declaration in plan.requested_fields.items():
        if field not in payload:
            presence[field] = (
                "unsupported" if _declared_unsupported(declaration) else "source_missing"
            )
        elif payload[field] is None:
            presence[field] = "source_missing"
        elif payload[field] in ("", [], {}):
            presence[field] = "source_empty"
        else:
            presence[field] = "present"
    return presence


def _undeclared_sources(
    populated: set[str], paths: ProvenancePaths, plan: ShadowPlan
) -> set[str]:
    """Source field paths a populated output claims but the plan never requested.

    This is the rule that makes the boundary checkable: a field the plan does
    not request is not available evidence, so a populated output whose lineage
    names one is quarantined instead of normalized. It cannot catch a rule that
    declares a requested path while reading another one, which is why a rule
    version is reviewed rather than trusted.
    """
    undeclared: set[str] = set()
    for field in populated:
        source_field = paths.get(field, ("", ""))[0]
        for part in source_field.split(","):
            if part in ("", "@plan.source_id", "unavailable"):
                continue
            if part not in plan.requested_fields:
                undeclared.add(f"{field}<-{part}")
    return undeclared


def _observed_at(execution: Mapping) -> datetime:
    value = execution.get("observed_at")
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("provider execution observed_at is not an ISO timestamp") from error
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("the provider execution record needs a timezone-aware observed_at")
    return value


def _record_provider_execution(
    session, run: CollectionRun, plan: ShadowPlan, evidence: RunEvidence,
    retention_until: datetime, now: datetime,
) -> RawArtifact:
    """Retain the provider's execution envelopes as one run-level artifact.

    The handoff, the progress transitions, and the terminal delivery are the
    provider's account of how it ran the request, not a listing, so the
    artifact gets no observation row. The submitted request is not restated
    here: it is digested in the run's `input_digest` and referenced by digest,
    which keeps the echo and the request from ever merging into one record.
    """
    observed_at = _observed_at(evidence.provider_execution)
    representation = {
        "record": "provider-execution",
        "request_digest": content_digest(dict(evidence.submitted_request)),
        "execution": deepcopy(dict(evidence.provider_execution)),
    }
    artifact = RawArtifact(
        collection_run_id=run.id, content_digest=content_digest(representation),
        representation_version="provider-execution-v1", media_type="application/json",
        byte_length=len(_bytes(representation)), storage_locator="in-row",
        representation=representation,
        acquired_at=_retrieved_at(observed_at, plan.retrieval_precision),
        retention_disposition="retained_full", retention_until=retention_until,
        authorization_revision=plan.authorization_revision, redaction_rules=None,
        created_at=now,
    )
    session.add(artifact)
    session.flush()
    return artifact


def _structural_defaults(values: dict | None, paths: ProvenancePaths) -> list[str]:
    """Name every populated output the canonical shape required but no source field supplied.

    A required column with no source behind it still has to carry a value, so the
    value is recorded. Naming it here means a reader of the output values alone can
    see which of them are answers and which are structural, without joining the
    provenance table to find out. `technical_seniority` and `leadership_scope` are
    absent on purpose under the #461 decision and are not warnings.
    """
    if not values:
        return []
    return sorted(
        f"no_source_field:{field}"
        for field, value in values.items()
        if value is not None
        and field not in ("technical_seniority", "leadership_scope")
        and paths.get(field, ("", ""))[1] == "unavailable"
    )


def _normalize(
    session, observation: RawObservation, artifact: RawArtifact,
    payload: dict, plan: ShadowPlan, normalizer: Normalizer, paths: ProvenancePaths,
    version: str, attempt: int, now: datetime, processing_run_id: int,
) -> NormalizationResult:
    if content_digest(payload) != artifact.content_digest:
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
                if _undeclared_sources(populated, paths, plan):
                    # A populated value whose lineage names a field the plan never
                    # requested is a rule error, not a value. The artifact stays;
                    # the value does not enter the projection.
                    outcome, reason, values = "quarantined", "unauthorized_field", None
                else:
                    outcome, reason = "succeeded", None

    result = NormalizationResult(
        observation_id=observation.id, collection_run_id=processing_run_id,
        normalization_version=version,
        attempt_number=attempt, outcome=outcome, quarantine_reason_code=reason,
        rule_version=version, output_digest=content_digest(values) if values is not None else None,
        output_values=values, warnings=_structural_defaults(values, paths),
        evaluator_metadata=None, created_at=now,
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
    run_evidence: RunEvidence | None = None,
) -> int:
    """Commit one synthetic run and its evidence atomically, never touching serving.

    Neither count nor an HTTP success establishes completeness. The fixture
    adapter must attest its declared terminal condition explicitly. Real
    collection is prohibited here until a separate G2-approved activation.

    `run_evidence` carries what only the adapter knows: the request it actually
    submitted, the provider's execution of it, and the weakest outcome and
    coverage the run may record. Omitting it leaves today's behavior untouched.
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
    # The run's input is what was asked for and what came back. The submitted
    # request is part of it, so the digest covers the body this adapter sent
    # rather than any echo of it.
    input_digest = content_digest({
        "submitted_request": dict(run_evidence.submitted_request) if run_evidence else None,
        "deliveries": [
            [delivery.posting.external_id, content_digest(delivery.posting.raw_payload),
             _retrieved_at(delivery.retrieved_at, plan.retrieval_precision).isoformat(),
             delivery.delivery_id] for delivery in deliveries
        ],
    })
    runtime_digest = _runtime_digest(plan, normalization_version, provenance_paths)
    cap = declared_record_cap(plan)
    if failure_category not in (None, "transport_error", "page_failed", "budget_exhausted", "terminal_not_observed"):
        raise ValueError("unknown failure category")
    if terminal_condition_met and failure_category:
        raise ValueError("a failed run cannot claim a terminal condition")
    if run_evidence is not None and run_evidence.outcome != "incomplete" and failure_category is None:
        raise ValueError("a failed or blocked run needs an explicit failure category")
    # A saturated safety cap cannot prove that the declared scope was exhausted.
    if cap is not None and len(deliveries) >= cap:
        terminal_condition_met = False
    outcome = "complete" if terminal_condition_met else (
        run_evidence.outcome if run_evidence else ("failed" if failure_category else "incomplete")
    )
    failure = None if outcome == "complete" else (failure_category or "terminal_not_observed")
    coverage = "complete" if terminal_condition_met else (
        run_evidence.coverage_result if run_evidence else "partial"
    )
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
            stored_plan = CollectionPlan(**facts, configuration_digest=content_digest(facts),
                                         created_at=now)
            session.add(stored_plan)
            session.flush()
        elif stored_plan.configuration_digest != content_digest(facts):
            raise ValueError("plan version changed without a new version")
        run = CollectionRun(
            plan_id=stored_plan.id, idempotency_key=run_key, run_kind="manual",
            started_at=now, finished_at=now, outcome=outcome,
            coverage_result=coverage, declared_record_cap=cap,
            observed_record_count=len(deliveries), declared_scope_digest=content_digest(plan.scope),
            request_count=request_count, failure_category=failure,
            configuration_digest=runtime_digest, input_digest=input_digest,
            replay_of_run_id=None, replay_reason=None, created_at=now,
        )
        session.add(run)
        session.flush()
        if run_evidence is not None:
            _record_provider_execution(session, run, plan, run_evidence, retention_until, now)
        local_keys: dict[str, int] = {}
        for delivery in deliveries:
            payload = delivery.posting.raw_payload
            retrieved_at = _retrieved_at(delivery.retrieved_at, plan.retrieval_precision)
            digest = content_digest(payload)
            if delivery.delivery_id:
                key = content_digest({"source": plan.source_id, "delivery_id": delivery.delivery_id})
                existing = session.scalar(select(RawObservation).where(
                    RawObservation.source_id == plan.source_id,
                    RawObservation.delivery_id == delivery.delivery_id,
                ))
            else:
                key = content_digest({"tuple": [run.id, delivery.posting.external_id, digest,
                                                retrieved_at.isoformat()]})
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
            presence = classify_field_presence(plan, payload)
            # The URL is recorded under the field path the rule says carried it,
            # not under a name this writer invented for one source.
            url_path = provenance_paths.get("source_url", ("", ""))[0]
            observation = RawObservation(
                collection_run_id=run.id, raw_artifact_id=artifact.id,
                source_id=plan.source_id, source_listing_key=delivery.posting.external_id,
                provider_listing_key=None, delivery_id=delivery.delivery_id,
                retrieved_at=retrieved_at,
                source_urls=(
                    {url_path: delivery.posting.source_url}
                    if url_path and delivery.posting.source_url else {}
                ),
                field_presence=presence, idempotency_key=key, created_at=now,
            )
            session.add(observation)
            session.flush()
            local_keys[key] = observation.id
            _normalize(session, observation, artifact, payload, plan, normalizer,
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
        if stored_plan is None or stored_plan.configuration_digest != content_digest(_plan_facts(plan)):
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
            input_digest=content_digest({"original_run_id": original_run_id}),
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
            _normalize(session, observation, artifact, artifact.representation, plan,
                       normalizer, provenance_paths, normalization_version,
                       max((item.attempt_number for item in attempts), default=0) + 1, now, run.id)
        session.commit()
        return run.id
