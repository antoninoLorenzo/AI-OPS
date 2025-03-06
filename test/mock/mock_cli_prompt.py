from typing import Union, List


class MockCLIInput:
    """mocks prompt_toolkit.PromptSession"""
    def __init__(self, commands: Union[str, List[str]]):
        # In the App.run REPL you can only exit the program with 'exit'.
        # If the test doesn't provide 'exit' it won't never do it. 
        # However monkeypatch can be called only once before app.run(), so we need to 
        # create an iterator that returns the commands to input.   
        #
        # bad design strikes again.
        if isinstance(commands, str):
            self._commands = iter([commands, 'exit'])
        else:
            self._commands = iter(commands)

    def prompt(self, *args, **kwargs):
        try:
            return next(self._commands)
        except StopIteration:
            return 'exit'

    def ask(self, *args, **kwargs):
        try:
            return next(self._commands)
        except StopIteration:
            return 'exit'

def build_input_mock(user_input, **kwargs):
    return MockCLIInput(user_input)

