from typing import Union, List


class MockCLIInput:
    def __init__(self, commands: Union[str, List[str]]):
        # in the App.run REPL (using rich.Prompt) you can only exit the program with
        # 'exit'. If the test doesn't provide 'exit' it won't never do it. 
        # However monkeypatch can be called only once before app.run(), so we need to 
        # create an iterator that returns the commands to input.   
        #
        # bad design strikes again.
        if isinstance(commands, str):
            self._commands = iter([commands, 'exit'])
        else:
            self._commands = iter(commands)

    def prompt(self):
        # mocks prompt_toolkit.PromptSession
        return self.ask()

    def ask(self, *args, **kwargs):
        # mocks rich.Prompt
        try:
            return next(self._commands)
        except StopIteration:
            return 'exit'

def build_input_mock(user_input):
    return MockCLIInput(user_input)

