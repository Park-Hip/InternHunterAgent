from langchain.agents import create_agent
from src.agents.runtime.provider import AgentProvider
from src.agents.runtime.middleware import build_trim_middleware, load_max_messages
from src.agents.tools.time import get_current_time
from src.agents.tools.query_clean_jobs import query_clean_jobs
from src.agents.runtime.prompts import load_system_prompt
from src.core.config import settings

def agent_factory(checkpointer=None):
    return create_agent(
        model=AgentProvider().build_model(),
        tools=[get_current_time, query_clean_jobs],
        system_prompt=load_system_prompt(),
        checkpointer=checkpointer,
        middleware=[build_trim_middleware(load_max_messages())],
    )