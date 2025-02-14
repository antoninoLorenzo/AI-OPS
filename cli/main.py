import sys
import argparse
from urllib.parse import urlparse

from commands import Command, CommandSchema, CommandParameter
from app import App
from impl import (
    __help,
    __clear,
    __chat,
    __conversation_list,
    __conversation_new,
    __conversation_load,
    __conversation_save,
    __conversation_delete,
    __conversation_rename
)


COMMANDS = [
    # BASIC COMMANDS
    Command(
        command_schema=CommandSchema(command_name='help'),
        command_callback=__help
    ),
    Command(
        command_schema=CommandSchema(command_name='clear'),
        command_callback=__clear,
        requires_app_context=False
    ),
    # ASSISTANT INTERACTION
    Command(
        command_schema=CommandSchema(command_name='chat'),
        command_callback=__chat
    ),
    # CONVERSATION MANAGEMENT
    Command(
        command_schema=CommandSchema(command_name='conversation list'),
        command_callback=__conversation_list
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation new',
            command_parameters=[
                CommandParameter(parameter_name='conversation_name')
            ]
        ),
        command_callback=__conversation_new
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation load',
            command_parameters=[
                CommandParameter(parameter_name='conversation_id')
            ]
        ),
        command_callback=__conversation_load
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation rename',
            command_parameters=[
                CommandParameter(parameter_name='conversation_id'),
                CommandParameter(parameter_name='new_name')
            ]
        ),
        command_callback=__conversation_rename
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation save',
            command_parameters=[
                CommandParameter(parameter_name='conversation_id')
            ]
        ),
        command_callback=__conversation_save
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation delete',
            command_parameters=[
                CommandParameter(parameter_name='conversation_id')
            ]
        ),
        command_callback=__conversation_delete
    )
]


def validate_endpoint(api_endpoint: str):
    parsed_endpoint = urlparse(api_endpoint)
    protocol = parsed_endpoint.scheme

    if protocol not in ('http', 'https') or \
            parsed_endpoint.query:
        return None
    return api_endpoint


def main():
    startup_parser = argparse.ArgumentParser()

    startup_parser.add_argument(
        '--api',
        default='http://127.0.0.1:8000',
        help='The Agent API address',
        type=validate_endpoint
    )

    try:
        args = startup_parser.parse_args(sys.argv[1:])
        client = App(api_url=args.api, commands=COMMANDS)
        client.run()
    except KeyboardInterrupt:
        sys.exit()


if __name__ == '__main__':
    main()

