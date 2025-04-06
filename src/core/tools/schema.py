from typing import Dict, Any
from pydantic import BaseModel


class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]

