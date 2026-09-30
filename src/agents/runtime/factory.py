"""Agent construction boundary.

The factory is asynchronous and receives the already-discovered LangChain tool
list through composition. Tool discovery happens exactly once at startup (see
src/agents/mcp/adapter.py and src/serving/composition.py), so ``create_agent``
is only ever called after successful MCP tool discovery and never publishes an
agent with a partial tool surface.
"""

import collections.abc

from langchain.agents import create_agent
from langchain.messages import SystemMessage
from langchain_core.tools import BaseTool

from src.agents.runtime.middleware import (
    build_compaction_middleware,
    build_tool_observation_middleware,
    build_trim_middleware,
    load_compaction_message_limits,
    load_max_turns,
)
from src.agents.runtime.prompts import load_system_prompt
from src.agents.runtime.provider import AgentProvider


async def agent_factory(
    checkpointer=None,
    system_prompt: SystemMessage | None = None,
    tools: collections.abc.Sequence[BaseTool] | None = None,
):
    """Build one agent with the discovered MCP tools and the present config."""
    model = AgentProvider().build_model("react")
    trigger_messages, keep_messages = load_compaction_message_limits()

    return create_agent(
        model=model,
        tools=list(tools) if tools is not None else [],
        system_prompt=system_prompt or load_system_prompt(),
        checkpointer=checkpointer,
        middleware=[
            build_compaction_middleware(model, trigger_messages, keep_messages),
            build_trim_middleware(load_max_turns()),
            # Innermost, so the reported call is the one as actually issued.
            build_tool_observation_middleware(),
        ],
    )