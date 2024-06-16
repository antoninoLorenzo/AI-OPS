import platform

from src.agent.tools.base import Tool

CUR_OS = platform.system()


class Terminal(Tool):
    """The standard tool to execute commands."""

    def __init__(self):
        self.name = 'terminal'
        self.tool_description = f"""Used to interact with {CUR_OS} OS or run programs from command line."""

        self.args_description = """Takes as input the command to execute."""

        self.examples = """<THOUGHT>I need to know the current folder content</THOUGHT>
    <TOOL>terminal ls -la</TOOL> /STOP
    
    <THOUGHT>I need to create a directory example_directory</THOUGHT>
    <TOOL>terminal mkdir example_directory</TOOL> /STOP
    """