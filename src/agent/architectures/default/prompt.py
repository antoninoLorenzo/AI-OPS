from pydantic import BaseModel, validate_call


class DefaultPrompt(BaseModel):
    router_prompt: str
    general_prompt: str
    reasoning_prompt: str
    tool_prompt: str
