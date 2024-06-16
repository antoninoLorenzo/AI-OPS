import platform
from src.agent.tools.base import Tool


class Terminal(Tool):

    def __init__(self):
        self.name = 'terminal'
        self.tool_description = f"""Used to interact with the OS or run programs from command line. The current OS is {platform.system()}"""

        self.args_description = """Takes as input the command to execute."""

        self.examples = """<THOUGHT>I need to know the current folder content</THOUGHT>
    <TOOL>terminal ls -la</TOOL> /STOP
    
    <THOUGHT>I need to create a directory example_directory</THOUGHT>
    <TOOL>terminal mkdir example_directory</TOOL> /STOP
    """