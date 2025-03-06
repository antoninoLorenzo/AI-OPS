import json
from pathlib import Path
from typing import Dict


__current = str(Path(__file__))
PROMPTS_BASE_PATH = (
    Path(__current[:__current.find('src')])
    / 'src'
    / 'agent'
    / 'prompts'
)


def load_prompts(architecture_name: str = 'default') -> Dict[str, str]:
    """
    :param architecture_name: name of the Assistant architecture

    :return: {prompt_name: prompt}
    """

    # open `prompts.json` to get prompts metadata
    with open(str(PROMPTS_BASE_PATH / 'prompts.json'), 'r', encoding='utf-8') as fp:
        prompts_metadata: dict = json.load(fp)
        available = list(prompts_metadata.keys())
        if not architecture_name in available:
            raise ValueError(
                f"Architecture {architecture_name} not found. Available: {available}"
            )

    # get the actual prompts
    architecture_prompts = {}
    for prompt_name, prompt_data in prompts_metadata[architecture_name].items():
        prompt_path = str(PROMPTS_BASE_PATH / 'templates' / prompt_data['path'])
        with open(prompt_path, 'r', encoding='utf-8') as fp:
            prompt = fp.read()
            architecture_prompts[prompt_name] = prompt

    return architecture_prompts

