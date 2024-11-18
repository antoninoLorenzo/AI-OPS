import json
from pathlib import Path

from tool_parse import ToolRegistry

from src.core import LLM
from src.agent.architectures.default.architecture import DefaultArchitecture


def init_default_architecture(
    llm: LLM,
    tool_registry: ToolRegistry
) -> DefaultArchitecture:
    prompt_path = Path(__file__).parent / 'prompts'

    with open(str(prompt_path / 'router'), encoding='utf-8') as fp:
        router = json.load(fp)

    with open(str(prompt_path / 'general'), encoding='utf-8') as fp:
        general = json.load(fp)

    with open(str(prompt_path / 'reasoning'), encoding='utf-8') as fp:
        reasoning = json.load(fp)

    with open(str(prompt_path / 'tool'), encoding='utf-8') as fp:
        tool = json.load(fp)

    return DefaultArchitecture(
        llm=llm,
        tools=tool_registry,
        router_prompt=router,
        general_prompt=general,
        reasoning_prompt=reasoning,
        tool_prompt=tool
    )
