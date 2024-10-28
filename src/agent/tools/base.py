"""Tool base class"""
import json
import platform
import queue
import subprocess
import threading
import time


class Tool:
    # TODO: remove, deprecating specific tool integration
    """Represents a Penetration Testing Tool"""
    name: str
    tool_description: str
    args_description: str
    use_case: str = ''

    def __init__(
            self,
            name: str,
            tool_description: str,
            args_description: str,
            use_case: str
    ):
        self.name = name
        self.tool_description = tool_description
        self.args_description = args_description
        self.use_case = use_case

    @staticmethod
    def load_tool(path: str):
        """Get tool description from json file"""
        # TODO: refactor schema validation in another method
        with open(path, 'r', encoding='utf-8') as fp:
            tool_data: dict = json.load(fp)
            keys = ['name', 'tool_description', 'args_description', 'use_case']

            if not isinstance(tool_data, dict):
                raise TypeError(
                    f"Wrong format for {path}.\n"
                    f"Expected: dict\n"
                    f"Got: {type(tool_data)}."
                )

            valid_keys = False in [key in keys for key in tool_data.keys()]
            if len(tool_data) != 4 or valid_keys:
                raise ValueError(f"Wrong format at {path}: invalid keys.")

            name = tool_data['name']
            tool_description = ''.join(tool_data['tool_description'])
            # in case args_description is provided as string instead
            # of string list it still works: ''.join(string) returns string
            args_description = ''.join(tool_data['args_description'])
            use_case = tool_data['use_case']

            if not (name and tool_description and args_description):
                raise ValueError(f"Wrong format at {path}\nFound empty values")

            return Tool(name, tool_description, args_description, use_case)

    def run(*args):
        """Execute a tool"""
        raise NotImplementedError

    def get_documentation(self):
        """Used to provide documentation for the Agent LLM"""
        return f"""
Tool: {self.name}
Description: 
    {self.tool_description}
Arguments:
    {self.args_description}          
"""


class Terminal:
    """A stateful terminal implementation"""
    name: str = 'Terminal'
    tool_description: str = f'A {platform.system()} Terminal.'
    args_description: str = f'Takes as argument the string representing the command to execute.'
    use_case: str = 'Terminal Usage'
    SHELLS = {
        'Linux': '/bin/sh',
        'Windows': 'cmd.exe'  # TODO: change with full path
    }

    def __init__(self):
        self.proc = subprocess.Popen(
            self.SHELLS[platform.system()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )
        self.reader_output = queue.Queue()

        reader = threading.Thread(target=self.__fetch_output)
        reader.daemon = True
        reader.start()

    def run(self, command: str):
        """Interface to terminal"""
        if not isinstance(command, str):
            raise ValueError(f"command should be str, found '{type(command)}'.")
        self.__exec(command)
        return ''.join(self.read())

    def __exec(self, command: str):
        """Write a command to the terminal standard input"""
        self.proc.stdin.write(f'{command}\n')
        self.proc.stdin.flush()
        time.sleep(0.2)

    def __fetch_output(self):
        """Read the output from terminal standard output"""
        if self.proc.stdout:
            for line in iter(self.proc.stdout.readline, ''):
                self.reader_output.put(line)

            # TODO: handle stderr, not working
            # for line in iter(proc.stderr.readline, ''):
            #     stdout.put(line)
        else:
            print(f'{self.proc.stdout}')

    def read(self):
        """A generator that returns single lines from the terminal output"""
        # wait for output to be added into queue
        while self.reader_output.empty():
            pass

        # read from queue
        while not self.reader_output.empty():
            yield self.reader_output.get()

    def close(self):
        """Clean up the subprocess"""
        if self.proc:
            self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait()

    def __del__(self):
        self.close()


if __name__ == "__main__":
    term = Terminal()
    print(term.run('ls -la'))
    print(term.run('cd ..'))
    print(term.run('ls -la'))
    term.close()
