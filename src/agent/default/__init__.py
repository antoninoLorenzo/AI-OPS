from pathlib import Path

from tool_parse import ToolRegistry

from src.core import LLM
from src.agent.utils import load_prompts
from src.agent.default.architecture import Default


def init_default_architecture(
    llm: LLM,
    tool_registry: ToolRegistry
) -> Default:
    return Default(
        llm=llm,
        tool_registry=tool_registry,
        prompts=load_prompts('default')
    )
