"""Provision version-controlled Langfuse model-pricing definitions."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, Sequence

import yaml
from langfuse import Langfuse
from langfuse.api.commons.types.model_usage_unit import ModelUsageUnit
from langfuse.api.commons.types.pricing_tier_input import PricingTierInput


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEFINITIONS_PATH = ROOT / "config" / "langfuse_models.yaml"


class ProvisioningError(ValueError):
    """Raised when the local definition cannot safely be provisioned."""


class ModelsAPI(Protocol):
    def create(self, **kwargs: Any) -> Any: ...

    def list(self, *, page: int | None = None, limit: int | None = None) -> Any: ...


@dataclass(frozen=True)
class PricingTier:
    name: str
    is_default: bool
    priority: int
    conditions: tuple[dict[str, Any], ...]
    prices: dict[str, float]


@dataclass(frozen=True)
class ModelDefinition:
    model_name: str
    match_pattern: str
    start_date: datetime
    unit: str
    pricing_tiers: tuple[PricingTier, ...]


def _required_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ProvisioningError(f"{context}.{key} must be a non-empty string")
    return value


def _parse_start_date(value: Any, context: str) -> datetime:
    if not isinstance(value, str):
        raise ProvisioningError(f"{context}.start_date must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProvisioningError(
            f"{context}.start_date is not a valid ISO 8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise ProvisioningError(f"{context}.start_date must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _parse_tier(data: Any, context: str) -> PricingTier:
    if not isinstance(data, dict):
        raise ProvisioningError(f"{context} must be a mapping")
    name = _required_string(data, "name", context)
    is_default = data.get("is_default")
    priority = data.get("priority")
    conditions = data.get("conditions")
    prices = data.get("prices")
    if not isinstance(is_default, bool):
        raise ProvisioningError(f"{context}.is_default must be a boolean")
    if not isinstance(priority, int):
        raise ProvisioningError(f"{context}.priority must be an integer")
    if not isinstance(conditions, list) or not all(
        isinstance(item, dict) for item in conditions
    ):
        raise ProvisioningError(f"{context}.conditions must be a list of mappings")
    if not isinstance(prices, dict) or not prices:
        raise ProvisioningError(f"{context}.prices must be a non-empty mapping")
    parsed_prices: dict[str, float] = {}
    for usage_type, price in prices.items():
        if not isinstance(usage_type, str) or not usage_type:
            raise ProvisioningError(f"{context}.prices has an invalid usage type")
        if not isinstance(price, (int, float)) or isinstance(price, bool) or price < 0:
            raise ProvisioningError(
                f"{context}.prices.{usage_type} must be a non-negative number"
            )
        parsed_prices[usage_type] = float(price)
    return PricingTier(name, is_default, priority, tuple(conditions), parsed_prices)


def load_definitions(
    path: Path = DEFAULT_DEFINITIONS_PATH,
) -> tuple[ModelDefinition, ...]:
    """Read and validate the dated model definitions committed in the repository."""
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ProvisioningError(f"Expected a mapping in {path}")
    evidence = data.get("evidence")
    models = data.get("models")
    if not isinstance(evidence, dict):
        raise ProvisioningError("evidence must be a mapping")
    _required_string(evidence, "retrieved_on", "evidence")
    _required_string(evidence, "source", "evidence")
    if not isinstance(models, list) or not models:
        raise ProvisioningError("models must be a non-empty list")

    definitions: list[ModelDefinition] = []
    identities: set[tuple[str, str, datetime]] = set()
    for index, item in enumerate(models):
        context = f"models[{index}]"
        if not isinstance(item, dict):
            raise ProvisioningError(f"{context} must be a mapping")
        model_name = _required_string(item, "model_name", context)
        match_pattern = _required_string(item, "match_pattern", context)
        try:
            pattern = re.compile(match_pattern)
        except re.error as exc:
            raise ProvisioningError(
                f"{context}.match_pattern is not a valid regex"
            ) from exc
        if pattern.fullmatch(model_name) is None:
            raise ProvisioningError(
                f"{context}.match_pattern must exactly match model_name"
            )
        if not match_pattern.startswith("(?i)^") or not match_pattern.endswith("$"):
            raise ProvisioningError(
                f"{context}.match_pattern must be case-insensitive and anchored"
            )
        start_date = _parse_start_date(item.get("start_date"), context)
        unit = _required_string(item, "unit", context)
        try:
            ModelUsageUnit(unit)
        except ValueError as exc:
            raise ProvisioningError(
                f"{context}.unit is not a Langfuse model usage unit"
            ) from exc
        tiers_data = item.get("pricing_tiers")
        if not isinstance(tiers_data, list) or not tiers_data:
            raise ProvisioningError(f"{context}.pricing_tiers must be a non-empty list")
        tiers = tuple(
            _parse_tier(tier, f"{context}.pricing_tiers[{tier_index}]")
            for tier_index, tier in enumerate(tiers_data)
        )
        if sum(tier.is_default for tier in tiers) != 1:
            raise ProvisioningError(
                f"{context}.pricing_tiers must contain exactly one default tier"
            )
        if {tier.priority for tier in tiers} != set(range(len(tiers))):
            raise ProvisioningError(
                f"{context}.pricing_tiers priorities must start at zero with no gaps"
            )
        identity = (model_name, match_pattern, start_date)
        if identity in identities:
            raise ProvisioningError(
                f"{context} duplicates an existing model definition"
            )
        identities.add(identity)
        definitions.append(
            ModelDefinition(model_name, match_pattern, start_date, unit, tiers)
        )
    return tuple(definitions)


def _list_models(api: ModelsAPI) -> list[Any]:
    page = 1
    models: list[Any] = []
    while True:
        response = api.list(page=page, limit=100)
        models.extend(response.data)
        total_pages = getattr(response.meta, "total_pages", page)
        if page >= total_pages:
            return models
        page += 1


def _same_definition(existing: Any, definition: ModelDefinition) -> bool:
    if (
        existing.model_name != definition.model_name
        or existing.match_pattern != definition.match_pattern
        or existing.start_date != definition.start_date
        or existing.unit != definition.unit
    ):
        return False
    expected = [
        (tier.name, tier.is_default, tier.priority, list(tier.conditions), tier.prices)
        for tier in definition.pricing_tiers
    ]
    actual = [
        (tier.name, tier.is_default, tier.priority, tier.conditions, tier.prices)
        for tier in existing.pricing_tiers
    ]
    return actual == expected


def provision_definitions(
    api: ModelsAPI,
    definitions: Sequence[ModelDefinition],
    *,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Create missing definitions and reject mismatched definitions instead of overwriting them."""
    existing_models = _list_models(api)
    created: list[str] = []
    unchanged: list[str] = []
    for definition in definitions:
        matches = [
            model
            for model in existing_models
            if model.model_name == definition.model_name
            and model.match_pattern == definition.match_pattern
            and model.start_date == definition.start_date
        ]
        if len(matches) > 1:
            raise ProvisioningError(
                f"Langfuse has duplicate definitions for {definition.model_name}; resolve them manually"
            )
        if matches:
            if not _same_definition(matches[0], definition):
                raise ProvisioningError(
                    f"Langfuse definition for {definition.model_name} differs from {DEFAULT_DEFINITIONS_PATH.name}"
                )
            unchanged.append(definition.model_name)
            continue
        if not dry_run:
            api.create(
                model_name=definition.model_name,
                match_pattern=definition.match_pattern,
                start_date=definition.start_date,
                unit=ModelUsageUnit(definition.unit),
                pricing_tiers=[
                    PricingTierInput(
                        name=tier.name,
                        is_default=tier.is_default,
                        priority=tier.priority,
                        conditions=list(tier.conditions),
                        prices=tier.prices,
                    )
                    for tier in definition.pricing_tiers
                ],
            )
        created.append(definition.model_name)
    return {"created": created, "unchanged": unchanged}


def _build_api_from_environment() -> ModelsAPI:
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL")
    if not public_key or not secret_key or not host:
        raise ProvisioningError(
            "Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST "
            "(or LANGFUSE_BASE_URL) before provisioning model definitions"
        )
    return Langfuse(public_key=public_key, secret_key=secret_key, host=host).api.models


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definitions", type=Path, default=DEFAULT_DEFINITIONS_PATH)
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate without creating models"
    )
    args = parser.parse_args()
    definitions = load_definitions(args.definitions)
    result = provision_definitions(
        _build_api_from_environment(), definitions, dry_run=args.dry_run
    )
    for model_name in result["created"]:
        action = "Would create" if args.dry_run else "Created"
        print(f"{action} {model_name}")
    for model_name in result["unchanged"]:
        print(f"Unchanged {model_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
