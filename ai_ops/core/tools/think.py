from typing import Annotated

from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool

_THINK_TOOL_DESCRIPTION = """Think before every action. Use this tool to reason about \
the current situation, evaluate what has already been done, decide what to do next, and \
avoid repeating previous steps. 

You MUST call this tool before calling any other tool. Use it to:
- Identify what you know about the target given the current findings.
- Identify the next logical step. Evaluate whether an action is necessary.
- Plan the approach before executing commands"""

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
        return "(no output)"
