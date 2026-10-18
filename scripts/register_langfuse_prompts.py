"""Register the release-pinned YAML prompt text with Langfuse."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml
from langfuse.api import NotFoundError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.tracing.prompt_registry import LANGFUSE_PROMPT_NAMES


def create_langfuse_client():
    """Create the client lazily so --dry-run remains network and settings free."""
    from src.agents.tracing.langfuse import create_langfuse_client as create_client

    return create_client()


PROMPTS_PATH = ROOT / "config" / "prompts.yaml"
PROMPT_LABEL = "candidate"
PRODUCTION_LABEL = "production"
PERMITTED_PROMPT_LABELS = frozenset({PROMPT_LABEL, PRODUCTION_LABEL})


class PromptClient(Protocol):
    @property
    def prompt(self) -> str: ...


class LangfusePromptClient(Protocol):
    def create_prompt(
        self,
        *,
        name: str,
        prompt: str,
        labels: list[str],
        type: Literal["text"],
        commit_message: str | None,
    ) -> PromptClient: ...

    def get_prompt(
        self,
        name: str,
        *,
        label: str,
        type: Literal["text"],
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
    label: str = PROMPT_LABEL,
    commit_message: str | None,
) -> tuple[int, int]:
    """Create versions only when the registered text differs from YAML.

    With `--label production` this is the deploy step: the released text
    becomes a version and the label moves to it, which restores the trace
    link. Unknown labels are refused so `latest` can never be written.
    """
    if label not in PERMITTED_PROMPT_LABELS:
        raise ValueError(
            "Prompt registration may target only: "
            + ", ".join(sorted(PERMITTED_PROMPT_LABELS))
        )
    created = 0
    unchanged = 0
    for definition in definitions:
        try:
            existing = client.get_prompt(
                definition.name,
                label=label,
                type="text",
                cache_ttl_seconds=0,
                max_retries=0,
            )
        except NotFoundError:  # A missing prompt is the normal first-run condition.
            existing = None

        if existing is not None and existing.prompt.strip() == definition.content:
            unchanged += 1
            print(f"unchanged {definition.name}")
            continue

        client.create_prompt(
            name=definition.name,
            prompt=definition.content,
            labels=[label],
            type="text",
            commit_message=commit_message,
        )
        created += 1
        print(f"registered {definition.name}")
    return created, unchanged


def check_prompt_drift(
    client: LangfusePromptClient,
    definitions: list[PromptDefinition],
    *,
    label: str = PRODUCTION_LABEL,
) -> int:
    """Compare each labelled version with the checked-in YAML text.

    Returns the number of surfaces whose text is missing or different, so a
    deployment can gate on a non-zero exit. A failed lookup also counts: the
    drift cannot be ruled out.
    """
    drifted = 0
    for definition in definitions:
        try:
            existing = client.get_prompt(
                definition.name,
                label=label,
                type="text",
                cache_ttl_seconds=0,
                max_retries=0,
            )
        except NotFoundError:
            print(
                f"drift {definition.name}: no '{label}' version is registered",
                file=sys.stderr,
            )
            drifted += 1
            continue
        except Exception as exc:
            print(
                f"drift {definition.name}: unable to read '{label}': {exc}",
                file=sys.stderr,
            )
            drifted += 1
            continue

        if existing.prompt.strip() != definition.content:
            print(
                f"drift {definition.name}: '{label}' text differs from "
                f"prompts.{definition.yaml_key}",
                file=sys.stderr,
            )
            drifted += 1
        else:
            print(
                f"ok {definition.name}: '{label}' text matches "
                f"prompts.{definition.yaml_key}"
            )
    return drifted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and list the YAML prompts without contacting Langfuse.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help=(
            f"Compare each '{PRODUCTION_LABEL}' version with the checked-in text; "
            "exit non-zero on drift."
        ),
    )
    parser.add_argument(
        "--commit-message",
        help="Override the default checked-out git commit provenance.",
    )
    parser.add_argument(
        "--label",
        default=PROMPT_LABEL,
        choices=sorted(PERMITTED_PROMPT_LABELS),
        help=(
            "Deployment label to register: candidate for an evaluation "
            "environment, production for a release."
        ),
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
                f"would register {definition.name} from prompts.{definition.yaml_key} with {args.label}"
            )
        return 0

    try:
        client = create_langfuse_client()
    except ValueError as exc:
        print(f"prompt registration: {exc}", file=sys.stderr)
        return 1

    if args.check:
        drifted = check_prompt_drift(client, definitions)
        if drifted:
            print(
                f"prompt check failed: {drifted} of {len(definitions)} surfaces drifted",
                file=sys.stderr,
            )
            return 1
        print(
            f"prompt check passed: all {len(definitions)} surfaces match "
            f"'{PRODUCTION_LABEL}'"
        )
        return 0

    commit_message = args.commit_message or git_commit()
    created, unchanged = synchronize_prompts(
        client, definitions, label=args.label, commit_message=commit_message
    )
    print(f"prompt registration complete: {created} created, {unchanged} unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
