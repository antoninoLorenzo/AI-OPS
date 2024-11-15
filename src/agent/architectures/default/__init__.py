import json
from pathlib import Path

from tool_parse import ToolRegistry

from src.core import LLM
from src.agent.architectures.default.architecture import DefaultArchitecture


def init_default_architecture(
    llm: LLM,
    tool_registry: ToolRegistry
) -> DefaultArchitecture:

    with open(
        str(Path(__file__).parent / 'prompts.json'),
        encoding='utf-8'
    ) as fp:
        prompts = json.load(fp)

    return DefaultArchitecture(
        llm=llm,
        tools=tool_registry,
        router_prompt=prompts['router']['content'],
        general_prompt=prompts['general']['content'],
        reasoning_prompt=prompts['reasoning']['content'],
        tool_prompt=prompts['tool']['content']
    )
