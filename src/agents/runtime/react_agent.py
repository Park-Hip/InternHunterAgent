from langchain.messages import HumanMessage
from src.agents.tracing.langfuse import build_langfuse_config, get_langfuse_handler, get_langfuse_client
from src.agents.runtime.factory import agent_factory

class AgentRuntime:
    def __init__(self, agent=None):
        self.agent=agent or agent_factory()

    async def ainvoke(self, query: str, user_id: str = None, session_id: str = None):
        langfuse_handler = get_langfuse_handler()
        config = build_langfuse_config(session_id=session_id, user_id=user_id)
        messages = self._build_messages(query)
        response = await self.agent.ainvoke(
            messages,
            config=config
        )
        answer = response['messages'][-1].content
        trace_id = langfuse_handler.last_trace_id
        get_langfuse_client().flush()

        return {
            "answer": answer,
            "trace_id": trace_id,
        }
    
    def _build_messages(self, query: str) -> list:
        return {"messages": [HumanMessage(content=query)]}
    
runtime = AgentRuntime(agent=agent_factory())
