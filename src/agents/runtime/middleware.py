from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain_core.messages import trim_messages

from src.core.config import settings


def load_max_messages() -> int:
    agent_cfg = settings.config_yaml.get("agent")
    if not isinstance(agent_cfg, dict):
        raise ValueError("Missing 'agent' section in config/settings.yaml")

    memory_cfg = agent_cfg.get("memory")
    if not isinstance(memory_cfg, dict):
        raise ValueError("Missing 'agent.memory' section in config/settings.yaml")

    max_messages = memory_cfg.get("max_messages")
    if isinstance(max_messages, bool) or not isinstance(max_messages, int) or max_messages <= 0:
        raise ValueError(
            "agent.memory.max_messages must be a positive integer in config/settings.yaml"
        )

    return max_messages


class TrimMessagesMiddleware(AgentMiddleware):
    """Trim the per-turn model input to the most recent ``max_messages`` messages.

    Wraps each model call with LangChain's native ``trim_messages`` (strategy ``last``,
    count-based) so only the inbound model request is trimmed — the stored checkpoint
    history is left untouched. Both the sync and async hooks are implemented because the
    runtime drives the agent through ``ainvoke``.
    """

    def __init__(self, max_messages: int) -> None:
        super().__init__()
        self._max_messages = max_messages

    def _trim(self, request: ModelRequest) -> ModelRequest:
        trimmed = trim_messages(
            request.messages,
            strategy="last",
            token_counter=len,
            max_tokens=self._max_messages,
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
        return request.override(messages=trimmed)

    def wrap_model_call(self, request, handler):
        return handler(self._trim(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._trim(request))


def build_trim_middleware(max_messages: int) -> AgentMiddleware:
    return TrimMessagesMiddleware(max_messages)
