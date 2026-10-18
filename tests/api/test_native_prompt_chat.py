"""End-to-end coverage for native Langfuse prompt propagation.

A managed prompt that resolves to a native Langfuse prompt client is the only
configuration that links a generation to its prompt version, and
`src/agents/tracing/langfuse.py` does that by calling
`propagate_attributes(prompt=...)`.
Production answered streaming chat with an in-band `error` event and never
invoked the model when the deployed SDK had no `prompt` keyword, while the
release-pinned fallback prompts kept working.

These probes drive the real route, the real runtime, the real Langfuse
`CallbackHandler`, and the real `propagate_attributes` with a real prompt
client, so a lockfile that cannot link prompts to generations fails here instead
of in production.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langfuse.model import TextPromptClient
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.agents.runtime.prompts import load_prompt_versions
from src.agents.runtime.react_agent import AgentRuntime
from src.agents.tracing import langfuse
from src.agents.tracing.prompt_registry import PROMPT_DEFINITIONS
from src.api.app import create_app
from src.core.config import settings
from tests.langfuse_prompts import native_prompt_client, prompt_link

ANSWER = "There are 3 roles."
CHAT_QUERY = "list 3 data engineer jobs"
GENERATION_TYPE = "generation"

# The managed deployment the test project serves, keyed by surface.
NATIVE_VERSIONS = {"system": 12, "schema_context": 31, "sql_generation": 13}
NATIVE_VERSIONS_BY_NAME = {
    definition.name: NATIVE_VERSIONS[definition.surface]
    for definition in PROMPT_DEFINITIONS
}

# The one system prompt the served bundle resolves, so the link a generation
# carries is the reviewed surface rather than whichever bundle happened to run.
EXPECTED_SYSTEM_LINK = {("resumi-system", NATIVE_VERSIONS["system"])}

# The released text of each surface, the text the served bundle must use.
RELEASE_TEXT = {
    definition.name: settings.prompts_yaml["prompts"][definition.yaml_key].strip()
    for definition in PROMPT_DEFINITIONS
}


def _release_prompt_tags() -> set[str]:
    return {
        f"prompt:{surface}:{version}"
        for surface, version in load_prompt_versions().items()
    }


def _parse_sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.strip().split("\n\n"):
        event_type = None
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ")
            if line.startswith("data: "):
                data = line.removeprefix("data: ")
        if event_type is not None:
            events.append((event_type, json.loads(data)))
    return events


def _streamed_answer(events: list[tuple[str, dict[str, Any]]]) -> str:
    return "".join(
        payload["text"] for event_type, payload in events if event_type == "token"
    )


class _ChatModelStub(GenericFakeChatModel):
    """Answer deterministically while still accepting the agent's tool binding."""

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        return self


def _build_model(profile: str = "react") -> _ChatModelStub:
    return _ChatModelStub(messages=iter([AIMessage(content=ANSWER)]))


class _LangfuseRecorder:
    """A real Langfuse client whose spans land in memory instead of on the network."""

    _public_keys = itertools.count()

    def __init__(self) -> None:
        public_key = f"pk-lf-native-prompt-{next(self._public_keys)}"
        self.exporter = InMemorySpanExporter()
        self.client = Langfuse(
            public_key=public_key,
            secret_key="sk-lf-native-prompt",
            base_url="https://langfuse.invalid",
            tracer_provider=TracerProvider(resource=Resource.create({})),
            span_exporter=self.exporter,
            flush_at=1,
            flush_interval=0.05,
        )
        self.handler = CallbackHandler(public_key=public_key)
        # `get_trace_url` resolves the project id over the network before it can
        # build a trace link. Seed it so a recorded turn never leaves the process.
        self.client._project_id = "project-native-prompt"

    def get_prompt(
        self, name: str, *, is_fallback: bool, drifted: bool = False
    ) -> TextPromptClient:
        """Answer a managed prompt lookup with the released or a drifted text."""
        return native_prompt_client(
            name,
            NATIVE_VERSIONS_BY_NAME[name],
            text=f"managed text for {name}" if drifted else RELEASE_TEXT[name],
            is_fallback=is_fallback,
        )

    def shutdown(self) -> None:
        self.client.shutdown()

    def trace_tags(self) -> set[str]:
        """Every trace tag the exported root observation carries."""
        for span in self.exporter.get_finished_spans():
            tags = span.attributes.get("langfuse.trace.tags")
            if tags:
                return {str(tag) for tag in tags}
        return set()

    def prompt_links(self, observation_type: str) -> list[tuple[Any, Any]]:
        """Every exported observation of a type, paired with its prompt link."""
        return [
            prompt_link(span.attributes)
            for span in self.exporter.get_finished_spans()
            if span.attributes.get("langfuse.observation.type") == observation_type
        ]


class _ChatHarness:
    """Chat over HTTP with a managed prompt deployment the test controls."""

    def __init__(self) -> None:
        self.recorder = _LangfuseRecorder()
        self.serve_fallbacks = False
        self.serve_drifted_text = False
        self.app = create_app(rate_limit="1000/minute", docs_enabled=False)
        self.client = TestClient(self.app)

    def install_runtime(self) -> None:
        """Attach the real runtime once the provider is under test control."""
        self.app.state.runtime = AgentRuntime()

    def stream(self, session_id: str) -> Any:
        return self.client.post(
            "/api/v1/agent/chat/stream",
            json={"query": CHAT_QUERY, "session_id": session_id},
        )

    def one_shot(self, session_id: str) -> Any:
        return self.client.post(
            "/api/v1/agent/chat",
            json={"query": CHAT_QUERY, "session_id": session_id},
        )

    def generations(self) -> list[tuple[Any, Any]]:
        links = self.recorder.prompt_links(GENERATION_TYPE)
        assert links, "the model must run and produce a Langfuse generation"
        return links

    def shutdown(self) -> None:
        self.recorder.shutdown()


@pytest.fixture
def chat(monkeypatch: pytest.MonkeyPatch) -> Iterator[_ChatHarness]:
    """Serve the real app with tracing live and prompts resolved in memory."""
    harness = _ChatHarness()
    monkeypatch.setattr(langfuse, "_langfuse", harness.recorder.client)
    monkeypatch.setattr(langfuse, "_langfuse_handler", harness.recorder.handler)
    monkeypatch.setattr(
        harness.recorder.client,
        "get_prompt",
        lambda name, **_kwargs: harness.recorder.get_prompt(
            name,
            is_fallback=harness.serve_fallbacks,
            drifted=harness.serve_drifted_text,
        ),
    )
    monkeypatch.setattr("src.agents.runtime.factory.build_model", _build_model)
    harness.install_runtime()
    yield harness
    harness.shutdown()


def test_streaming_chat_links_the_generation_to_the_managed_prompt(
    chat: _ChatHarness,
) -> None:
    response = chat.stream("session-471")

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    event_types = [event_type for event_type, _ in events]
    assert event_types[0] == "session"
    assert event_types[-1] == "done"
    assert "error" not in event_types
    assert _streamed_answer(events) == ANSWER
    metadata = next(
        payload for event_type, payload in events if event_type == "metadata"
    )
    assert metadata["trace_id"]

    assert set(chat.generations()) == EXPECTED_SYSTEM_LINK
    assert _release_prompt_tags() <= chat.recorder.trace_tags()


def test_streaming_chat_serves_the_release_text_when_the_managed_text_drifted(
    chat: _ChatHarness,
) -> None:
    """A drifted managed text never reaches the model and never links."""
    chat.serve_drifted_text = True

    response = chat.stream("session-471")

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert "error" not in [event_type for event_type, _ in events]
    assert _streamed_answer(events) == ANSWER
    assert _release_prompt_tags() <= chat.recorder.trace_tags()

    assert set(chat.generations()) == {(None, None)}


def test_one_shot_chat_links_the_generation_to_the_managed_prompt(
    chat: _ChatHarness,
) -> None:
    response = chat.one_shot("session-471")

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == ANSWER
    assert body["trace_id"]

    assert set(chat.generations()) == EXPECTED_SYSTEM_LINK
    assert _release_prompt_tags() <= chat.recorder.trace_tags()


def test_streaming_chat_answers_with_release_fallback_prompts(
    chat: _ChatHarness,
) -> None:
    """A fallback prompt is served, and is deliberately not linked as a version."""
    chat.serve_fallbacks = True

    response = chat.stream("session-471")

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert "error" not in [event_type for event_type, _ in events]
    assert _streamed_answer(events) == ANSWER

    assert set(chat.generations()) == {(None, None)}
