"""Register the git-authoritative prompts.yaml content in Langfuse."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml
from langfuse import Langfuse
from langfuse.api import NotFoundError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.tracing.prompt_registry import LANGFUSE_PROMPT_NAMES

PROMPTS_PATH = ROOT / "config" / "prompts.yaml"
PROMPT_LABEL = "production"


class PromptClient(Protocol):
    prompt: str


class LangfusePromptClient(Protocol):
    def create_prompt(
        self,
        *,
        name: str,
        prompt: str,
        labels: list[str],
        type: str,
        commit_message: str | None,
    ) -> PromptClient: ...

    def get_prompt(
        self,
        name: str,
        *,
        label: str,
        type: str,
        cache_ttl_seconds: int,
        max_retries: int,
    ) -> PromptClient: ...


@dataclass(frozen=True)
class PromptDefinition:
    yaml_key: str
    name: str
    content: str


def load_prompt_definitions(path: Path = PROMPTS_PATH) -> list[PromptDefinition]:
    """Read every registered prompt directly from the reviewed YAML source."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("prompts"), dict):
        raise ValueError("Missing 'prompts' mapping in config/prompts.yaml")
    prompts: dict[str, Any] = raw["prompts"]

    definitions: list[PromptDefinition] = []
    for yaml_key, name in LANGFUSE_PROMPT_NAMES.items():
        content = prompts.get(yaml_key)
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"Missing or empty 'prompts.{yaml_key}' in config/prompts.yaml"
            )
        definitions.append(
            PromptDefinition(yaml_key=yaml_key, name=name, content=content.strip())
        )
    return definitions


def git_commit(root: Path = ROOT) -> str | None:
    """Return the checked-out commit for Langfuse prompt-version provenance."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def synchronize_prompts(
    client: LangfusePromptClient,
    definitions: list[PromptDefinition],
    *,
    commit_message: str | None,
) -> tuple[int, int]:
    """Create versions only when the registered text differs from YAML."""
    created = 0
    unchanged = 0
    for definition in definitions:
        try:
            existing = client.get_prompt(
                definition.name,
                label=PROMPT_LABEL,
                type="text",
                cache_ttl_seconds=0,
                max_retries=0,
            )
        except NotFoundError:  # A missing prompt is the normal first-run condition.
            existing = None

        if existing is not None and existing.prompt == definition.content:
            unchanged += 1
            print(f"unchanged {definition.name}")
            continue

        client.create_prompt(
            name=definition.name,
            prompt=definition.content,
            labels=[PROMPT_LABEL],
            type="text",
            commit_message=commit_message,
        )
        created += 1
        print(f"registered {definition.name}")
    return created, unchanged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and list the YAML prompts without contacting Langfuse.",
    )
    parser.add_argument(
        "--commit-message",
        help="Override the default checked-out git commit provenance.",
    )
    args = parser.parse_args(argv)

    try:
        definitions = load_prompt_definitions()
    except ValueError as exc:
        print(f"prompt registration: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        for definition in definitions:
            print(
                f"would register {definition.name} from prompts.{definition.yaml_key}"
            )
        return 0

    commit_message = args.commit_message or git_commit()
    created, unchanged = synchronize_prompts(
        Langfuse(), definitions, commit_message=commit_message
    )
    print(f"prompt registration complete: {created} created, {unchanged} unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
