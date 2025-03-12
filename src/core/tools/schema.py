from typing import Dict, Any
from pydantic import BaseModel


JSON_REGEX = r"\s*({[^}]*(?:{[^}]*})*[^}]*}|\[[^\]]*(?:\[[^\]]*\])*[^\]]*\])\s*$"


class ToolCall(BaseModel):
    name: str
    parameters: Dict[str, Any]

