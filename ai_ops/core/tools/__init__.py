from typing import Dict

from ai_ops.core.tools.base import Tool, ToolContext, ToolFactory, validate_tool_call
from ai_ops.core.tools.load_skill.skill import LoadSkill, get_skill_registry
from ai_ops.core.tools.whiteboard import Whiteboard, get_whiteboard_store
from ai_ops.core.utils import get_logger

ToolRegistry: Dict[str, ToolFactory] = {
    "load_skill": lambda _: LoadSkill(),
    "whiteboard": lambda ctx: Whiteboard(whiteboard_id=ctx.conversation_id)
}


def register_tool(name: str, factory):
    global ToolRegistry
    get_logger(__name__).info(f"registering tool={name}")
    ToolRegistry[name] = factory
