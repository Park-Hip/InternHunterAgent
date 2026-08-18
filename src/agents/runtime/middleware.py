from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain_core.messages import HumanMessage

from src.core.config import settings


def load_max_turns() -> int:
    agent_cfg = settings.config_yaml.get("agent")
    if not isinstance(agent_cfg, dict):
        raise ValueError("Missing 'agent' section in config/settings.yaml")

    memory_cfg = agent_cfg.get("memory")
    if not isinstance(memory_cfg, dict):
        raise ValueError("Missing 'agent.memory' section in config/settings.yaml")

    max_turns = memory_cfg.get("max_turns")
    if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns <= 0:
        raise ValueError(
            "agent.memory.max_turns must be a positive integer in config/settings.yaml"
        )

    return max_turns


class TrimTurnsMiddleware(AgentMiddleware):
    """Trim the per-turn model input to the most recent complete user turns.

    A turn begins with a human message and includes every later message up to the next
    human message. Only the inbound model request is trimmed, leaving stored checkpoint
    history untouched. Both sync and async hooks are implemented because the runtime
    drives the agent through ``ainvoke``.
    """

    def __init__(self, max_turns: int) -> None:
        super().__init__()
        self._max_turns = max_turns

    def _trim(self, request: ModelRequest) -> ModelRequest:
        turn_starts = [
            index
            for index, message in enumerate(request.messages)
            if isinstance(message, HumanMessage)
        ]
        if len(turn_starts) <= self._max_turns:
            return request

        return request.override(messages=request.messages[turn_starts[-self._max_turns] :])

    def wrap_model_call(self, request, handler):
        return handler(self._trim(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._trim(request))


def build_trim_middleware(max_turns: int) -> AgentMiddleware:
    return TrimTurnsMiddleware(max_turns)
