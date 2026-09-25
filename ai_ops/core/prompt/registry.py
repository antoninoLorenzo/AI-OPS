import functools

from ai_ops.core.prompt._prompts import (
    LOAD_SKILL,
    REACT,
    TERMINAL,
    WRITE_FILE,
    WRITE_WHITEBOARD,
)

_PROMPT_REGISTRY = {
    "react": REACT,
    "terminal": TERMINAL,
    "write_whiteboard": WRITE_WHITEBOARD,
    "load_skill": LOAD_SKILL,
    "write_file": WRITE_FILE,
}


def get_prompt(name: str, parameters: dict | None = None) -> str:
    """
    Templating:
    * Parameters is flattened to a dict[str, str]
    * If a parameter is not defined in the prompt it's ignored
    * If a parameter is defined in the prompt and isn't provided it's ignored
    
    raises ValueError: prompt `name` not in `_PROMPT_REGISTRY`
    """
    template = _PROMPT_REGISTRY.get(name)
    if template is None:
        raise ValueError(f"Prompt \"{name}\" not found in [{', '.join(_PROMPT_REGISTRY.keys())}]")

    if parameters is None:
        parameters = {}
    
    parameters = flatten(parameters)
    prompt = template.format_map(drop_missing(parameters))
    prompt = prompt.strip()

    return prompt


class drop_missing(dict):
    def __missing__(self, _):
        return ""

def flatten(d: dict) -> dict:
    return {
        k: flatten_helper(v)
        for k, v in d.items()
    }

@functools.singledispatch
def flatten_helper(o: str) -> str:
    return o

@flatten_helper.register
def _(o: int | float) -> str:
    return str(o)
    
@flatten_helper.register
def _(o: list) -> str:
    return '\n'.join(
        f"* {flatten_helper(item)}" 
        for item in o
    )

@flatten_helper.register
def _(o: dict) -> str:
    return '\n'.join((
        f"{k}:\n{flatten_helper(v)}" 
        for k, v in o.items()
    ))

