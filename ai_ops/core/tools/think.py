from typing import Annotated

from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool


_THINK_TOOL_DESCRIPTION = """Use this tool to reason through a problem before acting.
Call it when you need to analyze information, evaluate options, or plan next steps \
without executing any action. The thought is logged but has no effect on the environment."""


class ThinkRequest(BaseModel):
    thought: Annotated[str, Field(description="The thought to log.")]

class ThinkResult(BaseModel):
    pass

class ThinkTool(Tool[ThinkRequest, ThinkResult]):
    name = 'think'
    description = _THINK_TOOL_DESCRIPTION

    def __call__(self, tool_args: ThinkRequest) -> ThinkResult:
        return ThinkResult()

    @staticmethod
    def format_result(tool_result: ThinkResult) -> str:
        return ""
