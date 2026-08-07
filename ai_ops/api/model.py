from pydantic import BaseModel

from ai_ops.core.runner import AgentMode


class StartAgentRequest(BaseModel):
    content: str
    mode: AgentMode
