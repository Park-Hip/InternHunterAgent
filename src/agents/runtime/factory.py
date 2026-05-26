from langchain.agents import create_agent
from src.agents.runtime.provider import AgentProvider
from src.agents.tools.time import get_current_time
from src.agents.runtime.prompts import load_system_prompt
from src.core.config import settings

def agent_factory():
    return create_agent(
        model=AgentProvider().build_model(),  
        tools=[get_current_time],
        system_prompt=load_system_prompt(),
        
    )