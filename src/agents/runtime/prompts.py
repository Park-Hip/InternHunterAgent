from langchain.messages import SystemMessage
from src.core.config import settings

def load_system_prompt():
    prompt = settings.prompts_yaml['prompts']["system_prompt"]
    return SystemMessage(content=prompt)
    