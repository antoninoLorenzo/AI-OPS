from pydantic import BaseModel
from ai_ops.core.tools.base import Tool, Noop


class StopReason(BaseModel):
    reason: str
    

class StopTool(Tool[StopReason, Noop]):    
    name = "stop"
    description = "Call this tool when you reached the user objective."

    def __call__(self, _: StopReason) -> Noop:
        return Noop()

    @staticmethod
    def format_result(_: Noop) -> str:
        return ""
