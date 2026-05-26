from src.agents.runtime.factory import agent_factory
from langchain.messages import HumanMessage

class AgentRuntime:
    def __init__(self, agent=None):
        self.agent=agent or agent_factory()

    async def ainvoke(self, query: str):
        messages = self._build_messages(query)
        response = await self.agent.ainvoke(messages)
        answer = response['messages'][-1].content

        return answer
    
    def _build_messages(self, query: str) -> list:
        return {"messages": [HumanMessage(content=query)]}
