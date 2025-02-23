import io
import sys
import argparse

from cli.commands.model import CommandParameter, CommandSchema, ParserException


class CommandParser:
    def __init__(self):
        # base commands
        self.base_parser = argparse.ArgumentParser(exit_on_error=False)
        self.base_parser.add_argument(
            'command',
            choices=['help', 'clear', 'exit', 'chat', 'conversation']
        )

        # conversation commands
        self.conversation_commands = [
            'list',
            'new',
            'load',
            'rename',
            'save',
            'delete'
        ]
        self.conversation_parser = argparse.ArgumentParser(exit_on_error=False)
        conversation_subparsers = self.conversation_parser.add_subparsers(
            dest='subcommand',
            required=True
        )

        # that's so manual
        _ = conversation_subparsers.add_parser(
            'list',
            exit_on_error=False,
            usage="conversation list"
        )

        new_parser = conversation_subparsers.add_parser(
            'new',
            exit_on_error=False,
            usage="conversation new [conversation_name]"
        )
        new_parser.add_argument('conversation_name', type=str)

        load_parser = conversation_subparsers.add_parser(
            'load',
            exit_on_error=False,
            usage="conversation load [conversation_id]"
        )
        load_parser.add_argument('conversation_id', type=int)

        rename_parser = conversation_subparsers.add_parser(
            'rename',
            exit_on_error=False,
            usage="conversation rename [conversation_id] [new_name]"
        )
        rename_parser.add_argument('conversation_id', type=int)
        rename_parser.add_argument('new_name', type=str)

        save_parser = conversation_subparsers.add_parser(
            'save',
            exit_on_error=False,
            usage="conversation save [conversation_id]"
        )
        save_parser.add_argument('conversation_id', type=int)

        delete_parser = conversation_subparsers.add_parser(
            'delete',
            exit_on_error=False,
            usage="conversation delete [conversation_id]"
        )
        delete_parser.add_argument('conversation_id', type=int)

    def parse(self, user_input: str) -> CommandSchema:
        try:
            # parse_known_args returns the namespace corresponding to the arguments
            # specified in the `base_parser`, any other argument is ignored and
            # returned in the subcommand list, if present, otherwise the list is empty.
            base_command, subcommand = self.base_parser.parse_known_args(user_input.split())
            command_schema = {'command_name': base_command.command}

            if base_command.command == "conversation":
                if not subcommand:
                    usage = self.conversation_parser.format_usage().strip()
                    raise ParserException(f"conversation: required {usage}")

                # argparse prints errors to stderr, instead we need to capture
                # them and print in the AppContext.console
                stderr_capture = io.StringIO()
                original_stderr = sys.stderr
                sys.stderr = stderr_capture
                try:
                    conversation_args = vars(self.conversation_parser.parse_args(subcommand))
                except SystemExit:
                    error_message = stderr_capture.getvalue().strip()
                    raise ParserException(error_message)
                finally:
                    sys.stderr = original_stderr

                command_schema['command_name'] += f" {conversation_args.pop('subcommand')}"
                parameters = []
                for param, value in conversation_args.items():
                    parameters.append(
                        CommandParameter(
                            parameter_name=param,
                            parameter_value=value
                        )
                    )
                command_schema['command_parameters'] = parameters

            return CommandSchema(**command_schema)
        except (argparse.ArgumentError, SystemExit) as arg_err:
            raise ParserException(str(arg_err))
