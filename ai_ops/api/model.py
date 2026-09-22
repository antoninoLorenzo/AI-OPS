from pydantic import BaseModel

from ai_ops.core.runner import AgentMode


class StartAgentRequest(BaseModel):
    content: str
    mode: AgentMode


class ModelInfo(BaseModel):
    model_id: str
    provider: str
    max_context_length: int
