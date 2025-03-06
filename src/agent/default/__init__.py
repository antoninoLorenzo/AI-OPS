from pathlib import Path

from tool_parse import ToolRegistry

from src.core import LLM
from src.agent.utils import load_prompts
from src.agent.default.architecture import DefaultArchitecture


def init_default_architecture(
    llm: LLM,
    tool_registry: ToolRegistry
) -> DefaultArchitecture:
    return DefaultArchitecture(
        llm=llm,
        tools=tool_registry,
        prompts=load_prompts('default')
    )
