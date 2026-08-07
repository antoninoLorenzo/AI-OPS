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
    replay_whiteboard,
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


@dataclass
class ToolContext:
    session_id: str
    model_id: str | None = None
    is_new_conversation: bool = True
    command_policies: Tuple[CommandAdmissionPolicy] = field(default_factory=list)
    # fucking benchmarks
    extra: Optional[Dict[str, Any]] = None


ToolFactory: TypeAlias = Callable[[ToolContext | None], Tool]


@dataclass(frozen=True)
class ToolSpec:
    """Single registry entry for a tool: the class and how to build it.

    The input/output models are derived from the concrete `Tool[In, Out]` base
    (see `Tool.get_input_schema`/`get_output_schema`) so they can't drift from
    the class definition.
    """
    tool: Type[Tool]
    factory: ToolFactory

    @property
    def input_type(self) -> Type[BaseModel]:
        return self.tool.get_input_schema()

    @property
    def output_type(self) -> Type[BaseModel]:
        return self.tool.get_output_schema()


ToolRegistry: Dict[str, ToolSpec] = {
    LoadSkill.name: ToolSpec(LoadSkill, lambda ctx: LoadSkill(model=ctx.model_id)),
    ThinkTool.name: ToolSpec(ThinkTool, lambda _: ThinkTool()),
    WhiteboardRead.name: ToolSpec(WhiteboardRead, lambda ctx: WhiteboardRead(
        whiteboard_id=ctx.session_id,
        new_whiteboard=ctx.is_new_conversation,
        model=ctx.model_id
    )),
    WhiteboardWrite.name: ToolSpec(WhiteboardWrite, lambda ctx: WhiteboardWrite(
        whiteboard_id=ctx.session_id,
        new_whiteboard=ctx.is_new_conversation,
        model=ctx.model_id
    )),
    WriteFile.name: ToolSpec(WriteFile, lambda ctx: WriteFile(
        working_directory=Path(AI_OPS_BASE_DIR / "workspace" / ctx.session_id)
    )),
    Terminal.name: ToolSpec(Terminal, lambda ctx: Terminal(
        session_id=ctx.session_id,
        working_directory=Path(AI_OPS_BASE_DIR / "workspace" / ctx.session_id),
        policies=ctx.command_policies
    )),
    # StopTool is an orchestration primitive (never auto-constructed via
    # config.tools) but is registered so its schemas resolve like any other.
    StopTool.name: ToolSpec(StopTool, lambda _: StopTool()),
}


def register_tool(tool: Type[Tool], factory: ToolFactory):
    global ToolRegistry

    get_logger(__name__).info(f"registering tool={tool.name}")
    ToolRegistry[tool.name] = ToolSpec(tool=tool, factory=factory)


def resolve_args_type(tool_name: str) -> Type[BaseModel] | None:
    spec = ToolRegistry.get(tool_name)
    return spec.input_type if spec is not None else None


def resolve_result_type(tool_name: str) -> Type[BaseModel] | None:
    spec = ToolRegistry.get(tool_name)
    return spec.output_type if spec is not None else None
