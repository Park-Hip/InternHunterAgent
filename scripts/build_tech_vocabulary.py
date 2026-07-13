from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
VENDOR_DIR = ROOT / "data" / "vendor"

LINGUIST_URL = (
    "https://raw.githubusercontent.com/github-linguist/linguist/master/"
    "lib/linguist/languages.yml"
)
DEVICON_URL = "https://raw.githubusercontent.com/devicons/devicon/master/devicon.json"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def fetch_text(url: str) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.text


def add_term(
    canonical_terms: set[str],
    aliases: dict[str, str],
    canonical: str,
    term_aliases: list[str] | None = None,
) -> None:
    canonical = canonical.strip()
    if not canonical:
        return
    canonical_terms.difference_update(
        [term for term in canonical_terms if term.casefold() == canonical.casefold()]
    )
    canonical_terms.add(canonical)
    for alias in term_aliases or []:
        alias = alias.strip()
        if alias and alias.casefold() != canonical.casefold():
            aliases[alias] = canonical
    for alias in list(aliases):
        if alias.casefold() == canonical.casefold():
            del aliases[alias]
    for alias, existing_canonical in list(aliases.items()):
        if existing_canonical.casefold() == canonical.casefold():
            aliases[alias] = canonical


def add_linguist_terms(
    languages: dict[str, Any],
    canonical_terms: set[str],
    aliases: dict[str, str],
) -> None:
    for language, metadata in languages.items():
        if not isinstance(language, str) or not isinstance(metadata, dict):
            continue
        if metadata.get("type") not in {"programming", "markup"}:
            continue
        language_aliases = metadata.get("aliases", [])
        add_term(
            canonical_terms,
            aliases,
            language,
            [alias for alias in language_aliases if isinstance(alias, str)],
        )


def add_devicon_terms(
    devicons: list[Any],
    canonical_terms: set[str],
    aliases: dict[str, str],
) -> None:
    for item in devicons:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        canonical = name.strip()
        if not canonical:
            continue
        alias_values: list[str] = []
        values = item.get("altnames", [])
        if isinstance(values, list):
            alias_values.extend(value for value in values if isinstance(value, str))
        add_term(canonical_terms, aliases, canonical, alias_values)


def add_seed_terms(
    seed: dict[str, Any],
    ingestion: dict[str, Any],
    canonical_terms: set[str],
    aliases: dict[str, str],
) -> list[str]:
    for legacy_term in ingestion.get("tech_dictionary", []):
        if isinstance(legacy_term, str):
            add_term(canonical_terms, aliases, legacy_term)

    techniques = seed.get("techniques", {})
    if isinstance(techniques, dict):
        for canonical, metadata in techniques.items():
            if not isinstance(canonical, str):
                continue
            term_aliases: list[str] = []
            if isinstance(metadata, dict) and isinstance(metadata.get("aliases"), list):
                term_aliases = [
                    alias for alias in metadata["aliases"] if isinstance(alias, str)
                ]
            add_term(canonical_terms, aliases, canonical, term_aliases)

    seed_aliases = seed.get("aliases", {})
    if isinstance(seed_aliases, dict):
        for alias, canonical in seed_aliases.items():
            if isinstance(alias, str) and isinstance(canonical, str):
                add_term(canonical_terms, aliases, canonical, [alias])

    denylist = seed.get("denylist", [])
    return [term for term in denylist if isinstance(term, str)]


def build_vocabulary() -> dict[str, Any]:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    languages_text = fetch_text(LINGUIST_URL)
    devicon_text = fetch_text(DEVICON_URL)

    (VENDOR_DIR / "languages.yml").write_text(languages_text, encoding="utf-8")
    (VENDOR_DIR / "devicon.json").write_text(devicon_text, encoding="utf-8")

    languages = yaml.safe_load(languages_text) or {}
    devicons = json.loads(devicon_text)
    if not isinstance(languages, dict):
        raise ValueError("Linguist languages.yml did not parse to a mapping")
    if not isinstance(devicons, list):
        raise ValueError("Devicon devicon.json did not parse to a list")

    canonical_terms: set[str] = set()
    aliases: dict[str, str] = {}
    add_linguist_terms(languages, canonical_terms, aliases)
    add_devicon_terms(devicons, canonical_terms, aliases)
    denylist = add_seed_terms(
        load_yaml(CONFIG_DIR / "tech_seed.yaml"),
        load_yaml(CONFIG_DIR / "ingestion.yaml"),
        canonical_terms,
        aliases,
    )

    return {
        "metadata": {
            "sources": [
                "GitHub Linguist languages.yml",
                "Devicon devicon.json",
                "config/ingestion.yaml tech_dictionary seed",
                "config/tech_seed.yaml AI/Data technique seed",
            ],
            "generated_by": "scripts/build_tech_vocabulary.py",
        },
        "canonical_terms": sorted(canonical_terms, key=str.casefold),
        "aliases": dict(sorted(aliases.items(), key=lambda item: item[0].casefold())),
        "denylist": sorted(set(denylist), key=str.casefold),
    }


def main() -> None:
    vocabulary = build_vocabulary()
    output_path = CONFIG_DIR / "tech_vocabulary.yaml"
    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        yaml.safe_dump(vocabulary, file, sort_keys=False, allow_unicode=True)

    print(f"Wrote {output_path.relative_to(ROOT)}")
    print(f"Wrote {(VENDOR_DIR / 'languages.yml').relative_to(ROOT)}")
    print(f"Wrote {(VENDOR_DIR / 'devicon.json').relative_to(ROOT)}")
    print(f"Canonical terms: {len(vocabulary['canonical_terms'])}")
    print(f"Aliases: {len(vocabulary['aliases'])}")


if __name__ == "__main__":
    main()
