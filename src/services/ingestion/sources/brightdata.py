"""Bright Data adapter for LinkedIn-shaped job discovery.

The adapter answers one question: what did this project ask the provider for,
and what did the provider say while answering?
Everything else about a Bright Data result is either a claim about LinkedIn or a
fact the provider never stated, and none of it is recorded here as a fact.

**No collection from this source is authorized.**
Both Bright Data rows of `docs/refactor/ingestion-gate-register.md` read Not
met, and the open maintainer action on the key exposed in #423 blocks G1. Three
things make that a property of this code rather than a promise in a comment:

* the adapter never constructs an HTTP client and never reads a credential, so
  it cannot reach the network on its own;
* the source registry gives it no serving adapter, so a run cannot fetch from it;
* the evidence writer refuses any plan whose authorization revision is not
  synthetic, so a request made under this plan could not leave evidence of a
  retention right nobody granted.

A caller that injects a client is holding a credential, which is a gate-owner
decision made outside this module. The first authorized live run is a separate,
separately authorized change.

The boundary this module encodes, all of it measured in
`docs/discovery/research/bright-data-bounded-observation-470.md`:

* the immediate response is branched on its status code, never on elapsed time,
  because the handoff observed at 37.22s is not the documented one-minute
  timeout and no elapsed time predicts it;
* every progress state in the declared vocabulary is recorded, and a state
  outside it fails closed rather than being interpreted;
* every URL is built from the plan's declared endpoint templates. A URL found in
  a response, in a `Location` header, or in a cursor is never followed, and every
  request records the declared endpoint it resolved from so the writer can check
  that against the plan rather than taking the adapter's word for it;
* the request body comes from the plan and is stored as submitted. It is never
  rebuilt from `discovery_input`, whose echo rendered omitted filters as empty
  strings and therefore cannot tell an omission from an empty value, and a body
  that could not be retained is not sent at all;
* every request the run issues becomes its own pair of records, so the submit,
  each progress poll, and the download are separate attempts with their own
  ordinals rather than list entries inside one run-level document;
* the declared cap is stored beside the observed count, and a run never reports
  complete, because the provider exposes no terminal-completeness signal and the
  observed count reached its cap in every measured run.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from src.core.logger import logger
from src.services.ingestion.evidence_store import (
    RequestAttempt,
    RunEvidence,
    SECRET_LOCATION,
    ShadowDelivery,
    ShadowPlan,
    UnstorableRequestError,
    content_digest,
    declared_record_cap,
    stored_request_digest,
    write_shadow_run,
)
from src.services.ingestion.models import RawPosting
from src.services.ingestion.normalize.brightdata import (
    NORMALIZATION_VERSION,
    PROVENANCE_PATHS,
    listing_key,
    to_normalized_job,
)

ADAPTER_ID = "brightdata-linkedin-jobs-v1"
SOURCE_ID = "linkedin_via_brightdata"

# A provider identifier is used only to build a declared URL template, so it is
# constrained to the shape a provider identifier has. Anything else is refused
# before a request is built, which is what makes "never follow an undeclared URL"
# hold even if a provider returned a hostile one.
_SNAPSHOT_ID = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")

# Provider status codes that mean the provider refused the account or the
# request rather than the collection. They are recorded as a block, never retried.
_BLOCKING_STATUSES = frozenset({400, 401, 402, 403, 429})


class BrightDataBoundaryError(Exception):
    """Raised when a response falls outside the boundary the plan declares.

    It is raised instead of being interpreted, because the alternative to
    understanding a response is inventing what it said.
    """


@dataclass(frozen=True)
class BrightDataRequest:
    """One request, exactly as declared, before it is sent."""

    method: str
    url: str
    query: dict
    body: dict | None = None
    # A named secret location, never a value. The retained request names where a
    # credential comes from; no credential is ever part of this record.
    credential_env: str | None = None
    # The entry in the plan's declared_endpoint_set this request resolves from,
    # and the parameters that render it. The stored attempt carries both, so the
    # evidence writer can re-render the template and check the address rather than
    # trusting that the adapter built it from a declaration.
    endpoint_name: str = ""
    path_parameters: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    """One provider response, or the transport failure that replaced it."""

    status_code: int
    headers: Mapping[str, str]
    payload: Any
    digest: str
    transport_error: str | None = None

    @property
    def delivered(self) -> bool:
        return self.transport_error is None


@dataclass(frozen=True)
class BrightDataCollection:
    """The result of one collection attempt, with nothing inferred about coverage.

    `attempts` is every request the run issued, in order, each carrying both the
    request as it was submitted and what the provider observably returned for it.
    There is no run-level execution document: a reader who wants to know what was
    asked for reads the attempts, and a reader who wants to know what the provider
    said reads them too, through the execution record each one points at.

    The adapter identifier is not here because every request attempt already
    carries it, and a field nothing reads is a field that will drift from the one
    that is read.
    """

    attempts: tuple[RequestAttempt, ...]
    records: tuple[dict, ...]
    retrieved_at: datetime
    request_count: int
    delivery: str
    failure_category: str | None = None
    outcome: str = "incomplete"
    snapshot_id: str | None = None


@dataclass
class _Waits:
    """Every wait the adapter asked for, so a test can see the budget without paying it."""

    sleep: Callable[[float], None]
    requested: list[float] = field(default_factory=list)

    def wait(self, seconds: float) -> None:
        self.requested.append(seconds)
        self.sleep(seconds)


@dataclass
class _Attempt:
    """Accumulator for one collection attempt.

    It holds exactly the state the run will report, plus every request attempt the
    run issued, so the state machine reads as a sequence of decisions about that
    state rather than a sequence of assignments to local variables.
    """

    source: BrightDataSource
    attempts: list[RequestAttempt]
    retrieved_at: datetime
    request_count: int = 0
    waited: float = 0.0
    failure: str | None = None
    outcome: str = "incomplete"
    records: tuple[dict, ...] = ()
    delivery: str = "none"
    snapshot_id: str | None = None

    def send(self, request: BrightDataRequest) -> tuple[ProviderResponse, RequestAttempt]:
        """Issue one request and record the attempt, before the send and after it.

        The request half is captured here, before anything leaves this process,
        and it is refused outright when it cannot be retained: a request whose body
        cannot be stored is not sent.
        """
        body = deepcopy(dict(request.body or {}))
        try:
            stored_request_digest(body)
        except UnstorableRequestError as error:
            raise BrightDataBoundaryError(
                f"a request whose body cannot be stored is not sent: {error}"
            ) from error
        self.request_count += 1
        # Read before the send, because this is when the request was sent. Reading it
        # after the response arrives would record when the provider answered, which is
        # a different fact and the wrong one for a column named `sent_at`.
        sent_at = self.source._clock()
        response = self.source._send(request)
        attempt = RequestAttempt(
            request_ordinal=self.request_count,
            attempt_number=1,
            adapter_id=self.source.adapter_id,
            endpoint_name=request.endpoint_name,
            endpoint=request.url,
            method=request.method,
            path_parameters=deepcopy(dict(request.path_parameters)),
            query_parameters=deepcopy(dict(request.query)),
            body=body,
            credential_env=request.credential_env,
            sent_at=sent_at,
            http_status=None if response.transport_error else response.status_code,
            transport_error=response.transport_error,
            response_digest=response.digest,
            observed_at=self.source._clock(),
            provider_facts={},
        )
        self.attempts.append(attempt)
        return response, attempt

    def fail(self, category: str, outcome: str) -> None:
        self.failure, self.outcome = category, outcome


class BrightDataSource:
    """Executes one declared discovery request and reports what came back."""

    source = SOURCE_ID
    adapter_id = ADAPTER_ID

    def __init__(
        self,
        plan: ShadowPlan,
        *,
        client: httpx.Client,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if plan.source_id != SOURCE_ID:
            raise BrightDataBoundaryError(
                f"plan {plan.source_id!r} is not a plan this adapter may execute"
            )
        self._plan = plan
        self._client = client
        self._waits = _Waits(sleep or time.sleep)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._request = self._declared_request(plan)

    # ------------------------------------------------------------------
    # The declared request
    # ------------------------------------------------------------------

    def _declared_request(self, plan: ShadowPlan) -> BrightDataRequest:
        """Build the request from the plan, refusing any declaration that lies.

        Every check here exists because the alternative is a run whose stored
        request is not the request that was sent.
        """
        scope = plan.scope
        body, query = scope.get("request_body"), scope.get("query_parameters")
        if not isinstance(body, Mapping) or not isinstance(query, Mapping):
            raise BrightDataBoundaryError("the plan declares no request to submit")
        for name in ("submit", "progress", "snapshot"):
            if not isinstance(plan.endpoints.get(name), str) or not plan.endpoints[name]:
                raise BrightDataBoundaryError(f"the plan declares no {name} endpoint")
            if urlsplit(plan.endpoints[name]).scheme != "https":
                # The submit request carries a credential and the two follow-ups
                # address a provider-held snapshot, so none of the three may be
                # declared over a channel that does not protect it.
                raise BrightDataBoundaryError(
                    f"the {name} endpoint must be https: it carries a credential or a "
                    "provider-held reference"
                )
        for name, value in plan.caps.items():
            if body.get(name) != value:
                raise BrightDataBoundaryError(
                    f"the plan declares the cap {name}={value!r} while the request body "
                    f"carries {body.get(name)!r}"
                )
        # The selector is how the plan says which fields it asks for, so a request
        # that carries none would let the provider return fields the plan never
        # requested, which are not evidence even when they arrive.
        selector = _selector(plan.requested_fields)
        carried = [
            (location, str(declared["custom_output_fields"]))
            for location, declared in (("body", body), ("query", query))
            if "custom_output_fields" in declared
        ]
        if not carried:
            raise BrightDataBoundaryError(
                "the request carries no output field selector, so the response would not be "
                "the evidence the plan declared"
            )
        for location, declared in carried:
            if _selector(declared.split("|")) != selector:
                raise BrightDataBoundaryError(
                    f"the request {location} field selector does not name exactly the plan's "
                    "requested fields, so the response would not be the evidence the plan "
                    "declared"
                )
        for index, discovery_input in enumerate(body.get("input") or []):
            if not isinstance(discovery_input, Mapping):
                raise BrightDataBoundaryError(f"declared discovery input {index} is not a mapping")
            for name in scope.get("omitted_discovery_inputs") or ():
                if name in discovery_input:
                    raise BrightDataBoundaryError(
                        f"discovery input {index} declares {name}, which the plan lists as "
                        "omitted: an omitted filter must be absent, not submitted"
                    )
        credential_env = scope.get("credential_env")
        if credential_env is not None and not SECRET_LOCATION.match(str(credential_env)):
            raise BrightDataBoundaryError("credential_env must name a secret location")
        return BrightDataRequest(
            method="POST", url=plan.endpoints["submit"], query=deepcopy(dict(query)),
            body=deepcopy(dict(body)), credential_env=credential_env,
            endpoint_name="submit",
        )

    def _declared_get(self, name: str, snapshot_id: str | None) -> BrightDataRequest:
        """Build one follow-up GET from a declared endpoint, refusing to leave it.

        The returned request names the declared endpoint it came from and the
        parameters that render it, so the request that is sent and the request the
        evidence writer checks against the plan are one fact stated twice, and the
        writer can re-render the template rather than trust the adapter's rendering.
        """
        template = self._plan.endpoints[name]
        if not isinstance(snapshot_id, str) or not _SNAPSHOT_ID.match(snapshot_id):
            raise BrightDataBoundaryError(
                f"the provider identifier {snapshot_id!r} is not a snapshot identifier, so no "
                f"declared {name} endpoint can be built from it"
            )
        url = template.format(snapshot_id=snapshot_id)
        rendered, declared = urlsplit(url), urlsplit(template)
        if (rendered.scheme, rendered.netloc) != (declared.scheme, declared.netloc):
            raise BrightDataBoundaryError(f"the {name} endpoint resolves outside its declaration")
        return BrightDataRequest(
            method="GET", url=url, query={"format": "json"}, endpoint_name=name,
            path_parameters={"snapshot_id": snapshot_id},
        )

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send(self, request: BrightDataRequest) -> ProviderResponse:
        try:
            response = self._client.request(
                request.method, request.url, params=request.query,
                json=request.body, headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as error:
            # A transport failure is evidence too: the attempt happened and
            # produced nothing. It is recorded, and it is not retried here.
            return ProviderResponse(
                status_code=0, headers={}, payload=None,
                digest=content_digest({"transport_error": type(error).__name__}),
                transport_error=type(error).__name__,
            )
        payload = _json_or_none(response)
        return ProviderResponse(
            status_code=response.status_code, headers=dict(response.headers), payload=payload,
            digest=(
                content_digest(payload)
                if isinstance(payload, (dict, list))
                else content_digest(_unreadable_body(response))
            ),
        )

    # ------------------------------------------------------------------
    # The provider state machine
    # ------------------------------------------------------------------

    def collect(self) -> BrightDataCollection:
        """Run one declared request through the provider's state machine.

        The immediate response decides the path: 200 carries records inline, 202
        carries a snapshot to poll. Nothing here predicts which one will arrive,
        because a 202 was observed at 37.22 seconds, well inside the documented
        one-minute synchronous limit.
        """
        states, terminal, max_polls, default_wait = self._state_machine()
        attempt = _Attempt(self, attempts=[], retrieved_at=self._clock())
        submit, submitted = attempt.send(self._request)
        if not submit.delivered:
            attempt.fail("transport_error", "failed")
        elif submit.status_code in _BLOCKING_STATUSES:
            attempt.fail("page_failed", "authorization_blocked")
            submitted.note(provider_message=_message(submit.payload))
        elif submit.status_code == 200:
            self._accept_inline(attempt, submit, submitted)
        elif submit.status_code == 202:
            self._follow_handoff(
                attempt, submit, submitted, states, terminal, max_polls, default_wait,
            )
        else:
            attempt.fail("page_failed", "failed")
            submitted.note(provider_message=_message(submit.payload))
        return self._settle(attempt)

    def _accept_inline(
        self, attempt: _Attempt, submit: ProviderResponse, submitted: RequestAttempt,
    ) -> None:
        """Take the records the provider returned in its immediate response."""
        attempt.delivery = "inline"
        records, shape = _records(submit.payload)
        attempt.records = records
        submitted.note(delivery="inline", records=len(records), shape=shape)
        attempt.failure, attempt.outcome = _shape_failure(shape)

    def _follow_handoff(
        self, attempt: _Attempt, handoff: ProviderResponse, handoff_attempt: RequestAttempt,
        states: list[str], terminal: set[str], max_polls: int, default_wait: float,
    ) -> None:
        """Poll the declared progress endpoint, then read the declared snapshot.

        Every transition the provider reports is recorded, in order, including
        the ones that are not terminal. Running is not readiness, so a poll that
        reports `running` never advances the run.
        """
        attempt.delivery = "snapshot"
        attempt.snapshot_id = _snapshot_id(handoff.payload)
        announced = handoff.headers.get("retry-after") is not None
        wait = self._retry_after(handoff, default_wait)
        # `retry_after_source` says which of the two this was. Without it the row
        # cannot tell a delay the provider asked for from a delay this plan guessed,
        # and "the provider said thirty seconds" would be an invention.
        handoff_attempt.note(delivery="snapshot", snapshot_id=attempt.snapshot_id,
                             retry_after_seconds=wait,
                             retry_after_source="provider" if announced else "plan_default")
        self._wait(attempt, handoff_attempt, wait)
        for poll in range(1, max_polls + 1):
            progress, step = attempt.send(self._declared_get("progress", attempt.snapshot_id))
            if not progress.delivered:
                step.note(poll=poll)
                attempt.fail("transport_error", "failed")
                return
            if progress.status_code != 200 or not isinstance(progress.payload, Mapping):
                step.note(poll=poll)
                attempt.fail("page_failed", "failed")
                return
            status = self._record_progress(progress, poll, states, terminal, step)
            if step.provider_facts["schema_drift"]:
                # The provider reported a state the plan does not declare. The run
                # records exactly that and stops, and keeps the attempt as evidence
                # rather than losing it: reading a completeness or an emptiness
                # claim out of an unknown state would be a guess, and a guess here
                # is how a provider change becomes a coverage claim.
                attempt.fail("page_failed", "failed")
                logger.warning(
                    "ingestion.brightdata_schema_drift", source=self.source,
                    snapshot_id=attempt.snapshot_id, reported_state=status,
                    declared_states=states, poll=poll,
                )
                return
            if status in terminal:
                break
            if poll < max_polls:
                # No wait after the last permitted poll. The budget is spent, the run
                # is about to end, and a delay charged to a response that no further
                # request follows would be a response fact that never happened.
                wait = self._retry_after(progress, wait)
                self._wait(attempt, step, wait)
        else:
            # The declared poll budget ran out with no terminal state observed.
            attempt.fail("budget_exhausted", "incomplete")
            return
        if status != "ready":
            attempt.fail("page_failed", "failed")
            return
        # An absent `errors` key is silence, not zero, so it is read as absent.
        self._download(attempt, step.provider_facts.get("errors"))

    def _record_progress(
        self, progress: ProviderResponse, poll: int, states: list[str],
        terminal: set[str], attempt: RequestAttempt,
    ) -> str:
        """Retain one progress transition, flagging any state the plan does not declare."""
        state = progress.payload.get("status")
        # `records` and `errors` are stated only when the envelope carries them. A
        # provider that omits a key is asserting nothing about it, and recording a
        # null there would make its silence read as a claim of zero, which is the one
        # thing an omitted key must never become.
        attempt.note(
            poll=poll, status=state, terminal=state in terminal,
            schema_drift=state not in states,
            **{
                key: progress.payload[key] for key in ("records", "errors")
                if key in progress.payload
            },
        )
        return state

    def _download(self, attempt: _Attempt, reported_errors: Any) -> None:
        """Read the terminal snapshot, and record a partial delivery as a failure."""
        download, downloaded = attempt.send(self._declared_get("snapshot", attempt.snapshot_id))
        if not download.delivered:
            attempt.fail("transport_error", "failed")
            return
        if download.status_code != 200:
            # The status and the response digest are the whole account of this
            # response. There is no envelope here to read declared facts from.
            attempt.fail("page_failed", "failed")
            return
        records, shape = _records(download.payload)
        attempt.records = records
        downloaded.note(records=len(records), shape=shape)
        if shape != "array_of_objects" or (reported_errors or 0) > 0:
            # A partial delivery is a failed run that still carries the records
            # which did arrive. Dropping the error-bearing inputs, or presenting
            # the rest as the whole scope, are both prohibited.
            attempt.fail("page_failed", "failed")
            return
        attempt.failure, attempt.outcome = None, "incomplete"

    def _wait(self, attempt: _Attempt, response_attempt: RequestAttempt, seconds: float) -> None:
        """Pay a wait the provider asked for, against the response that asked for it.

        Attributing the wait to its own response is what keeps "this response cost
        this project thirty seconds" readable, instead of only the run's total.
        """
        self._waits.wait(seconds)
        attempt.waited += seconds
        response_attempt.note(waited_seconds=seconds)

    def _settle(self, attempt: _Attempt) -> BrightDataCollection:
        """Freeze the attempt into the collection the run is written from.

        A saturated cap is not recorded here. It is not a new fact: it is exactly
        the observed count having reached its declared cap, and the run stores both
        beside each other precisely so a reader can derive that rather than trust
        one more summary field.
        """
        cap = declared_record_cap(self._plan)
        logger.info(
            "ingestion.brightdata_attempt", source=self.source, plan_version=self._plan.version,
            delivery=attempt.delivery, snapshot_id=attempt.snapshot_id,
            # The declared cap travels beside the count so neither is readable alone:
            # a count that reached its cap says nothing about how many exist. Neither
            # is folded into a saturation verdict here, because a verdict is a third
            # number a reader could take as a coverage claim.
            declared_record_cap=cap,
            observed_record_count=len(attempt.records), requests=attempt.request_count,
            waited_seconds=attempt.waited, failure_category=attempt.failure,
        )
        return BrightDataCollection(
            attempts=tuple(attempt.attempts), records=attempt.records,
            retrieved_at=attempt.retrieved_at, request_count=attempt.request_count,
            delivery=attempt.delivery, failure_category=attempt.failure,
            outcome=attempt.outcome, snapshot_id=attempt.snapshot_id,
        )

    def _state_machine(self) -> tuple[list[str], set[str], int, float]:
        scope = self._plan.scope
        states = list(scope.get("progress_states") or ())
        terminal = set(scope.get("terminal_states") or ())
        max_polls = int(scope.get("max_progress_polls") or 0)
        default_wait = float(scope.get("default_retry_after_seconds") or 0)
        if not states or not terminal or not terminal <= set(states) or max_polls < 1:
            raise BrightDataBoundaryError("the plan declares no usable provider state machine")
        if default_wait <= 0:
            raise BrightDataBoundaryError("the plan declares no wait between progress polls")
        return states, terminal, max_polls, default_wait

    def _retry_after(self, response: ProviderResponse, default: float) -> float:
        """The provider's own retry delay, bounded and never invented locally."""
        raw = response.headers.get("retry-after")
        if raw is None:
            return float(default)
        try:
            seconds = float(raw)
        except (TypeError, ValueError) as error:
            raise BrightDataBoundaryError(
                f"the provider sent an unreadable retry-after: {raw!r}"
            ) from error
        if not 0 <= seconds <= 3600:
            raise BrightDataBoundaryError(f"the provider sent an out-of-range retry-after: {raw!r}")
        return seconds


def _selector(fields: Any) -> set[str]:
    """The requested fields as one unordered set, refusing a repeated name.

    Order carries no meaning in a pipe-separated selector, so the check is on the
    set, which is what stops a hand-edited declaration from quietly asking for a
    field the plan never requested or dropping one it did.
    """
    names = list(fields)
    if len(set(names)) != len(names):
        raise BrightDataBoundaryError("the plan requests a field more than once")
    return set(names)


def _json_or_none(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _unreadable_body(response: httpx.Response) -> dict:
    """A digestable summary of a body that is not the declared JSON shape."""
    return {"unreadable_body_digest": content_digest({"text": response.text}),
            "content_type": response.headers.get("content-type", "")}


def _records(payload: Any) -> tuple[tuple[dict, ...], str]:
    """Return the delivered records and the shape they arrived in.

    A body that is not an array of objects is not a partial result, it is an
    unrecognised shape, and the run records that rather than picking records out
    of it.
    """
    if not isinstance(payload, list):
        return (), "not_an_array"
    if any(not isinstance(record, dict) for record in payload):
        return (), "not_an_array_of_objects"
    return tuple(payload), "array_of_objects"


def _shape_failure(shape: str) -> tuple[str | None, str]:
    return ("page_failed", "failed") if shape != "array_of_objects" else (None, "incomplete")


def _snapshot_id(payload: Any) -> str:
    """The provider's snapshot identifier, which is not a source listing key."""
    value = payload.get("snapshot_id") if isinstance(payload, Mapping) else None
    if not isinstance(value, str) or not _SNAPSHOT_ID.match(value):
        raise BrightDataBoundaryError(
            f"the 202 handoff carried no usable snapshot identifier: {value!r}"
        )
    return value


def _message(payload: Any) -> str | None:
    if isinstance(payload, Mapping) and isinstance(payload.get("message"), str):
        return payload["message"]
    return None


def deliveries(collection: BrightDataCollection) -> list[ShadowDelivery]:
    """The records a collection delivered, as evidence deliveries.

    The provider supplies a snapshot identifier for the whole delivery and no
    per-record delivery identifier, so none is invented here: the observation key
    stays the blueprint's run-local tuple, and a re-read of the same snapshot is
    a new retrieval rather than a replayed one.
    """
    return [
        ShadowDelivery(
            RawPosting(
                source=SOURCE_ID, external_id=listing_key(record),
                source_url=record.get("url") if isinstance(record.get("url"), str) else None,
                raw_payload=record, content_hash=content_digest(record),
            ),
            retrieved_at=collection.retrieved_at,
        )
        for record in collection.records
    ]


def shadow_run_evidence(collection: BrightDataCollection) -> RunEvidence:
    """Package one collection as the run-level evidence the writer stores.

    Coverage is always `unknown` and completion is never claimed: this plan
    declares that the provider exposes no completeness signal, so reporting even
    partial coverage would be a claim the provider never supported.
    """
    return RunEvidence(
        requests=collection.attempts,
        coverage_result="unknown",
        outcome=collection.outcome,
    )


def record_shadow_collection(
    plan: ShadowPlan, collection: BrightDataCollection, *,
    run_key: str, retention_until: datetime,
) -> int:
    """Write one collection attempt and its evidence, without touching serving.

    The terminal condition is never attested: this plan declares that the
    provider exposes no completeness signal, so no run of it may read complete.
    """
    return write_shadow_run(
        plan, deliveries(collection), run_key=run_key,
        normalizer=to_normalized_job, provenance_paths=PROVENANCE_PATHS,
        normalization_version=NORMALIZATION_VERSION, retention_until=retention_until,
        terminal_condition_met=False, request_count=collection.request_count,
        failure_category=collection.failure_category,
        run_evidence=shadow_run_evidence(collection),
    )
