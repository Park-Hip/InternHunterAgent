from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langfuse.api import NotFoundError

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "register_langfuse_prompts.py"
SPEC = importlib.util.spec_from_file_location("register_langfuse_prompts", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
register_langfuse_prompts = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = register_langfuse_prompts
SPEC.loader.exec_module(register_langfuse_prompts)


class FakeLangfuse:
    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}
        self.create_calls: list[dict[str, object]] = []

    def get_prompt(self, name: str, **_: object) -> SimpleNamespace:
        if name not in self.prompts:
            raise NotFoundError({"name": name})
        return SimpleNamespace(prompt=self.prompts[name])

    def create_prompt(self, **kwargs: object) -> SimpleNamespace:
        name = str(kwargs["name"])
        prompt = str(kwargs["prompt"])
        self.prompts[name] = prompt
        self.create_calls.append(kwargs)
        return SimpleNamespace(prompt=prompt)


def test_load_prompt_definitions_registers_each_model_visible_prompt() -> None:
    definitions = register_langfuse_prompts.load_prompt_definitions()

    assert [(item.yaml_key, item.name) for item in definitions] == [
        ("system_prompt", "resumi-system"),
        ("schema_context", "resumi-schema-context"),
        ("sql_generation", "resumi-sql-generation"),
    ]
    assert all(item.content for item in definitions)


def test_synchronize_prompts_is_a_noop_when_yaml_content_is_unchanged() -> None:
    client = FakeLangfuse()
    definitions = register_langfuse_prompts.load_prompt_definitions()

    assert register_langfuse_prompts.synchronize_prompts(
        client, definitions, commit_message="commit-1"
    ) == (3, 0)
    assert register_langfuse_prompts.synchronize_prompts(
        client, definitions, commit_message="commit-1"
    ) == (0, 3)
    assert len(client.create_calls) == 3


def test_synchronize_prompts_creates_a_version_only_for_changed_content() -> None:
    client = FakeLangfuse()
    definitions = register_langfuse_prompts.load_prompt_definitions()
    register_langfuse_prompts.synchronize_prompts(
        client, definitions, commit_message="commit-1"
    )
    changed = [
        register_langfuse_prompts.PromptDefinition(
            yaml_key=item.yaml_key,
            name=item.name,
            content=item.content + "\nChanged."
            if item.yaml_key == "sql_generation"
            else item.content,
        )
        for item in definitions
    ]

    assert register_langfuse_prompts.synchronize_prompts(
        client, changed, commit_message="commit-2"
    ) == (1, 2)
    assert [call["name"] for call in client.create_calls] == [
        "resumi-system",
        "resumi-schema-context",
        "resumi-sql-generation",
        "resumi-sql-generation",
    ]
    assert client.create_calls[-1]["commit_message"] == "commit-2"


def test_dry_run_validates_yaml_without_creating_a_langfuse_client(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        register_langfuse_prompts,
        "create_langfuse_client",
        lambda: (_ for _ in ()).throw(AssertionError("must not construct client")),
    )

    assert register_langfuse_prompts.main(["--dry-run"]) == 0
    assert "would register resumi-sql-generation" in capsys.readouterr().out


def test_synchronize_prompts_does_not_create_a_version_when_remote_lookup_fails() -> (
    None
):
    client = FakeLangfuse()
    client.get_prompt = lambda *_args, **_kwargs: (_ for _ in ()).throw(  # type: ignore[method-assign]
        RuntimeError("Langfuse unavailable")
    )

    with pytest.raises(RuntimeError, match="Langfuse unavailable"):
        register_langfuse_prompts.synchronize_prompts(
            client,
            register_langfuse_prompts.load_prompt_definitions(),
            commit_message="commit-1",
        )

    assert client.create_calls == []
