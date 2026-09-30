"""Source resolution by declared source id.

A source id names a namespace, a normalizer, its field lineage, and, when the
source is allowed to serve, an adapter. Nothing is imported at a call site to
decide which of those applies, so adding a source is a declaration plus a
binding rather than an edit to the loader.

The registry is deliberately narrower than the plan registry. A source may be
declared for evidence and still have no serving adapter, which is the state
Bright Data is in: its plan is declarable and reviewable, and it may not be
collected from at all. `resolve_source` refuses such a source rather than
returning something the loader could fetch with.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.services.ingestion.evidence_store import Normalizer, ProvenancePaths
from src.services.ingestion.normalize import brightdata as brightdata_normalizer
from src.services.ingestion.normalize import vietnamworks as vietnamworks_normalizer
from src.services.ingestion.sources.base import JobSource
from src.services.ingestion.sources.vietnamworks import VietnamWorksSource

# The source a run collects from when nothing is declared. It is the only source
# whose G1 row reads met, so an undeclared run keeps resolving exactly as it did
# before source resolution existed.
DEFAULT_SERVING_SOURCE = "vietnamworks"


class UnknownSourceError(Exception):
    """Raised when a declared source id resolves to no source this build may use."""


@dataclass(frozen=True)
class SourceBinding:
    """Everything one declared source id resolves to."""

    source_id: str
    normalize: Normalizer
    provenance_paths: ProvenancePaths
    normalization_version: str
    # None means the source is declared for evidence only and has no serving
    # adapter, which is a gate state rather than a missing implementation.
    new_source: Callable[[], JobSource] | None = None

    def build_source(self) -> JobSource:
        if self.new_source is None:
            raise UnknownSourceError(
                f"source {self.source_id!r} has no serving adapter: it is declared for "
                "evidence only, and no gate authorizes collection from it"
            )
        return self.new_source()


_BINDINGS: dict[str, SourceBinding] = {
    vietnamworks_normalizer.SOURCE_ID: SourceBinding(
        source_id=vietnamworks_normalizer.SOURCE_ID,
        normalize=vietnamworks_normalizer.to_normalized_job,
        provenance_paths=vietnamworks_normalizer.PROVENANCE_PATHS,
        normalization_version=vietnamworks_normalizer.NORMALIZATION_VERSION,
        new_source=VietnamWorksSource,
    ),
    brightdata_normalizer.SOURCE_ID: SourceBinding(
        source_id=brightdata_normalizer.SOURCE_ID,
        normalize=brightdata_normalizer.to_normalized_job,
        provenance_paths=brightdata_normalizer.PROVENANCE_PATHS,
        normalization_version=brightdata_normalizer.NORMALIZATION_VERSION,
    ),
}


def declared_source_ids() -> tuple[str, ...]:
    """Return every source id this build knows how to resolve."""
    return tuple(sorted(_BINDINGS))


def resolve_binding(source_id: str) -> SourceBinding:
    """Return the binding for one source id: rule, lineage, version, and adapter if any.

    Callers that need only the normalizer should use `resolve_normalizer`, and callers
    that need a runnable adapter should use `resolve_source`, which fails closed when
    the source has none.
    """
    if source_id not in _BINDINGS:
        raise UnknownSourceError(
            f"unknown source {source_id!r}; known sources are {declared_source_ids()}"
        )
    return _BINDINGS[source_id]


def resolve_source(declared: str | None = None) -> JobSource:
    """Build the source a run collects from.

    `None` keeps the historical behaviour: the one source whose authorization
    gate reads met. Naming a source whose gate does not read met fails here
    rather than at the first request.
    """
    return resolve_binding(declared or DEFAULT_SERVING_SOURCE).build_source()


def resolve_normalizer(source_id: str) -> Normalizer:
    """Return the normalizer for a source id, so the loader never imports one."""
    return resolve_binding(source_id).normalize
