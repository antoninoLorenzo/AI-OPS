"""
Loads the prompts for the entire system, prompts are organized in a
hierarchical structure, they are grouped by model, version, objective,
then divided in system prompts (instructions) and user prompts.
"""
import json
from pathlib import Path

PROMPT_VERSION = "0.0"
PROMPTS_PATH = str(Path(Path(__file__).parent / 'prompts.json'))
with open(PROMPTS_PATH, 'r', encoding='utf-8') as fp:
    PROMPTS = json.load(fp)
