"""Tool package"""
from pathlib import Path

from src.agent.tools.base import Tool

TOOLS_PATH = Path(Path.home() / '.aiops' / 'tools')
if not TOOLS_PATH.exists():
    TOOLS_PATH.mkdir(parents=True, exist_ok=True)

TOOLS = []
for path in TOOLS_PATH.iterdir():
    tool = Tool.load_tool(str(path))
    TOOLS.append(tool)
