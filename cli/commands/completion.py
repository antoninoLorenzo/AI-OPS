from typing import List

from prompt_toolkit.completion import Completer, Completion

from cli.commands.model import CommandSchema, Command


class CommandCompleter(Completer):
    def __init__(self, commands: List[Command]):
        self.commands = commands

    def get_completions(self, document, complete_event):
        # Get word being completed
        word = document.get_word_before_cursor()
        
        # Return matching commands
        for command in self.commands:
            name = command.command_schema.command_name
            if name.startswith(word):
                yield Completion(name, start_position=-len(word))
