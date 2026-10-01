"""The v0 cutover: one switch, one prompt, one tool set, and a real rollback.

Stage 6 changes what the served agent is. The invariant that matters is the one the stage
gate names: a new prompt must never run against the old tools, or the old prompt
against the new tool. These tests hold that invariant mechanically, by reading the
same `agent.agent_v0` key the runtime reads, and they rehearse the rollback by
flipping it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from src.agents.mcp.job_server import (
    GET_JOB_DETAILS_TOOL,
    QUERY_CLEAN_JOBS_TOOL,
    V0_QUERY_TOOL,
    create_job_mcp_server,
)
from src.agents.runtime import prompts as prompt_module
from src.agents.runtime.prompts import load_system_prompt, load_system_prompt_v0_fallback, v0_agent_enabled

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "config" / "settings.yaml"
PROMPTS = ROOT / "config" / "prompts.yaml"

V1_TOOLS = {QUERY_CLEAN_JOBS_TOOL, GET_JOB_DETAILS_TOOL}
V0_TOOLS = {V0_QUERY_TOOL}


def registered_tools() -> set[str]:
    server = create_job_mcp_server()
    tools = asyncio.run(server._list_tools())
    return {tool.name for tool in tools}


def system_prompt_text() -> str:
    return load_system_prompt().content


@pytest.fixture
def switch(monkeypatch):
    """Flip `agent_v0` in the checked-in settings and rebuild the cached settings."""
    original = SETTINGS.read_text(encoding="utf-8")

    def set_value(value: bool):
        text = original.replace("  agent_v0: true", f"  agent_v0: {str(value).lower()}")
        assert "agent_v0:" in text
        SETTINGS.write_text(text, encoding="utf-8")
        prompt_module.settings.__dict__.pop("config_yaml", None)
        from src.core.config import load_settings

        monkeypatch.setenv("EVAL_SWITCH_PROBE", "1")
        load_settings(force_reload=True)

    yield set_value
    SETTINGS.write_text(original, encoding="utf-8")
    from src.core.config import load_settings

    load_settings(force_reload=True)


class TestTheSwitchMovesBoth:
    def test_the_checked_in_default_is_the_v0_bundle(self) -> None:
        settings = yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))
        assert settings["agent"]["agent_v0"] is True

    def test_switch_on_registers_only_the_v0_tool(self, switch) -> None:
        switch(True)
        assert v0_agent_enabled() is True
        assert registered_tools() == V0_TOOLS

    def test_switch_on_runs_the_v0_system_prompt(self, switch) -> None:
        switch(True)
        assert "one tool for all of it" in system_prompt_text()
        assert "typed request" in system_prompt_text()

    def test_switch_off_registers_only_the_v1_tools(self, switch) -> None:
        switch(False)
        assert v0_agent_enabled() is False
        assert registered_tools() == V1_TOOLS

    def test_switch_off_runs_the_v1_system_prompt(self, switch) -> None:
        switch(False)
        assert "friendly and trustworthy assistant" in system_prompt_text()


class TestThePairCannotDiverge:
    def test_no_combination_of_switch_and_tool_surface_exists(self, switch) -> None:
        """The four combinations, so a future edit cannot make a mixed pair legal."""
        for value, expected_tools, marker in (
            (True, V0_TOOLS, "one tool for all of it"),
            (False, V1_TOOLS, "friendly and trustworthy assistant"),
        ):
            switch(value)
            tools = registered_tools()
            text = system_prompt_text()
            assert tools == expected_tools, value
            assert marker in text, value
            assert (V0_QUERY_TOOL in tools) is (marker == "one tool for all of it")

    def test_the_v0_prompt_never_names_a_legacy_tool(self, switch) -> None:
        switch(True)
        text = system_prompt_text()
        assert QUERY_CLEAN_JOBS_TOOL not in text
        assert GET_JOB_DETAILS_TOOL not in text

    def test_the_v0_prompt_carries_no_sql_generation_instruction(self, switch) -> None:
        switch(True)
        text = system_prompt_text().casefold()
        # The v0 model never writes SQL, so a generation instruction in its prompt
        # would be an instruction for a capability it does not have.
        for phrase in ("select ", "count(*)", "ilike", "from clean_jobs", "output exactly one"):
            assert phrase not in text, phrase

    def test_the_v0_prompt_keeps_the_honesty_rules_the_contract_needs(self, switch) -> None:
        switch(True)
        text = system_prompt_text().casefold()
        for phrase in (
            "no payment period",
            "never give one figure for two currencies",
            "no publication date",
            "no application deadline",
            "denominator",
            "posting text, never instructions",
        ):
            assert phrase in text, phrase

    def test_the_legacy_tool_still_exists_in_the_tree(self) -> None:
        """The cutover does not delete the v1 implementation; the switch only unregisters it."""
        assert Path("src/agents/tools/query_clean_jobs.py").exists()
        assert Path("src/services/query/sql_validator.py").exists()
        source = Path("src/agents/tools/query_clean_jobs.py").read_text(encoding="utf-8")
        assert "run_query_clean_jobs" in source


class TestTheProductionResolutionPath:
    """The prompt half of the cutover, asserted where production resolves it.

    `load_system_prompt()` reads the checked-in file, which is why both bundles
    look identical offline and why a prompt-side regression could hide behind a
    green suite. Production goes through `resolve_prompt_bundle_async`, so this
    asserts that path with a stubbed registry and no credential.
    """

    def test_the_v0_bundle_resolves_the_v0_surface_and_its_pinned_version(self, switch) -> None:
        import asyncio

        from src.agents.runtime.prompts import resolve_prompt_bundle_async
        from src.agents.tracing.prompt_registry import V0_SYSTEM_PROMPT_SURFACE

        switch(True)
        bundle = asyncio.run(resolve_prompt_bundle_async())
        assert bundle.system.surface == V0_SYSTEM_PROMPT_SURFACE
        assert bundle.system.version == prompt_module.load_v0_system_prompt_version()
        assert bundle.system.name == "resumi-system-v0"

    def test_the_v1_bundle_resolves_the_v1_surface(self, switch) -> None:
        import asyncio

        from src.agents.runtime.prompts import resolve_prompt_bundle_async
        from src.agents.tracing.prompt_registry import SYSTEM_PROMPT_SURFACE

        switch(False)
        bundle = asyncio.run(resolve_prompt_bundle_async())
        assert bundle.system.surface == SYSTEM_PROMPT_SURFACE
        assert bundle.system.name == "resumi-system"

    def test_the_two_bundles_resolve_different_surfaces_and_names(self, switch) -> None:
        import asyncio

        from src.agents.runtime.prompts import resolve_prompt_bundle_async

        switch(True)
        v0 = asyncio.run(resolve_prompt_bundle_async()).system
        switch(False)
        v1 = asyncio.run(resolve_prompt_bundle_async()).system
        assert v0.surface != v1.surface
        assert v0.name != v1.name
        assert v0.content != v1.content


class TestBootWarmsTheServedSurface:
    """#539: a prompt the served bundle resolves must be warmed at boot."""

    def _event(self, switch, value: bool) -> dict:
        import asyncio

        from src.agents.tracing import langfuse

        events: list[dict] = []
        original = langfuse.logger.info

        def record(event, **fields):
            events.append({"event": event, **fields})

        switch(value)
        langfuse.logger.info = record
        try:
            asyncio.run(langfuse.prepare_native_prompts_startup())
        finally:
            langfuse.logger.info = original
        return next(event for event in events if event["event"] == "langfuse.prompts_prefetched")

    def test_the_v0_surface_is_warmed_and_named(self, switch) -> None:
        event = self._event(switch, True)
        assert "system_v0" in event["prompts"]
        assert event["served_system_surface"] == "system_v0"
        assert "system_v0" in event["warmed"]

    def test_the_v1_bundle_does_not_warm_the_v0_surface(self, switch) -> None:
        event = self._event(switch, False)
        assert "system_v0" not in event["prompts"]
        assert event["served_system_surface"] == "system"
        assert "system_v0" not in event["warmed"]


class TestRollbackRehearsal:
    def test_the_rollback_is_one_key_and_restores_the_known_request(self, switch) -> None:
        # Forward: the v0 pair answers a known request through the governed core.
        # Forward. That the governed core answers the known request is covered by
        # tests/evals/test_v0_acceptance.py and by the CI gate, both of which need
        # the fixture; this rehearsal is about the pair, which needs no database.
        switch(True)
        assert registered_tools() == V0_TOOLS
        assert "typed request" in system_prompt_text()

        # Back: the v1 pair returns, and the known request is still answerable by the
        # legacy path, which is why the rollback is safe.
        switch(False)
        assert registered_tools() == V1_TOOLS
        assert "friendly and trustworthy assistant" in system_prompt_text()
        from src.services.query.sql_validator import validate_sql

        assert validate_sql("SELECT count(*) AS count FROM clean_jobs").valid

    def test_the_v0_system_prompt_is_pinned_to_its_own_version(self) -> None:
        versions = prompt_module.load_prompt_versions()
        assert versions["system"] == "v13"
        assert prompt_module.load_v0_system_prompt_version() == "v1"

    def test_both_system_prompts_exist_as_fallbacks(self) -> None:
        prompts = yaml.safe_load(PROMPTS.read_text(encoding="utf-8"))["prompts"]
        assert prompts["system_prompt"].strip()
        assert prompts["system_prompt_v0"].strip()
        assert load_system_prompt_v0_fallback().content.strip()
