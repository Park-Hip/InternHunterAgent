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
  a response, in a `Location` header, or in a cursor is never followed;
* the request body comes from the plan and is stored as submitted. It is never
  rebuilt from `discovery_input`, whose echo rendered omitted filters as empty
  strings and therefore cannot tell an omission from an empty value;
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
    SECRET_LOCATION,
    RequestAttempt,
    RunEvidence,
    ShadowDelivery,
    ShadowPlan,
    SubmittedRequest,
    content_digest,
    declared_record_cap,
    validate_request_attempt,
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
# The shape of a named secret location is the evidence writer's rule, not this
# adapter's, so that the record it stores and the request it sends cannot disagree
# about what a credential location looks like.

# Provider status codes that mean the provider refused the account or the
# request rather than the collection. They are recorded as a block, never retried.
_BLOCKING_STATUSES = frozenset({400, 401, 402, 403, 429})

# The keys in an execution record that are this project's reading rather than the
# provider's words. Every other key the adapter writes is something the provider
# stated, and this is the whole list of exceptions, so a reader never has to guess
# which is which and a sixth exception cannot be added without appearing here. The
# blueprint names the same set.
PROJECT_READING_FACTS = frozenset({
    "delivery", "delivered_records", "shape", "schema_drift", "terminal", "poll",
})


class BrightDataBoundaryError(Exception):
    """Raised when a response falls outside the boundary the plan declares.

    It is raised instead of being interpreted, because the alternative to
    understanding a response is inventing what it said.
    """


@dataclass(frozen=True)
class ProviderResponse:
    """One provider response, or the transport failure that replaced it."""

    # Absent when nothing came back. A provider answers with an HTTP status, so a
    # stored zero would be a status no provider can return.
    status_code: int | None
    headers: Mapping[str, str]
    payload: Any
    digest: str
    transport_error: str | None = None

    @property
    def delivered(self) -> bool:
        return self.transport_error is None


@dataclass(frozen=True)
class BrightDataCollection:
    """The result of one collection attempt, with nothing inferred about coverage."""

    records: tuple[dict, ...]
    attempts: tuple[RequestAttempt, ...]
    retrieved_at: datetime
    delivery: str
    failure_category: str | None = None
    outcome: str = "incomplete"
    snapshot_id: str | None = None

    @property
    def request_count(self) -> int:
        """The requests this collection made, counted from the records it keeps."""
        return len(self.attempts)

    @property
    def waited_seconds(self) -> float:
        """The total wait, summed from the per-attempt waits that were recorded."""
        return sum(attempt.waited_before_seconds for attempt in self.attempts)


@dataclass
class _Send:
    """One request in flight, and every fact learned from its answer.

    The record is built before the request leaves, and its facts are filled in as the
    adapter learns them, because a provider's answer cannot be known before the
    question is asked and a question that cannot be recorded must not be asked.
    """

    ordinal: int
    phase: str
    request: SubmittedRequest
    sent_at: datetime
    response: ProviderResponse
    observed_at: datetime
    waited_before: float = 0.0
    facts: dict = field(default_factory=dict)


@dataclass
class _Attempt:
    """Accumulator for one collection attempt.

    It holds exactly the state the run will report, so the state machine reads
    as a sequence of decisions about that state rather than a sequence of
    assignments to local variables.
    """

    source: BrightDataSource
    retrieved_at: datetime
    failure: str | None = None
    outcome: str = "incomplete"
    records: tuple[dict, ...] = ()
    delivery: str = "none"
    snapshot_id: str | None = None
    sends: list[_Send] = field(default_factory=list)

    @property
    def request_count(self) -> int:
        """The requests made so far, counted from the sends that were recorded."""
        return len(self.sends)

    @property
    def waited_seconds(self) -> float:
        return sum(send.waited_before for send in self.sends)

    def send(
        self, request: SubmittedRequest, *, phase: str, waited_before: float = 0.0,
    ) -> _Send:
        """Refuse to send a request the run could not record, then send it.

        The record is validated here rather than after the response, so an endpoint
        the plan never declared or a body the run could not store stops the attempt
        before it costs a request.
        """
        self.source._require_storable(request)
        # Read in order, around the send, so sent_at can never be recorded after the
        # answer it precedes.
        sent_at = self.source._clock()
        response = self.source._send(request)
        observed_at = self.source._clock()
        send = _Send(
            ordinal=len(self.sends) + 1, phase=phase, request=request,
            sent_at=sent_at, response=response, observed_at=observed_at,
            waited_before=waited_before,
        )
        self.sends.append(send)
        return send

    def record(self, send: _Send, **facts: Any) -> dict:
        """Retain what this project's own reading of the answer was."""
        send.facts.update(facts)
        return send.facts

    def reading(self, send: _Send, **facts: Any) -> dict:
        """Retain something this project concluded rather than something told.

        The key has to be declared in `PROJECT_READING_FACTS` first, because the
        record's namespace is only useful if a reader can tell which half of it the
        provider spoke. Without this, a new conclusion would read as a provider
        statement and nothing would say so.
        """
        unnamed = sorted(set(facts) - PROJECT_READING_FACTS)
        if unnamed:
            raise BrightDataBoundaryError(
                f"{unnamed} are this project's own reading, and are not declared as such in "
                "PROJECT_READING_FACTS"
            )
        return self.record(send, **facts)

    def fail(self, category: str | None, outcome: str) -> None:
        """Record how the run ended. No category is the successful case: the
        provider answered in the declared shape and nothing else went wrong."""
        self.failure, self.outcome = category, outcome


class BrightDataSource:
    """Executes one declared discovery request and reports what came back."""

    source = SOURCE_ID

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
        self._sleep = sleep or time.sleep
        self._clock = clock or (lambda: datetime.now(UTC))
        self._request = self._declared_request(plan)

    # ------------------------------------------------------------------
    # The declared request
    # ------------------------------------------------------------------

    def _declared_request(self, plan: ShadowPlan) -> SubmittedRequest:
        """Build the request from the plan, refusing any declaration that lies.

        Every check here exists because the alternative is a run whose stored
        request is not the request that was sent. The request is built as the
        evidence contract's own type, so what is sent and what is recorded are one
        value and not two that can drift.
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
        return SubmittedRequest(
            method="POST", endpoint=plan.endpoints["submit"], endpoint_name="submit",
            query=deepcopy(dict(query)), body=deepcopy(dict(body)),
            credential_env=credential_env,
        )

    def _declared_url(self, name: str, snapshot_id: str | None) -> str:
        """Render one declared endpoint, and refuse anything that leaves it."""
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
        return url

    def _require_storable(self, request: SubmittedRequest) -> None:
        """Refuse a request the run could not record as evidence.

        The rule itself lives in the evidence writer, because it is the writer that
        decides what may be stored; this is the adapter refusing to send anything the
        writer would later have to reject, so no request is ever spent on evidence
        that could not have been written.
        """
        try:
            validate_request_attempt(self._plan, request)
        except ValueError as error:
            raise BrightDataBoundaryError(str(error)) from error

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send(self, request: SubmittedRequest) -> ProviderResponse:
        try:
            response = self._client.request(
                request.method, request.endpoint, params=request.query,
                json=request.body, headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as error:
            # A transport failure is evidence too: the attempt happened and
            # produced nothing. It is recorded, and it is not retried here. There is
            # no status, because nothing answered.
            return ProviderResponse(
                status_code=None, headers={}, payload=None,
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
        attempt = _Attempt(self, retrieved_at=self._clock())
        send = attempt.send(self._request, phase="submit")
        submit = send.response
        if not submit.delivered:
            attempt.fail("transport_error", "failed")
        elif submit.status_code in _BLOCKING_STATUSES:
            attempt.fail("page_failed", "authorization_blocked")
            attempt.record(
                send, **_stated(submit.payload, "message", as_provider_message=True)
            )
        elif submit.status_code == 200:
            self._accept_inline(attempt, send)
        elif submit.status_code == 202:
            self._follow_handoff(
                attempt, send, states, terminal, max_polls, default_wait,
            )
        else:
            attempt.fail("page_failed", "failed")
            attempt.record(
                send, **_stated(submit.payload, "message", as_provider_message=True)
            )
        return self._settle(attempt)

    def _accept_inline(self, attempt: _Attempt, send: _Send) -> None:
        """Take the records the provider returned in its immediate response."""
        attempt.delivery = "inline"
        records, shape = _records(send.response.payload)
        attempt.records = records
        # `delivered_records` and `shape` are this project's count and classification
        # of what arrived, not a number the provider stated.
        attempt.reading(send, delivery="inline", delivered_records=len(records),
                        shape=shape)
        attempt.fail(*_shape_failure(shape))

    def _follow_handoff(
        self, attempt: _Attempt, handoff: _Send, states: list[str],
        terminal: set[str], max_polls: int, default_wait: float,
    ) -> None:
        """Poll the declared progress endpoint, then read the declared snapshot.

        Every transition the provider reports is recorded, in order, including
        the ones that are not terminal. Running is not readiness, so a poll that
        reports `running` never advances the run.
        """
        attempt.delivery = "snapshot"
        attempt.snapshot_id = _snapshot_id(handoff.response.payload)
        wait = self._retry_after(handoff.response, default_wait)
        # Only a delay the provider announced is recorded as one. The plan's default
        # is this project's own choice, and recording it as the provider's answer
        # would put a decision in the provider's mouth.
        announced = handoff.response.headers.get("retry-after")
        attempt.reading(handoff, delivery="snapshot")
        attempt.record(
            handoff, snapshot_id=attempt.snapshot_id,
            **_stated(handoff.response.payload, "message", as_provider_message=True),
            **({"retry_after_seconds": wait} if announced is not None else {}),
        )
        self._wait(attempt, wait)
        for poll in range(1, max_polls + 1):
            progress = attempt.send(
                SubmittedRequest(
                    method="GET",
                    endpoint=self._declared_url("progress", attempt.snapshot_id),
                    endpoint_name="progress", query={"format": "json"}, body=None,
                ),
                phase="progress", waited_before=wait,
            )
            if not progress.response.delivered:
                attempt.reading(progress, poll=poll)
                attempt.fail("transport_error", "failed")
                return
            if (progress.response.status_code != 200
                    or not isinstance(progress.response.payload, Mapping)):
                attempt.reading(progress, poll=poll)
                attempt.fail("page_failed", "failed")
                return
            transition = self._record_progress(attempt, progress, poll, states, terminal)
            if transition.get("schema_drift"):
                # The provider reported a state the plan does not declare. The run
                # records exactly that and stops, and keeps the attempt as evidence
                # rather than losing it: reading a completeness or an emptiness
                # claim out of an unknown state would be a guess, and a guess here
                # is how a provider change becomes a coverage claim.
                attempt.fail("page_failed", "failed")
                logger.warning(
                    "ingestion.brightdata_schema_drift", source=self.source,
                    snapshot_id=attempt.snapshot_id, reported_state=transition["status"],
                    declared_states=states, poll=poll,
                )
                return
            if transition["status"] in terminal:
                break
            if poll == max_polls:
                # The budget is spent. Waiting now would delay the end of the run for
                # a request that will never be made, and a wait no request follows is
                # not a fact any record could hold.
                attempt.fail("budget_exhausted", "incomplete")
                return
            wait = self._retry_after(progress.response, wait)
            # The delay the provider announced belongs to the response that
            # announced it, and the wait it causes belongs to the request that
            # follows, so neither answer is recorded twice.
            if progress.response.headers.get("retry-after") is not None:
                attempt.record(progress, retry_after_seconds=wait)
            self._wait(attempt, wait)
        else:
            # The declared poll budget ran out with no terminal state observed.
            attempt.fail("budget_exhausted", "incomplete")
            return
        if transition.get("schema_drift"):
            # The last poll was a state the plan does not declare, which the poll
            # itself already failed on.
            return
        if transition["status"] != "ready":
            attempt.fail("page_failed", "failed")
            return
        self._download(attempt, transition)

    def _record_progress(
        self, attempt: _Attempt, send: _Send, poll: int,
        states: list[str], terminal: set[str],
    ) -> dict:
        """Retain one progress transition, flagging any state the plan does not declare."""
        progress = send.response
        state = progress.payload.get("status")
        entry = attempt.reading(send, poll=poll)
        entry.update(
            # Only what the provider actually stated. A key it omitted is absent from
            # the record, because a stored null would read as the provider asserting
            # one, which is a different statement from saying nothing at all.
            **_stated(progress.payload, "status", "records", "errors", "snapshot_id",
                      "dataset_id", "collection_duration", "avg_duration_per_input",
                      "error_message"),
        )
        if state is None:
            # An envelope with no state names no transition, so there is nothing to
            # interpret and the attempt is recorded exactly as it stands.
            attempt.reading(send, schema_drift=True)
            return entry
        attempt.reading(send, terminal=state in terminal, schema_drift=state not in states)
        return entry

    def _download(self, attempt: _Attempt, transition: Mapping) -> None:
        """Read the terminal snapshot, and record a partial delivery as a failure."""
        download = attempt.send(
            SubmittedRequest(
                method="GET",
                endpoint=self._declared_url("snapshot", attempt.snapshot_id),
                endpoint_name="snapshot", query={"format": "json"}, body=None,
            ),
            phase="download",
        )
        response = download.response
        if not response.delivered:
            attempt.fail("transport_error", "failed")
            return
        if response.status_code != 200:
            attempt.fail("page_failed", "failed")
            return
        records, shape = _records(response.payload)
        attempt.records = records
        attempt.reading(download, delivered_records=len(records), shape=shape)
        if shape != "array_of_objects" or (transition.get("errors") or 0) > 0:
            # A partial delivery is a failed run that still carries the records
            # which did arrive. Dropping the error-bearing inputs, or presenting
            # the rest as the whole scope, are both prohibited.
            attempt.fail("page_failed", "failed")
            return
        attempt.fail(*_shape_failure(shape))

    def _wait(self, attempt: _Attempt, seconds: float) -> None:
        self._sleep(seconds)

    def _settle(self, attempt: _Attempt) -> BrightDataCollection:
        """Freeze the attempt into the collection the run is written from.

        Each send becomes one immutable request attempt, so a retry, a second poll, or
        a repeated submit is its own record rather than another entry inside one
        document. The run's execution trace is then read one request at a time, and
        nothing is ever merged into a record that already means something else.

        Saturation is deliberately not recorded here. The declared cap and the
        observed count are two columns on the run, and a count that reached its cap
        cannot separate an exhausted scope from a truncated one, so a flag copied
        from the adapter would only restate that comparison.
        """
        logger.info(
            "ingestion.brightdata_attempt", source=self.source, plan_version=self._plan.version,
            delivery=attempt.delivery, snapshot_id=attempt.snapshot_id,
            # The declared cap travels beside the count so neither is readable alone:
            # a count that reached its cap says nothing about how many exist.
            declared_record_cap=declared_record_cap(self._plan),
            observed_record_count=len(attempt.records), requests=attempt.request_count,
            # Summed from the waits recorded on the attempts, so the log and the
            # stored evidence state the same number.
            waited_seconds=attempt.waited_seconds, failure_category=attempt.failure,
        )
        return BrightDataCollection(
            records=attempt.records,
            attempts=tuple(_attempt_record(send) for send in attempt.sends),
            retrieved_at=attempt.retrieved_at, delivery=attempt.delivery,
            failure_category=attempt.failure, outcome=attempt.outcome,
            snapshot_id=attempt.snapshot_id,
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


def _stated(payload: Any, *names: str, as_provider_message: bool = False) -> dict:
    """The named keys a provider body actually carries, and nothing else.

    A key the provider omitted stays omitted in the record.
    Storing it as a null would claim the provider asserted one, and "the provider said
    nothing" and "the provider said null" are different statements, so a record that
    cannot tell them apart cannot be read as either.
    """
    if not isinstance(payload, Mapping):
        return {}
    return {name: payload[name] for name in names
            if name in payload and (not as_provider_message
                                    or isinstance(payload[name], str))}


def _attempt_record(send: _Send) -> RequestAttempt:
    """Freeze one sent request into the attempt the run records.

    This adapter never retries: each poll is the next request, not a second try at
    the first one, so every attempt number is 1. A provider that does retry states
    the retry in its own attempt number, and the key `(ordinal, attempt)` keeps the
    two facts apart.
    """
    response = send.response
    return RequestAttempt(
        ordinal=send.ordinal, attempt_number=1, phase=send.phase, request=send.request,
        sent_at=send.sent_at, observed_at=send.observed_at, response_digest=response.digest,
        http_status=response.status_code,
        transport_error=response.transport_error,
        observed_facts=deepcopy(send.facts),
        waited_before_seconds=send.waited_before,
    )


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
        attempts=collection.attempts,
        adapter_id=ADAPTER_ID,
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
