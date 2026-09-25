import pytest

from ai_ops.core.prompt.registry import get_prompt
from ai_ops.core.tools import ToolRegistry

def test_prompts_load():
    prompts = {
        tool_name: get_prompt(tool_name) 
        for tool_name in ToolRegistry.keys()
        if tool_name not in ('think', 'stop') # not registered tools 
    }

    for tool_name, prompt_template in prompts.items():
        assert prompt_template is not None and len(prompt_template) > 0, f"Empty prompt for {tool_name}"

    system = get_prompt("react")
    assert system is not None and len(system) > 0, "Empty system prompt"
