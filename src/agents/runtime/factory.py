from langchain.agents import create_agent
from src.agents.runtime.provider import AgentProvider
from src.agents.runtime.middleware import (
    build_compaction_middleware,
    build_trim_middleware,
    load_compaction_message_limits,
    load_max_turns,
)
from src.agents.tools.query_clean_jobs import query_clean_jobs
from src.agents.tools.get_job_details import get_job_details
from src.agents.runtime.prompts import load_system_prompt

def agent_factory(checkpointer=None):
    model = AgentProvider().build_model("react")
    trigger_messages, keep_messages = load_compaction_message_limits()

    return create_agent(
        model=model,
        tools=[query_clean_jobs, get_job_details],
        system_prompt=load_system_prompt(),
        checkpointer=checkpointer,
        middleware=[
            build_compaction_middleware(model, trigger_messages, keep_messages),
            build_trim_middleware(load_max_turns()),
        ],
    )
