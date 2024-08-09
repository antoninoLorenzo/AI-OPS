"""Tool base class"""
import json
import subprocess


class Tool:
    """Represents a Penetration Testing Tool"""
    name: str
    tool_description: str
    args_description: str

    def __init__(self, name: str, tool_description: str, args_description: str):
        self.name = name
        self.tool_description = tool_description
        self.args_description = args_description

    @staticmethod
    def load_tool(path: str):
        """Get tool description from json file"""
        with open(path, 'r', encoding='utf-8') as fp:
            tool_data = json.load(fp)
            name = tool_data['name']
            tool_description = ''.join(tool_data['tool_description'])
            args_description = ''.join(tool_data['args_description'])

            return Tool(name, tool_description, args_description)

    @staticmethod
    def run(*args):
        """Execute a tool"""
        if not isinstance(args[0], str):
            raise ValueError(f'Argument must be a string found {type(args[0])}')

        command = args[0].encode('utf-8').decode('utf-8')
        arguments = command.split()
        result = subprocess.run(arguments, capture_output=True, check=False)

        stdout = result.stdout.decode('utf-8', errors='replace')
        stderr = result.stderr.decode('utf-8', errors='replace')

        if len(stderr) > 0:
            return f'{stdout}\n{stderr}'
        return stdout

    def get_documentation(self):
        """Used to provide documentation for the Agent LLM"""
        return f"""
Tool: {self.name}
Description: 
    {self.tool_description}
Arguments:
    {self.args_description}          
"""
