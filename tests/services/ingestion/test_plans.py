"""A collection plan is configuration, and the plan factory proves it.

These tests read the loaded `config/ingestion.yaml` rather than a local copy, so a plan
that drifts from the values an adapter actually uses fails here instead of in a run.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from src.core.config import settings
from src.services.ingestion.evidence_store import ShadowPlan, content_digest
from src.services.ingestion.plans import (
    PlanConfigurationError,
    build_shadow_plan,
    declared_sources,
)
from src.services.ingestion.source_registry import declared_source_ids
from src.services.ingestion.sources.brightdata import SOURCE_ID as BRIGHTDATA_SOURCE


@pytest.fixture
def document() -> dict:
    return deepcopy(settings.ingestion_yaml)


def test_every_declared_plan_builds(document):
    assert declared_sources() == ("vietnamworks", BRIGHTDATA_SOURCE)
    for source_id in declared_sources():
        plan = build_shadow_plan(source_id)
        assert isinstance(plan, ShadowPlan)
        assert plan.source_id == source_id
        assert plan.version and plan.completion_rule
        assert plan.retrieval_precision in ("second", "millisecond", "microsecond")
        assert plan.requested_fields and plan.endpoints


def test_the_registry_and_the_configuration_agree():
    """A source with a rule but no plan, or a plan with no rule, is a configuration bug."""
    assert set(declared_source_ids()) == set(declared_sources())


def test_vietnamworks_plan_reads_the_operational_configuration(document):
    plan = build_shadow_plan("vietnamworks")

    assert plan.scope == {
        "queries": document["queries"],
        "pages_per_query": document["api"]["pages_per_query"],
        "hits_per_page": document["api"]["hits_per_page"],
        "job_function": document["job_function"],
    }
    assert plan.caps == {"max_jobs": document["max_jobs"]}
    assert plan.endpoints == {"search": document["api"]["url"]}
    assert plan.authorization_revision.startswith("synthetic:")
    assert plan.requested_fields["jobId"] == "source listing key"
    # The scope is a copy, never an alias of the live configuration value.
    plan.scope["queries"].append("a query that was never configured")
    assert "a query that was never configured" not in settings.ingestion_yaml["queries"]


def test_brightdata_plan_declares_a_request_with_no_credential(document):
    plan = build_shadow_plan(BRIGHTDATA_SOURCE)
    body = plan.scope["request_body"]

    assert plan.authorization_revision == "synthetic:recorded-provider-responses"
    assert plan.caps == {"limit_per_input": 10}
    assert body["limit_per_input"] == 10
    assert set(body["custom_output_fields"].split("|")) == set(plan.requested_fields)
    assert plan.scope["credential_env"] == "BRIGHTDATA_API_KEY"
    assert "Authorization" not in str(plan.scope)
    # An omitted filter stays absent, which is the only way the request can show it.
    omitted = set(plan.scope["omitted_discovery_inputs"])
    assert omitted and not omitted & set(body["input"][0])
    # The declared completion rule says out loud that no run may read complete.
    assert "no run" in plan.completion_rule and "unsatisfiable" in plan.completion_rule


def test_the_plan_version_is_the_digest_of_everything_the_plan_declares():
    plan = build_shadow_plan("vietnamworks")
    facts = {
        "scope": plan.scope, "caps": plan.caps, "requested_fields": plan.requested_fields,
        "completion_rule": plan.completion_rule, "endpoints": plan.endpoints,
        "retrieval_precision": plan.retrieval_precision,
        "authorization_revision": plan.authorization_revision,
    }
    assert plan.version == "synthetic-" + content_digest(facts)[:16]

    # Moving the completion rule into configuration is what changed the version, and
    # any further declared change produces a new immutable row rather than an edit.
    changed = build_shadow_plan("vietnamworks", config=_with_completion_rule(
        "every declared page succeeded, or the run failed"))
    assert changed.version != plan.version
    assert changed.scope == plan.scope


def test_an_undeclared_source_is_refused(document):
    with pytest.raises(PlanConfigurationError, match="no collection plan is declared"):
        build_shadow_plan("linkedin_direct")


def test_an_unresolvable_reference_is_an_error_not_a_default(document):
    document["plans"]["vietnamworks"]["declared_caps"]["max_jobs"] = "@safety.max_jobs"
    with pytest.raises(PlanConfigurationError, match="does not resolve"):
        build_shadow_plan("vietnamworks", config=document)


def test_an_unknown_plan_key_is_refused(document):
    document["plans"]["vietnamworks"]["declared_stop_condition"] = "never"
    with pytest.raises(PlanConfigurationError, match="undeclared keys"):
        build_shadow_plan("vietnamworks", config=document)


def test_a_missing_required_plan_key_is_refused(document):
    del document["plans"]["vietnamworks"]["completion_rule"]
    with pytest.raises(PlanConfigurationError, match="missing keys"):
        build_shadow_plan("vietnamworks", config=document)


@pytest.mark.parametrize("key", ["declared_scope", "declared_endpoints", "requested_fields"])
def test_a_declaration_may_not_be_empty(document, key):
    document["plans"]["vietnamworks"][key] = {}
    with pytest.raises(PlanConfigurationError, match="must not be empty"):
        build_shadow_plan("vietnamworks", config=document)


def test_an_unsupported_retrieval_precision_is_refused(document):
    document["plans"]["vietnamworks"]["retrieval_precision"] = "fortnight"
    with pytest.raises(PlanConfigurationError, match="retrieval precision"):
        build_shadow_plan("vietnamworks", config=document)


def test_a_plan_that_is_not_a_mapping_is_refused(document):
    document["plans"]["vietnamworks"] = ["vietnamworks"]
    with pytest.raises(PlanConfigurationError, match="not a mapping"):
        build_shadow_plan("vietnamworks", config=document)


def _with_completion_rule(rule: str) -> dict:
    document = deepcopy(settings.ingestion_yaml)
    document["plans"]["vietnamworks"]["completion_rule"] = rule
    return document
