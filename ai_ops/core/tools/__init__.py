from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, Any, Type, TypeAlias, Callable

from pydantic import BaseModel

from ai_ops.config import AI_OPS_BASE_DIR
from ai_ops.core.tools.base import Tool, Noop, validate_tool_call
from ai_ops.core.tools.load_skill.skill import (
    LoadSkill, 
    LoadSkillRequest, 
    LoadSkillResult, 
    get_skill_registry
)
from ai_ops.core.tools.think import (
    ThinkTool, 
    ThinkRequest, 
    ThinkResult
)
from ai_ops.core.tools.whiteboard import (
    WhiteboardRead,
    WhiteboardWrite,
    WhiteboardReadRequest,
    WhiteboardResult,
    WhiteboardWriteRequest,
    get_whiteboard_store,
)
from ai_ops.core.tools.write_file import (
    WriteFile, 
    WriteFileInput, 
    WriteFileOutput
)
from ai_ops.core.tools.terminal import (
    Terminal, 
    TerminalRequest, 
    TerminalResult, 
    CommandAdmissionPolicy
)
from ai_ops.core.tools.stop import (
    StopTool, 
    StopReason
)
from ai_ops.core.log import get_logger


DEFAULT_TOOLS = [LoadSkill, ThinkTool, WhiteboardWrite, WriteFile, Terminal]

_TOOL_INPUT_TYPES = {
    LoadSkill.name: LoadSkillRequest,
    ThinkTool.name: ThinkResult,
    WhiteboardRead.name: WhiteboardReadRequest,
    WhiteboardWrite.name: WhiteboardWriteRequest,
    Terminal.name: TerminalRequest,
    WriteFile.name: WriteFileInput,
    StopTool.name: StopReason
}

_TOOL_OUTPUT_TYPES = {
    LoadSkill.name: LoadSkillResult,
    ThinkTool.name: ThinkResult,
    WhiteboardRead.name: WhiteboardResult,
    WhiteboardWrite.name: WhiteboardResult,
    Terminal.name: TerminalResult,
    WriteFile.name: WriteFileOutput,
    StopTool.name: Noop
}

ToolMap: Dict[str, Tool] = {
    LoadSkill.name: LoadSkill,
    ThinkTool.name: ThinkTool,
    WhiteboardRead.name: WhiteboardRead,
    WhiteboardWrite.name: WhiteboardWrite,
    WriteFile.name: WriteFile,
    Terminal.name: Terminal
}

@dataclass
class ToolContext:
    conversation_id: str
    model_id: str | None = None
    is_new_conversation: bool = True
    working_directory: str | None = None
    command_policies: Tuple[CommandAdmissionPolicy] = field(default_factory=list)
    # fucking benchmarks
    extra: Optional[Dict[str, Any]] = None


ToolFactory: TypeAlias = Callable[[ToolContext | None], Tool]

ToolRegistry: Dict[str, ToolFactory] = {
    LoadSkill.name: lambda ctx: LoadSkill(model=ctx.model_id),
    ThinkTool.name: lambda _: ThinkTool(),
    WhiteboardRead.name: lambda ctx: WhiteboardRead(
        whiteboard_id=ctx.conversation_id,
        new_whiteboard=ctx.is_new_conversation,
        model=ctx.model_id
    ),
    WhiteboardWrite.name: lambda ctx: WhiteboardWrite(
        whiteboard_id=ctx.conversation_id,
        new_whiteboard=ctx.is_new_conversation,
        model=ctx.model_id
    ),
    WriteFile.name: lambda ctx: WriteFile(
        working_directory=Path(AI_OPS_BASE_DIR / "workspace" / ctx.conversation_id)
    ),
    Terminal.name: lambda ctx: Terminal(
        conversation_id=ctx.conversation_id,
        working_directory=Path(AI_OPS_BASE_DIR / "workspace" / ctx.conversation_id),
        policies=ctx.command_policies
    )
}


def register_tool(
    tool: Type[Tool], 
    args_model: Type[BaseModel], 
    result_model: Type[BaseModel], 
    factory: ToolFactory
):
    global ToolRegistry
    global _TOOL_INPUT_TYPES
    global _TOOL_OUTPUT_TYPES

    get_logger(__name__).info(f"registering tool={tool.name}")
    ToolRegistry[tool.name] = factory
    ToolMap[tool.name] = Tool
    _TOOL_INPUT_TYPES[tool.name] = args_model
    _TOOL_OUTPUT_TYPES[tool.name] = result_model


def resolve_args_type(tool_name: str) -> Type[BaseModel] | None:
    return _TOOL_INPUT_TYPES.get(tool_name)


def resolve_result_type(tool_name: str) -> Type[BaseModel] | None:
    return _TOOL_OUTPUT_TYPES.get(tool_name)
