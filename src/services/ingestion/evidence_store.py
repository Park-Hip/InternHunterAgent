"""Synthetic-only shadow evidence writer. No serving projection is imported or written.

The public entry point is deliberately not wired into the production loader. A
real source requires a reviewed G2 retention boundary before this path can be
activated; fixtures can exercise the contract against a disposable database.

An adapter may attach `RunEvidence` to a run: every request attempt it issued, each one
carrying both the request it sent and the provider's account of that attempt, plus the
weakest outcome and coverage the run may record. Everything else in a run is derived
here, so an adapter cannot widen what a run claims.

Two rules make the request records checkable rather than decorative.

* A request is built and validated before it is sent, and `validate_request_attempt` is
  the single definition of what may be sent and what may be stored. The adapter calls it
  before a request leaves, so no request is ever spent on evidence that could not have been
  written, and the writer calls it again before a row exists, so the two cannot drift
  apart. An endpoint outside the plan's declared endpoint set, a URL that does not resolve
  to that declared endpoint, a body that cannot be encoded, or a credential travelling in
  the body all stop the attempt.
* The request and the provider's account of it are separate records with separate
  digests. The echo of a submitted request is not the submitted request, and one record
  holding both would let a later reader take one for the other.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field
from datetime import UTC, datetime

from sqlalchemy import select

from src.core.db import session_factory
from src.services.ingestion.models import (
    CollectionPlan,
    CollectionRequestBody,
    CollectionRequestExecution,
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
# The methods that carry no body by definition. Stated once because the request record
# is checked against this list in the database as well as here, and an absent body on
# any other method is a fact no record could store.
BODYLESS_METHODS = ("GET", "HEAD", "DELETE")

# A credential is retained by the name of the location it comes from, so a value can
# never be stored in the request record even by accident.
SECRET_LOCATION_PATTERN = r"^[A-Z][A-Z0-9_]*$"

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
class SubmittedRequest:
    """One request, exactly as it will be sent, and nothing the provider said.

    `body` is the request's own body. An omitted parameter is absent from it rather
    than empty, and a credential is referenced by its named secret location rather
    than travelling in the record. `endpoint` is the URL alone: query parameters
    travel in `query`, so a stored endpoint stays comparable to a declared endpoint
    template.
    """

    method: str
    endpoint: str
    endpoint_name: str
    query: Mapping
    body: Mapping | None
    credential_env: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.method, str) or not self.method:
            raise ValueError("a request records the method it was sent with")
        if self.method != self.method.upper():
            # The stored method is compared against a fixed list of the methods that
            # carry no body, in the database as well as here, and a lowercase method
            # would read as one this contract does not recognise.
            raise ValueError("a request method is uppercase, as HTTP defines it")
        if not isinstance(self.endpoint, str) or not self.endpoint:
            raise ValueError("a request records the endpoint it was sent to")
        if not isinstance(self.endpoint_name, str) or not self.endpoint_name:
            raise ValueError("a request names the declared endpoint it resolves to")
        if not isinstance(self.query, Mapping):
            raise ValueError("a request records the query it was sent with")
        if self.body is not None and not isinstance(self.body, Mapping):
            raise ValueError("a request body is a mapping, or is absent")
        if self.credential_env is not None and not isinstance(self.credential_env, str):
            raise ValueError("a credential is named by its location, never by value")

    def record(self) -> dict:
        return {
            "method": self.method,
            "endpoint": self.endpoint,
            "endpoint_name": self.endpoint_name,
            "query": deepcopy(dict(self.query)),
            "body": deepcopy(self.body),
            "credential_env": self.credential_env,
        }


@dataclass(frozen=True)
class RequestAttempt:
    """One request attempt: what was sent, and what the provider said about it.

    `ordinal` is the attempt's position in the run and `attempt_number` counts the
    retries of that one request, so a retry is a second fact rather than a second
    entry inside one document.

    `http_status` is absent exactly when a transport error is recorded: a request
    that never reached the provider has no status, and writing zero would claim the
    provider answered.
    """

    ordinal: int
    attempt_number: int
    phase: str
    request: SubmittedRequest
    sent_at: datetime
    observed_at: datetime
    response_digest: str
    http_status: int | None = None
    transport_error: str | None = None
    observed_facts: Mapping = dataclass_field(default_factory=dict)
    waited_before_seconds: float = 0.0

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise ValueError("a request attempt is positioned in its run from 1")
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise ValueError("a request attempt counts its retries from 1")
        if not isinstance(self.phase, str) or not self.phase:
            raise ValueError("a request attempt records the phase it was sent in")
        if not isinstance(self.request, SubmittedRequest):
            raise ValueError("a request attempt records the request it sent")
        if not isinstance(self.response_digest, str) or not self.response_digest:
            raise ValueError("a request attempt records what the provider answered, digest included")
        if self.http_status is None and self.transport_error is None:
            raise ValueError("an attempt either observed a status or recorded why none arrived")
        if self.http_status is not None and (type(self.http_status) is not int or
                                             self.http_status < 0):
            raise ValueError("a provider status is a nonnegative integer")
        if self.transport_error is not None and not (
                isinstance(self.transport_error, str) and self.transport_error):
            raise ValueError("a transport failure is recorded by name")
        if not isinstance(self.observed_facts, Mapping):
            raise ValueError("the observed facts of an attempt are a mapping")
        if not isinstance(self.waited_before_seconds, (int, float)) or \
                self.waited_before_seconds < 0:
            raise ValueError("a wait is a nonnegative number of seconds")
        _instant(self.sent_at, "sent_at")
        _instant(self.observed_at, "observed_at")


@dataclass(frozen=True)
class RunEvidence:
    """Every request attempt one run issued, and the weakest claim it may record.

    `coverage_result` and `outcome` are the weakest claim an adapter may record.
    Neither may read "complete": only the declared terminal condition may do
    that, and a provider that returns no completeness signal can never satisfy
    one.
    """

    attempts: Sequence[RequestAttempt]
    adapter_id: str
    coverage_result: str = "unknown"
    outcome: str = "incomplete"

    def __post_init__(self) -> None:
        if isinstance(self.attempts, (str, bytes, Mapping)) or not isinstance(
                self.attempts, Iterable):
            raise ValueError("a run records every request attempt it made")
        attempts = tuple(self.attempts)
        if not attempts:
            raise ValueError("a run records every request attempt it made")
        if any(not isinstance(attempt, RequestAttempt) for attempt in attempts):
            raise ValueError("a run records request attempts, not anything shaped like one")
        object.__setattr__(self, "attempts", attempts)
        positions = [(attempt.ordinal, attempt.attempt_number) for attempt in attempts]
        if positions != sorted(positions) or len(set(positions)) != len(positions):
            raise ValueError("request attempts are recorded in order, and a position and a "
                             "retry number together name exactly one attempt")
        if sorted({attempt.ordinal for attempt in attempts}) != list(
                range(1, len({attempt.ordinal for attempt in attempts}) + 1)):
            raise ValueError("request ordinals are the requests' positions in the run, "
                             "from 1 with no gap")
        if not isinstance(self.adapter_id, str) or not self.adapter_id.strip():
            raise ValueError("a run records the adapter that issued its requests")
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


def _instant(value: datetime, name: str) -> datetime:
    """Accept an instant only when it is timezone-aware, and say which one failed."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value


def _recorded_at(value: datetime, precision: str, name: str) -> datetime:
    """Round one recorded instant to the precision the plan declared.

    Every instant a run records goes through this one rule: a send, an observation, a
    retrieval. Rounding one and not another would make two attempts of the same run
    incomparable for no stated reason, and the precision a plan declares is the
    precision the whole run keeps.
    """
    value = _instant(value, name).astimezone(UTC)
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


def _resolves_to(endpoint: str, template: str) -> bool:
    """True when a URL is one declared endpoint template, placeholder or not.

    A placeholder stands for exactly one path segment and never for a query, a
    fragment, or a second slash, so a template can never authorise a URL that
    reaches another host or walks out of the declared path.
    """
    if endpoint == template:
        return True
    pattern = re.sub(r"\\\{[a-z_]+\\\}", "[^/?#]+", re.escape(template))
    return re.fullmatch(pattern, endpoint) is not None


def _names_of(value: object) -> Iterator[str]:
    """Every key name inside a request body or query, at any depth."""
    if isinstance(value, Mapping):
        for name, item in value.items():
            yield str(name)
            yield from _names_of(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _names_of(item)


def validate_request_attempt(plan: ShadowPlan, request: SubmittedRequest) -> None:
    """Refuse a request the run may not send, because it could not be stored.

    This is the single definition of what may leave an adapter, and the writer calls
    it again before storing, so the two facts cannot drift apart. Five things stop an
    attempt: an endpoint name outside the plan's declared endpoint set, a URL that does
    not resolve to that declared endpoint, a body that is absent from a method that
    carries one, a body or query that cannot be encoded as the evidence it is meant to
    be, and a credential travelling inside one.
    """
    template = plan.endpoints.get(request.endpoint_name)
    if not isinstance(template, str) or not template:
        raise ValueError(
            f"{request.endpoint_name!r} is not a value in the declared endpoint set of plan "
            f"{plan.source_id!r}, which declares {sorted(plan.endpoints)}"
        )
    if "?" in request.endpoint:
        raise ValueError(
            "query parameters travel in the query, never inside the endpoint, so a stored "
            "endpoint stays comparable to a declared one"
        )
    if not _resolves_to(request.endpoint, template):
        raise ValueError(
            f"the {request.endpoint_name!r} endpoint {request.endpoint!r} resolves outside the "
            f"declared {template!r}"
        )
    if request.body is None and request.method not in BODYLESS_METHODS:
        # The same rule the stored record is checked against, stated here so that a
        # request which could never have been stored is never sent in the first place.
        raise ValueError(
            f"a {request.method} request carries a body by definition, so an absent body is not "
            "a fact this record could store"
        )
    for location, value in (("body", request.body), ("query", request.query)):
        try:
            _bytes(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"the request {location} cannot be stored as the evidence it is meant to be: {error}"
            ) from error
    if request.credential_env is not None and request.credential_env in {
            *_names_of(request.body), *_names_of(request.query)}:
        raise ValueError(
            f"the request carries {request.credential_env!r} inside its own body or query, and a "
            "credential is retained by its named location only"
        )


def _record_request_attempts(
    session, run: CollectionRun, plan: ShadowPlan, evidence: RunEvidence, now: datetime,
) -> None:
    """Store one request record and one execution record per attempt.

    They are two rows because they are two claims. The request row holds what the
    adapter sent and digests it; the execution row holds what the provider returned and
    digests that. Neither restates the other, so a provider echo can never be read as
    the request that provoked it, and a retry is a new pair rather than an edit of the
    pair before it.
    """
    for attempt in evidence.attempts:
        validate_request_attempt(plan, attempt.request)
        request = attempt.request
        sent_at = _recorded_at(attempt.sent_at, plan.retrieval_precision, "sent_at")
        body_row = CollectionRequestBody(
            collection_run_id=run.id, request_ordinal=attempt.ordinal,
            attempt_number=attempt.attempt_number, adapter_id=evidence.adapter_id,
            method=request.method, endpoint=request.endpoint,
            query_parameters=deepcopy(dict(request.query)),
            body=deepcopy(dict(request.body)) if request.body is not None else None,
            credential_env=request.credential_env,
            body_digest=content_digest(request.body), declared_caps=deepcopy(plan.caps),
            requested_fields=deepcopy(plan.requested_fields), sent_at=sent_at,
            created_at=now,
        )
        session.add(body_row)
        session.flush()
        observed_facts = deepcopy(dict(attempt.observed_facts))
        execution_digest = content_digest({
            "phase": attempt.phase, "http_status": attempt.http_status,
            "transport_error": attempt.transport_error,
            "response_digest": attempt.response_digest, "observed_facts": observed_facts,
        })
        session.add(CollectionRequestExecution(
            collection_run_id=run.id, request_body_id=body_row.id,
            request_ordinal=attempt.ordinal, attempt_number=attempt.attempt_number,
            phase=attempt.phase, http_status=attempt.http_status,
            transport_error=attempt.transport_error,
            response_digest=attempt.response_digest, execution_digest=execution_digest,
            observed_facts=observed_facts,
            observed_at=_recorded_at(attempt.observed_at, plan.retrieval_precision,
                                     "observed_at"),
            waited_before_seconds=attempt.waited_before_seconds, created_at=now,
        ))
    session.flush()


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

    `run_evidence` carries what only the adapter knows: every request attempt it
    issued, and the weakest outcome and coverage the run may record. Omitting it
    leaves today's behavior untouched.
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
    # The run's input is what was asked for and what came back. The requests this
    # adapter sent are part of it, so the digest covers the bodies it sent rather
    # than any echo of them.
    input_digest = content_digest({
        "requests": [attempt.request.record() for attempt in run_evidence.attempts]
        if run_evidence else [],
        "deliveries": [
            [delivery.posting.external_id, content_digest(delivery.posting.raw_payload),
             _recorded_at(delivery.retrieved_at, plan.retrieval_precision,
                          "retrieved_at").isoformat(),
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
    if run_evidence is not None and request_count != len(run_evidence.attempts):
        # The run's own request records say how many requests it made, so a count
        # beside them is a claim about a fact the run already states twice over.
        raise ValueError(
            f"the run claims {request_count} requests while its own evidence records "
            f"{len(run_evidence.attempts)} request attempts"
        )
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
            _record_request_attempts(session, run, plan, run_evidence, now)
        local_keys: dict[str, int] = {}
        for delivery in deliveries:
            payload = delivery.posting.raw_payload
            retrieved_at = _recorded_at(delivery.retrieved_at, plan.retrieval_precision,
                                        "retrieved_at")
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
