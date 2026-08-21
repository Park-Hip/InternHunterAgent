from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "provision_langfuse_models.py"
SPEC = importlib.util.spec_from_file_location("provision_langfuse_models", SCRIPT_PATH)
assert SPEC and SPEC.loader
provision = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = provision
SPEC.loader.exec_module(provision)


@dataclass
class FakeMeta:
    total_pages: int = 1


@dataclass
class FakeResponse:
    data: list[object]
    meta: FakeMeta


@dataclass
class FakeTier:
    name: str
    is_default: bool
    priority: int
    conditions: list[dict[str, object]]
    prices: dict[str, float]


@dataclass
class FakeModel:
    model_name: str
    match_pattern: str
    start_date: datetime
    unit: str
    pricing_tiers: list[FakeTier]


class FakeModelsAPI:
    def __init__(self, models: list[FakeModel] | None = None) -> None:
        self.models = models or []
        self.creates: list[dict[str, object]] = []
        self.pages: list[int | None] = []

    def list(
        self, *, page: int | None = None, limit: int | None = None
    ) -> FakeResponse:
        self.pages.append(page)
        return FakeResponse(self.models, FakeMeta())

    def create(self, **kwargs: object) -> None:
        self.creates.append(kwargs)


def existing_model(definition: object) -> FakeModel:
    tiers = [
        FakeTier(
            tier.name,
            tier.is_default,
            tier.priority,
            list(tier.conditions),
            dict(tier.prices),
        )
        for tier in definition.pricing_tiers
    ]
    return FakeModel(
        definition.model_name,
        definition.match_pattern,
        definition.start_date,
        definition.unit,
        tiers,
    )


def test_committed_definition_is_dated_and_cannot_price_another_model() -> None:
    definition = provision.load_definitions()[0]

    assert definition.model_name == "deepseek-v4-flash"
    assert definition.start_date == datetime(2026, 8, 21, tzinfo=timezone.utc)
    assert definition.pricing_tiers[0].prices == {
        "input": 0.00000014,
        "input_cached_tokens": 0.0000000028,
        "output": 0.00000028,
    }
    assert provision.re.fullmatch(definition.match_pattern, "deepseek-v4-flash")
    assert not provision.re.fullmatch(definition.match_pattern, "deepseek-v4-pro")
    assert not provision.re.fullmatch(definition.match_pattern, "qwen/qwen3.6-27b")


def test_provision_creates_missing_definition_with_exact_pricing_tier() -> None:
    api = FakeModelsAPI()
    definition = provision.load_definitions()[0]

    result = provision.provision_definitions(api, [definition])

    assert result == {"created": ["deepseek-v4-flash"], "unchanged": []}
    assert len(api.creates) == 1
    created_tier = api.creates[0]["pricing_tiers"][0]
    assert created_tier.prices == definition.pricing_tiers[0].prices


def test_provision_is_idempotent_when_definition_already_matches() -> None:
    definition = provision.load_definitions()[0]
    api = FakeModelsAPI([existing_model(definition)])

    result = provision.provision_definitions(api, [definition])

    assert result == {"created": [], "unchanged": ["deepseek-v4-flash"]}
    assert api.creates == []


def test_provision_rejects_conflicting_existing_definition() -> None:
    definition = provision.load_definitions()[0]
    existing = existing_model(definition)
    existing.pricing_tiers[0].prices["output"] = 0.00000027
    api = FakeModelsAPI([existing])

    with pytest.raises(provision.ProvisioningError, match="differs"):
        provision.provision_definitions(api, [definition])

    assert api.creates == []


def test_dry_run_does_not_create_models() -> None:
    api = FakeModelsAPI()
    definition = provision.load_definitions()[0]

    result = provision.provision_definitions(api, [definition], dry_run=True)

    assert result == {"created": ["deepseek-v4-flash"], "unchanged": []}
    assert api.creates == []
