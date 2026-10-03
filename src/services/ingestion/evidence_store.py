"""Synthetic-only shadow evidence writer. No serving projection is imported or written.

The public entry point is deliberately not wired into the production loader. A
real source requires a reviewed G2 retention boundary before this path can be
activated; fixtures can exercise the contract against a disposable database.

An adapter may attach `RunEvidence` to a run: every request attempt it issued,
the provider's account of running each one, and the weakest outcome and coverage
the run may record. Everything else in a run is derived here, so an adapter cannot
widen what a run claims.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
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
RECORD_CAP_RULE = (
    "a plan declares at most one record cap, because a run records exactly one beside the count "
    "the source returned; a request parameter that merely travels in the body belongs in the body"
)

# A named secret location, never a value. No credential is ever part of a retained
# request, so the location is the only thing that may be stored and it has a shape a
# credential does not. Declared once because the plan boundary and the stored record
# both have to refuse the same thing the same way.
SECRET_LOCATION = re.compile(r"\A[A-Z][A-Z0-9_]*\Z")


class UnstorableRequestError(ValueError):
    """Raised when a request body cannot be retained, and so must not be sent."""


def stored_request_digest(body: Mapping) -> str:
    """Digest a request body, refusing one that could never be stored.

    Digesting is how a request row is written, so it is also how a body is proved
    storable: a value that cannot be canonically encoded as JSON cannot be
    retained. An adapter calls this before sending, because a request whose body
    cannot be stored is not sent at all; the writer calls it again while writing,
    so a run that somehow reached the store without the pre-send check still
    refuses to retain it.
    """
    if not isinstance(body, Mapping):
        raise UnstorableRequestError(
            f"a request body must be a mapping, not {type(body).__name__}"
        )
    try:
        return content_digest(dict(body))
    except (TypeError, ValueError) as error:
        raise UnstorableRequestError(
            f"a request body cannot be stored as JSON: {error}"
        ) from error


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
class RequestAttempt:
    """One request attempt: what this project issued, and what came back.

    The two halves are separate facts and are written to separate records.

    The request half is captured before the send. It is never reconstructed from a
    provider echo, a redirect, or a retry log, and an omitted parameter stays
    absent rather than arriving back as the empty string a provider echo would
    render it as. The execution half is what the provider observably returned for
    that one request.

    They travel in one value because the adapter knows both at the moment it
    sends, and they are stored apart because the echo of a submitted request is not
    the submitted request. One attempt per row means a retry, a second discovery
    input, or a second submit inside one run is its own record with its own
    ordinal, not a list entry inside a single run-level document.

    `endpoint_name` names the entry in the executed plan's `declared_endpoint_set`
    that `endpoint` was rendered from, and `path_parameters` is what renders it.
    Carrying both is what lets the writer check the endpoint against the plan
    rather than taking the adapter's word for it.

    Exactly one of `http_status` and `transport_error` is set. A transport failure
    produced no response at all, so recording a status for it would invent one,
    and recording neither would make it indistinguishable from an attempt that
    never happened.
    """

    request_ordinal: int
    attempt_number: int
    adapter_id: str
    endpoint_name: str
    endpoint: str
    method: str
    path_parameters: dict
    query_parameters: dict
    body: dict
    sent_at: datetime
    observed_at: datetime
    response_digest: str
    provider_facts: dict
    credential_env: str | None = None
    http_status: int | None = None
    transport_error: str | None = None

    def __post_init__(self) -> None:
        for name in ("request_ordinal", "attempt_number"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} counts from 1, got {value!r}")
        for name in ("adapter_id", "endpoint_name", "endpoint", "method", "response_digest"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"a request attempt must record a {name}")
        for name in ("path_parameters", "query_parameters", "body", "provider_facts"):
            if not isinstance(getattr(self, name), Mapping):
                raise ValueError(f"a request attempt needs a {name} mapping")
        for name in ("sent_at", "observed_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError(f"{name} must be a timezone-aware instant")
        if not isinstance(self.http_status, int) and self.http_status is not None:
            raise ValueError("an http_status is an integer or absent")
        if (self.http_status is None) == (self.transport_error is None):
            raise ValueError(
                "exactly one of http_status and transport_error must be set: a response "
                "carries a status and no transport failure, and a transport failure "
                "carries neither"
            )
        if self.credential_env is not None and not SECRET_LOCATION.match(self.credential_env):
            # A named secret location has the shape of an environment variable
            # name. Anything else is a credential value, and a retained request is
            # not a place to keep one.
            raise ValueError("credential_env must name a secret location, never a value")

    def note(self, **facts: object) -> None:
        """Record what one response carried, after that response was read.

        A fact is added once and never replaced. A provider cannot say two
        different things about a single response, so a second write that disagreed
        would mean the first was wrong, and that is a run failure to be surfaced
        rather than a value to overwrite in place.

        Nothing here may reconstruct the request from the response. The request
        half is already fixed, and letting a response write into it is exactly how
        an echo would stop being an echo.
        """
        for key, value in facts.items():
            if key in self.provider_facts:
                raise ValueError(f"request attempt already recorded {key!r}")
            self.provider_facts[key] = value


@dataclass(frozen=True)
class RunEvidence:
    """Run-level facts that only the adapter can supply.

    `requests` is every request attempt the run issued, numbered from one without
    gaps so a reader can walk the run in the order it happened. It is the only
    place a submitted request lives.

    `coverage_result` and `outcome` are the weakest claim an adapter may record.
    Neither may read "complete": only the declared terminal condition may do
    that, and a provider that returns no completeness signal can never satisfy
    one.
    """

    requests: tuple[RequestAttempt, ...]
    coverage_result: str = "unknown"
    outcome: str = "incomplete"

    def __post_init__(self) -> None:
        if not isinstance(self.requests, tuple) or not self.requests:
            raise ValueError("a run must record the requests it actually issued")
        for request in self.requests:
            if not isinstance(request, RequestAttempt):
                raise ValueError("run evidence carries request attempts and nothing else")
        ordinals = [request.request_ordinal for request in self.requests]
        if ordinals != list(range(1, len(ordinals) + 1)):
            # A gap or a repeat makes two requests indistinguishable in the record,
            # and a run nobody can read in order is not evidence of what it sent.
            raise ValueError(
                f"request attempts are numbered {ordinals}, which is not a run from 1 without gaps"
            )
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


def _declared_endpoint(plan: ShadowPlan, request: RequestAttempt) -> str:
    """The declared endpoint a request resolves from, or a refusal to store the run.

    The rule the request-body record exists for is that a request may only address
    an endpoint in the executed plan's declared set, so this is a re-render of the
    named template using the parameters the attempt recorded. A request naming an
    endpoint the plan does not declare, or one whose address is not what that
    template renders to, aborts the run here rather than becoming evidence that
    cannot be checked against the plan.

    Deriving it in the writer rather than trusting the adapter is the point: the
    adapter that built the URL is exactly the component whose construction of it
    would be in question.
    """
    template = plan.endpoints.get(request.endpoint_name)
    if not isinstance(template, str) or not template:
        raise ValueError(
            f"request {request.request_ordinal} addresses {request.endpoint_name!r}, which the "
            f"executed plan does not declare; declared endpoints are {sorted(plan.endpoints)}"
        )
    try:
        rendered = template.format(**dict(request.path_parameters))
    except (IndexError, KeyError) as error:
        raise ValueError(
            f"request {request.request_ordinal} cannot render the declared "
            f"{request.endpoint_name!r} endpoint {template!r} from "
            f"{sorted(request.path_parameters)}"
        ) from error
    if rendered != request.endpoint:
        raise ValueError(
            f"request {request.request_ordinal} addressed {request.endpoint!r}, which is not the "
            f"declared {request.endpoint_name!r} endpoint {template!r} rendered to {rendered!r}"
        )
    return request.endpoint


def _record_request_attempts(
    session, run: CollectionRun, plan: ShadowPlan, requests: tuple[RequestAttempt, ...], now: datetime,
) -> None:
    """Store every request attempt and the provider's account of it, as two records.

    The submitted request and the response it produced are separate rows, so a
    reader can answer "what did this project ask for" without reading provider
    output, and each attempt in a multi-request run is its own walkable row rather
    than a list entry inside one document.

    Neither row carries a `raw_observations` sibling: the handoff, the progress
    envelopes, and the terminal delivery observe no listing, and the provider's
    accounts of running a request are not retained representations of a retrieval.
    """
    for request in requests:
        endpoint = _declared_endpoint(plan, request)
        body = deepcopy(dict(request.body))
        row = CollectionRequestBody(
            collection_run_id=run.id,
            request_ordinal=request.request_ordinal,
            attempt_number=request.attempt_number,
            adapter_id=request.adapter_id,
            method=request.method,
            endpoint_name=request.endpoint_name,
            endpoint=endpoint,
            path_parameters=deepcopy(dict(request.path_parameters)),
            query_parameters=deepcopy(dict(request.query_parameters)),
            body=body,
            body_digest=stored_request_digest(body),
            credential_env=request.credential_env,
            declared_caps=deepcopy(dict(plan.caps)),
            requested_fields=deepcopy(dict(plan.requested_fields)),
            sent_at=_retrieved_at(request.sent_at, plan.retrieval_precision),
            created_at=now,
        )
        session.add(row)
        session.flush()
        session.add(CollectionRequestExecution(
            collection_run_id=run.id,
            request_body_id=row.id,
            http_status=request.http_status,
            transport_error=request.transport_error,
            response_digest=request.response_digest,
            observed_at=_retrieved_at(request.observed_at, plan.retrieval_precision),
            provider_facts=deepcopy(dict(request.provider_facts)),
            created_at=now,
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


def _integrity_failure(
    payload: dict, artifact: RawArtifact, declared_digest: str | None,
) -> tuple[str | None, list[str]]:
    """Why the retained artifact's digest is not what every claim says it is.

    Two claims can disagree with the bytes that were retained, and they are
    answered apart because they are repaired apart.

    `artifact_integrity_failed`
        The stored representation no longer hashes to the digest stored beside
        it. That says what happened to the row, and it is reachable only when the
        payload being normalized is not the object the artifact was written from:
        today, a replay, which reads the representation back.
    `declared_digest_mismatch`
        The payload does not hash to the digest the adapter declared when it
        captured it. That says what happened on the way in, and it means the
        retained record is not the record the adapter believes it captured, so
        nothing it would produce can enter the projection.

    The declared value is kept in the warnings because the recomputed one is
    already on the artifact row: an operator comparing the two is comparing the
    adapter's claim against the bytes, which is the only question worth asking.

    `declared_digest` is None only on a replay, where the artifact's declaration
    was checked when the artifact was written and no adapter speaks again.
    """
    if content_digest(payload) != artifact.content_digest:
        return "artifact_integrity_failed", []
    if declared_digest is not None and declared_digest != artifact.content_digest:
        return "declared_digest_mismatch", [f"declared_content_hash:{declared_digest}"]
    return None, []


def _normalize(
    session, observation: RawObservation, artifact: RawArtifact,
    payload: dict, plan: ShadowPlan, normalizer: Normalizer, paths: ProvenancePaths,
    version: str, attempt: int, now: datetime, processing_run_id: int,
    *, declared_digest: str | None,
) -> NormalizationResult:
    integrity_reason, integrity_warnings = _integrity_failure(payload, artifact, declared_digest)
    if integrity_reason is not None:
        outcome, reason, values = "quarantined", integrity_reason, None
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
        output_values=values, warnings=_structural_defaults(values, paths) + integrity_warnings,
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

    `run_evidence` carries what only the adapter knows: every request it issued
    with the provider's account of each one, and the weakest outcome and coverage
    the run may record.
    Omitting it records a run that issued no request and offers no account of any,
    which is the shape a source with nothing to declare would take.

    Every delivery's `content_hash` is the adapter's claim about the payload it
    captured, and the writer checks it rather than accepting it: a payload that
    does not hash to the claim it arrived with is retained and quarantined as
    `declared_digest_mismatch`, because a record that disagrees with its own
    integrity claim cannot be normalized into anything.
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
    # The run's input is what was asked for and what came back. Every request the
    # run issued is part of it, so the digest covers each request as it was
    # submitted rather than an echo of one of them. The send times are deliberately
    # excluded: they are wall clock, so including them would make two runs of the
    # same plan with the same deliveries look like different evidence.
    requests = run_evidence.requests if run_evidence else ()
    if run_evidence is not None and request_count != len(requests):
        # The run's own request counter and the rows that record those requests are
        # two statements of the same count. A run that claims five requests and can
        # show three is a run whose counter cannot be checked against its own
        # evidence, and nothing else here would catch it.
        raise ValueError(
            f"a run records {request_count} requests but supplied {len(requests)} request "
            "attempts: the counter and the request records have to be the same count"
        )
    input_digest = content_digest({
        "requests": [
            [request.request_ordinal, request.attempt_number, request.adapter_id,
             request.endpoint_name, request.endpoint, request.method,
             dict(request.query_parameters), dict(request.body)]
            for request in requests
        ],
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
            _record_request_attempts(session, run, plan, run_evidence.requests, now)
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
                       provenance_paths, normalization_version, 1, now, run.id,
                       declared_digest=delivery.posting.content_hash)
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
                       max((item.attempt_number for item in attempts), default=0) + 1, now, run.id,
                       declared_digest=None)
        session.commit()
        return run.id
