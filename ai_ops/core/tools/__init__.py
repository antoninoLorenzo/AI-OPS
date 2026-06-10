from typing import Dict

from ai_ops.core.tools.base import Tool, ToolContext, ToolFactory, validate_tool_call
from ai_ops.core.tools.load_skill.skill import LoadSkill, get_skill_registry
from ai_ops.core.tools.think import ThinkTool
from ai_ops.core.tools.whiteboard import (
    WhiteboardRead,
    WhiteboardWrite,
    get_whiteboard_store,
)
from ai_ops.core.tools.terminal import Terminal, CommandAdmissionPolicy
from ai_ops.core.log import get_logger

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
    Terminal.name: lambda ctx: Terminal(
        conversation_id=ctx.conversation_id,
        working_directory=ctx.working_directory
        # TODO: how do I make command policies go from AgentConfig there?
        # `ToolContext` is defined in tools/base.py, I can't import `CommandAdmissionPolicy` 
        # there without having a circular import...
    )
}


def register_tool(name: str, factory):
    global ToolRegistry
    get_logger(__name__).info(f"registering tool={name}")
    ToolRegistry[name] = factory
