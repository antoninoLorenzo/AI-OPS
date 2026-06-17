from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, Any, TypeAlias, Callable

from ai_ops.config import AI_OPS_BASE_DIR
from ai_ops.core.tools.base import Tool, validate_tool_call
from ai_ops.core.tools.load_skill.skill import LoadSkill, get_skill_registry
from ai_ops.core.tools.think import ThinkTool
from ai_ops.core.tools.whiteboard import (
    WhiteboardRead,
    WhiteboardWrite,
    get_whiteboard_store,
)
from ai_ops.core.tools.write_file import WriteFile
from ai_ops.core.tools.terminal import Terminal, CommandAdmissionPolicy
from ai_ops.core.log import get_logger


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


def register_tool(name: str, factory):
    global ToolRegistry
    get_logger(__name__).info(f"registering tool={name}")
    ToolRegistry[name] = factory
