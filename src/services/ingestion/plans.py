"""Collection plans are configuration, not Python.

`config/ingestion.yaml` owns what a run declares: the scope, the caps, the
requested field map, the completion rule, the endpoints, the retrieval
precision, and the authorization revision.
This module turns one declared plan into the `ShadowPlan` the evidence writer
stores, and it is the only place a plan is assembled.

Two rules make the declaration trustworthy.

* **A plan cannot drift from what an adapter reads.**
  A string of the form `@path.to.key` is resolved from the same configuration
  document, so a plan that says `max_jobs: "@max_jobs"` names the very value the
  adapter will use.
  A reference that does not resolve is a configuration error, never a default
  and never an empty value.
* **A plan version is the digest of everything the plan declares.**
  The version is the content digest of the declared scope, caps, requested
  fields, completion rule, endpoints, retrieval precision, and authorization
  revision, so editing any declared fact produces a new immutable plan row
  instead of mutating an existing one.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from src.core.config import settings
from src.services.ingestion.evidence_store import RECORD_CAP_RULE, ShadowPlan, content_digest

# The closed key set of one plan entry. An unknown key is a configuration error
# rather than a silently ignored typo, because a typo in a declaration is a
# declaration that says less than its author believes.
PLAN_KEYS = frozenset({
    "version_prefix",
    "authorization_revision",
    "retrieval_precision",
    "completion_rule",
    "declared_scope",
    "declared_caps",
    "declared_endpoints",
    "requested_fields",
})
REQUIRED_PLAN_KEYS = PLAN_KEYS - {"version_prefix"}
RETRIEVAL_PRECISIONS = frozenset({"second", "millisecond", "microsecond"})


class PlanConfigurationError(Exception):
    """Raised when a declared plan cannot be built. Never a default, never a guess."""


def declared_sources(config: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    """Return the source ids that `config/ingestion.yaml` declares a plan for."""
    return tuple(_plans(config))


def build_shadow_plan(
    source_id: str, *, config: Mapping[str, Any] | None = None
) -> ShadowPlan:
    """Build the declared `ShadowPlan` for one source id, without sending anything.

    Passing `config` exists so a caller can build a plan from a proposed
    document instead of the loaded one; it is how a candidate plan is reviewed
    before it becomes the loaded one.
    """
    document = _document(config)
    declared = _declared_plan(document, source_id)
    facts = {
        "scope": declared["declared_scope"],
        "caps": declared["declared_caps"],
        "requested_fields": declared["requested_fields"],
        "completion_rule": declared["completion_rule"],
        "endpoints": declared["declared_endpoints"],
        "retrieval_precision": declared["retrieval_precision"],
        "authorization_revision": declared["authorization_revision"],
    }
    prefix = declared.get("version_prefix", "")
    if not isinstance(prefix, str):
        raise PlanConfigurationError(f"plan {source_id!r} has a non-string version_prefix")
    return ShadowPlan(
        source_id=source_id,
        version=prefix + content_digest(facts)[:16],
        scope=deepcopy(facts["scope"]),
        caps=deepcopy(facts["caps"]),
        requested_fields=deepcopy(facts["requested_fields"]),
        completion_rule=facts["completion_rule"],
        endpoints=deepcopy(facts["endpoints"]),
        retrieval_precision=facts["retrieval_precision"],
        authorization_revision=facts["authorization_revision"],
    )


def _document(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return settings.ingestion_yaml if config is None else config


def _plans(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    plans = _document(config).get("plans")
    if not isinstance(plans, Mapping):
        raise PlanConfigurationError("configuration declares no plans: section")
    return plans


def _declared_plan(document: Mapping[str, Any], source_id: str) -> Mapping[str, Any]:
    plans = _plans(document)
    if source_id not in plans:
        raise PlanConfigurationError(
            f"no collection plan is declared for source {source_id!r}; "
            f"declared sources are {sorted(plans)}"
        )
    plan = plans[source_id]
    if not isinstance(plan, Mapping):
        raise PlanConfigurationError(f"plan {source_id!r} is not a mapping")
    unknown = sorted(set(plan) - PLAN_KEYS)
    if unknown:
        raise PlanConfigurationError(f"plan {source_id!r} has undeclared keys: {unknown}")
    missing = sorted(REQUIRED_PLAN_KEYS - set(plan))
    if missing:
        raise PlanConfigurationError(f"plan {source_id!r} is missing keys: {missing}")
    if not isinstance(plan["authorization_revision"], str) or not plan["authorization_revision"].strip():
        raise PlanConfigurationError(f"plan {source_id!r} needs a nonempty authorization_revision")
    if plan["retrieval_precision"] not in RETRIEVAL_PRECISIONS:
        raise PlanConfigurationError(
            f"plan {source_id!r} declares unsupported retrieval precision "
            f"{plan['retrieval_precision']!r}; expected one of {sorted(RETRIEVAL_PRECISIONS)}"
        )
    if not isinstance(plan["completion_rule"], str) or not plan["completion_rule"].strip():
        raise PlanConfigurationError(f"plan {source_id!r} needs a nonempty completion_rule")
    for key in ("declared_scope", "declared_caps", "declared_endpoints", "requested_fields"):
        if not isinstance(plan[key], Mapping):
            raise PlanConfigurationError(f"plan {source_id!r} key {key!r} must be a mapping")
    if len(plan["declared_caps"]) > 1:
        raise PlanConfigurationError(
            f"plan {source_id!r} declares {sorted(plan['declared_caps'])}: {RECORD_CAP_RULE}"
        )
    for key in ("declared_scope", "declared_endpoints", "requested_fields"):
        if not plan[key]:
            raise PlanConfigurationError(f"plan {source_id!r} key {key!r} must not be empty")
    return {key: _resolve(value, document, f"plans.{source_id}.{key}")
            for key, value in plan.items()}


def _resolve(value: Any, document: Mapping[str, Any], path: str) -> Any:
    """Resolve every `@path.to.key` reference in one declared value.

    Containers are rebuilt rather than shared, so a plan can never alias the
    live configuration value it points at.
    """
    if isinstance(value, str) and value.startswith("@"):
        return deepcopy(_lookup(document, value[1:], path))
    if isinstance(value, Mapping):
        return {key: _resolve(item, document, f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, document, f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def _lookup(document: Mapping[str, Any], reference: str, path: str) -> Any:
    current: Any = document
    for part in reference.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise PlanConfigurationError(
                f"{path} references @{reference}, which does not resolve in the configuration"
            )
        current = current[part]
    return current
