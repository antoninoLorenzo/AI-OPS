from typing import List, Union, Iterable, Optional

from cli.commands.model import CommandSchema, Command


class CommandRegistry:
    """Store of commands, used to map CommandSchema with its implementation."""
    def __init__(self):
        self.__commands: List[Command] = []

    def register(
            self,
            commands: Union[Command, Iterable[Command]],
    ):
        if isinstance(commands, Iterable):
            self.__commands.extend(commands)
        else:
            self.__commands.append(commands)

    def search(self, command_schema: CommandSchema) -> Optional[Command]:
        """
        :param command_schema: command parsed by CommandParser
        :return: the Command instance to execute
        """
        command = None
        for cmd in self.__commands:
            if command_schema.command_name == cmd.command_schema.command_name:
                command = Command(
                    command_schema=command_schema,  # the schema contains parameters !!!
                    command_callback=cmd.command_callback,
                    requires_app_context=cmd.requires_app_context
                )
                break
        return command
