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


def seed_production(client: FakeLangfuse) -> None:
    register_langfuse_prompts.synchronize_prompts(
        client,
        register_langfuse_prompts.load_prompt_definitions(),
        label="production",
        commit_message="deploy-1",
    )


def test_load_prompt_definitions_registers_each_model_visible_prompt() -> None:
    """Every managed prompt surface is registered.

    The list comes from the prompt registry rather than a local copy, so a new
    surface cannot be added without a published version of its own.
    """
    from src.agents.tracing.prompt_registry import PROMPT_DEFINITIONS

    definitions = register_langfuse_prompts.load_prompt_definitions()

    assert [(item.yaml_key, item.name) for item in definitions] == [
        (definition.yaml_key, definition.name) for definition in PROMPT_DEFINITIONS
    ]
    assert all(item.content for item in definitions)


def test_synchronize_prompts_is_a_noop_when_yaml_content_is_unchanged() -> None:
    client = FakeLangfuse()
    definitions = register_langfuse_prompts.load_prompt_definitions()

    created = len(definitions)
    assert register_langfuse_prompts.synchronize_prompts(
        client, definitions, commit_message="commit-1"
    ) == (created, 0)
    assert register_langfuse_prompts.synchronize_prompts(
        client, definitions, commit_message="commit-1"
    ) == (0, created)
    assert len(client.create_calls) == created


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
    ) == (1, len(definitions) - 1)
    assert [call["name"] for call in client.create_calls] == [
        *(item.name for item in definitions),
        "resumi-sql-generation",
    ]
    assert client.create_calls[-1]["commit_message"] == "commit-2"


def test_synchronize_prompts_registers_the_production_label() -> None:
    """The deploy step moves `production` onto the released text."""
    client = FakeLangfuse()
    definitions = register_langfuse_prompts.load_prompt_definitions()

    assert register_langfuse_prompts.synchronize_prompts(
        client, definitions, label="production", commit_message="deploy-1"
    ) == (len(definitions), 0)
    assert [call["labels"] for call in client.create_calls] == [
        ["production"] for _ in definitions
    ]


def test_synchronize_prompts_moves_production_only_for_changed_content() -> None:
    client = FakeLangfuse()
    definitions = register_langfuse_prompts.load_prompt_definitions()
    seed_production(client)
    client.create_calls.clear()
    changed = [
        register_langfuse_prompts.PromptDefinition(
            yaml_key=item.yaml_key,
            name=item.name,
            content=item.content + "\nChanged."
            if item.yaml_key == "system_prompt"
            else item.content,
        )
        for item in definitions
    ]

    assert register_langfuse_prompts.synchronize_prompts(
        client, changed, label="production", commit_message="deploy-2"
    ) == (1, len(definitions) - 1)
    assert [call["name"] for call in client.create_calls] == ["resumi-system"]
    assert client.create_calls[-1]["labels"] == ["production"]


def test_synchronize_prompts_refuses_an_unknown_label() -> None:
    with pytest.raises(ValueError, match="may target only"):
        register_langfuse_prompts.synchronize_prompts(
            FakeLangfuse(),
            register_langfuse_prompts.load_prompt_definitions(),
            label="latest",
            commit_message="commit-1",
        )


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


def test_main_registers_the_production_label_after_a_release(
    monkeypatch, capsys
) -> None:
    client = FakeLangfuse()
    monkeypatch.setattr(
        register_langfuse_prompts, "create_langfuse_client", lambda: client
    )

    assert (
        register_langfuse_prompts.main(
            ["--label", "production", "--commit-message", "deploy-1"]
        )
        == 0
    )
    assert "prompt registration complete" in capsys.readouterr().out
    assert all(call["labels"] == ["production"] for call in client.create_calls)


def test_check_exits_zero_when_every_production_text_matches(
    monkeypatch, capsys
) -> None:
    client = FakeLangfuse()
    seed_production(client)
    monkeypatch.setattr(
        register_langfuse_prompts, "create_langfuse_client", lambda: client
    )

    assert register_langfuse_prompts.main(["--check"]) == 0
    assert "prompt check passed" in capsys.readouterr().out


def test_check_exits_non_zero_when_a_production_text_drifted(
    monkeypatch, capsys
) -> None:
    client = FakeLangfuse()
    seed_production(client)
    client.prompts["resumi-sql-generation"] = "stale text"
    monkeypatch.setattr(
        register_langfuse_prompts, "create_langfuse_client", lambda: client
    )

    assert register_langfuse_prompts.main(["--check"]) == 1
    captured = capsys.readouterr()
    assert "drift resumi-sql-generation" in captured.err
    assert "prompt check failed" in captured.err


def test_check_exits_non_zero_when_a_production_version_is_missing(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        register_langfuse_prompts, "create_langfuse_client", FakeLangfuse
    )

    assert register_langfuse_prompts.main(["--check"]) == 1
    assert "no 'production' version is registered" in capsys.readouterr().err


def test_check_exits_non_zero_when_the_remote_lookup_fails(
    monkeypatch, capsys
) -> None:
    client = FakeLangfuse()
    client.get_prompt = lambda *_args, **_kwargs: (_ for _ in ()).throw(  # type: ignore[method-assign]
        RuntimeError("Langfuse unavailable")
    )
    monkeypatch.setattr(
        register_langfuse_prompts, "create_langfuse_client", lambda: client
    )

    assert register_langfuse_prompts.main(["--check"]) == 1
    assert "unable to read 'production'" in capsys.readouterr().err


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
