"""Vendor-neutral observations for streamed agent responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import perf_counter
from typing import Callable, Literal, Protocol

StreamOutcome = Literal["success", "error", "cancelled"]


class StreamObservation(Protocol):
    """Receive lifecycle events for one streamed response.

    ``trace`` is an opaque adapter-owned handle.
    Application code never creates, inspects, or depends on it.
    """

    def attach_trace(self, trace: object) -> None:
        """Associate the observation with the active request trace."""

    def mark_user_visible(self) -> None:
        """Record the first user-visible response token."""

    def complete(self, outcome: StreamOutcome) -> None:
        """Record the terminal stream outcome."""


StreamObservationFactory = Callable[[], StreamObservation]


class NoopStreamObservation:
    """Keep streaming behavior independent of whether tracing is configured."""

    def attach_trace(self, trace: object) -> None:
        del trace

    def mark_user_visible(self) -> None:
        pass

    def complete(self, outcome: StreamOutcome) -> None:
        del outcome


def create_noop_stream_observation() -> StreamObservation:
    """Create the default observation used outside assembled serving."""
    return NoopStreamObservation()


_request_sequence_lock = Lock()
_request_sequence = 0


@dataclass
class StreamLatency:
    """Server-side timings for one streamed agent request, always in milliseconds."""

    started_at: float = field(default_factory=perf_counter)
    cold_start: Literal["process-first-agent-request", "warm"] = field(init=False)
    user_visible_ttft_ms: int | None = None
    completion_ms: int | None = None
    outcome: StreamOutcome | None = None

    def __post_init__(self) -> None:
        global _request_sequence
        with _request_sequence_lock:
            _request_sequence += 1
            self.cold_start = (
                "process-first-agent-request" if _request_sequence == 1 else "warm"
            )

    def mark_user_visible(self) -> None:
        if self.user_visible_ttft_ms is None:
            self.user_visible_ttft_ms = self._elapsed_ms()

    def complete(self, outcome: StreamOutcome) -> None:
        if self.completion_ms is None:
            self.completion_ms = self._elapsed_ms()
        self.outcome = outcome

    def _elapsed_ms(self) -> int:
        return round((perf_counter() - self.started_at) * 1000)
