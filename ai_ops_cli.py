import os
import io
import sys
import argparse
from functools import partial
from typing import Callable, Any, List, Union, Iterable, Optional
from urllib.parse import urlparse

import httpx
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import InvalidResponse, Prompt
from rich.tree import Tree
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers import MarkdownLexer
from prompt_toolkit.keys import Keys
from pydantic import BaseModel, validate_call

VERSION = "0.0.0"


class CommandParameter(BaseModel):
    parameter_name: str
    parameter_value: Any = None
    required: bool = True


class CommandSchema(BaseModel):
    command_name: str
    command_parameters: List[CommandParameter] = []


class Command(BaseModel):
    command_schema: CommandSchema
    command_callback: Callable
    requires_app_context: bool = True


class ParserException(Exception):
    pass


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
        list_parser = conversation_subparsers.add_parser(
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
        load_parser.add_argument('conversation_id', type=str)

        rename_parser = conversation_subparsers.add_parser(
            'rename',
            exit_on_error=False,
            usage="conversation rename [conversation_id] [new_name]"
        )
        rename_parser.add_argument('conversation_id', type=str)
        rename_parser.add_argument('new_name', type=str)

        save_parser = conversation_subparsers.add_parser(
            'save',
            exit_on_error=False,
            usage="conversation save [conversation_id]"
        )
        save_parser.add_argument('conversation_id', type=str)

        delete_parser = conversation_subparsers.add_parser(
            'delete',
            exit_on_error=False,
            usage="conversation delete [conversation_id]"
        )
        delete_parser.add_argument('conversation_id', type=str)

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


class CommandRegistry:
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


class AppContext:

    def __init__(self, client: httpx.Client, console: Console):
        # most commands need either access to stdout or api client
        self.client = client
        self.console = console
        self.current_conversation_id: Optional[int] = None


class App:

    def __init__(
            self,
            api_url: str,
            commands: List[Command]
    ):
        self.__parser = CommandParser()
        self.__registry = CommandRegistry()
        self.__registry.register(commands)

        # health-check
        try:
            self.__context = AppContext(
                httpx.Client(base_url=api_url),
                Console()
            )

            response = self.__context.client.get('/ping', timeout=5)
            response.raise_for_status()
            self.__context.console.print(f"Backend: [blue]online[/]")
            self.__context.console.print(
                "[bold cyan]ℹ️  Tip:[/bold cyan] Press [bold green]Ctrl + ↓ (Down Arrow)[/bold green] to move to the next line while typing.",
                style="italic"
            )
        except Exception:
            self.__context.console.print('Backend: [red]offline[/]\n')
            sys.exit(-1)

    def run(self):
        while True:
            user_input = Prompt.ask(
                '[underline]ai-ops[/] >',
                console=self.__context.console,
                default='help',
                show_default=False
            )
            if user_input == 'exit':
                break

            # parse user input as command schema
            try:
                command_schema = self.__parser.parse(user_input)
            except ParserException as parse_err:
                self.__context.console.print(
                    f"[red]Error:[/] invalid command {user_input}: {parse_err}"
                )
                continue

            command: Command = self.__registry.search(command_schema)

            # bind context (if required) and parameters to command function
            if command.requires_app_context:
                command.command_callback = partial(
                    command.command_callback,
                    app_context=self.__context
                )
            parameters = {
                parameter.parameter_name: parameter.parameter_value
                for parameter
                in command.command_schema.command_parameters
            }

            command.command_callback(**parameters)


def build_input_multiline():
    """Creates an input prompt that can handle:
    - Multiline input
    - Copy-Paste
    - Press Enter to complete input
    - Press Ctrl+DownArrow to go next line"""
    bindings = KeyBindings()

    @bindings.add(Keys.ControlDown, eager=True)
    def _(event):
        event.current_buffer.newline()

    return PromptSession(
        "> ",
        key_bindings=bindings,
        lexer=PygmentsLexer(MarkdownLexer)
    )


def __help(app_context: AppContext):
    console = app_context.console
    console.print("[bold white]Basic Commands[/]")
    console.print("- [bold blue]help[/]   : Show available commands.")
    console.print("- [bold blue]clear[/]  : Clears the terminal.")
    console.print("- [bold blue]exit[/]   : Exit the program")

    console.print("\n[bold white]Assistant[/]")
    console.print("- [bold blue]chat[/]   : Open chat with the agent.")
    console.print("- [bold blue]back[/]   : Exit chat")

    console.print("\n[bold white]Conversation[/]")
    cmd = '[italic]conversation[/]'
    console.print(f"- {cmd} [bold blue]list[/]")
    console.print(f"- {cmd} [bold blue]new[/]    \\[name]")
    console.print(f"- {cmd} [bold blue]load[/]   \\[conversation id]")
    console.print(f"- {cmd} [bold blue]save[/]   \\[conversation id]")
    console.print(f"- {cmd} [bold blue]delete[/] \\[conversation id]")
    console.print(f"- {cmd} [bold blue]rename[/] \\[conversation id] \\[new name]")


def __clear():
    os.system(
        'cls' if os.name == 'nt'  # windows (its always him)
        else 'clear'  # unix
    )


def __chat(app_context: AppContext):
    client = app_context.client
    console = app_context.console

    if not app_context.current_conversation_id:
        __conversation_new(app_context, conversation_name='chat convo')
        return

    multiline_input = build_input_multiline()
    conversation_id = app_context.current_conversation_id
    while True:
        user_input = multiline_input.prompt()
        if user_input.startswith('back'):
            break

        with client.stream(
            method='POST',
            url=f'/conversations/{conversation_id}/chat',
            json={'message': user_input}
        ) as response_stream:
            console.print('[bold blue]Assistant[/]: ', end='')
            for c in response_stream.iter_text():
                console.print(c)


def __conversation_list(app_context: AppContext):
    client = app_context.client
    console = app_context.console
    try:
        response = client.get('/conversations')
        response.raise_for_status()
        conversations = response.json()
    except httpx.HTTPStatusError as status:
        console.print(f"[bold red]Error: [/] {status}")
        return

    if len(conversations) == 0:
        console.print(f"No Conversations.")
        return

    tree = Tree("Conversations:")
    for conversation in conversations:
        tree.add(f'[{conversation["conversation_id"]}]: {conversation["name"]}')
    console.print(tree)


def __conversation_new(app_context: AppContext, conversation_name: str):
    client = app_context.client
    console = app_context.console
    try:
        response = client.post(
            url='/conversations',
            params={'name': conversation_name}
        )
        response.raise_for_status()
        conversation = response.json()
    except httpx.HTTPError as status:
        console.print(f"[bold red]Error: [/] {status}")
        return

    console.print(f'[{conversation["conversation_id"]}]: {conversation["name"]}')
    # new conversation makes transition to chat
    app_context.current_conversation_id = conversation["conversation_id"]
    __chat(app_context)


def __conversation_load(app_context: AppContext, conversation_id: int):
    client = app_context.client
    console = app_context.console
    try:
        response = client.get(f'/conversations/{conversation_id}')
        response.raise_for_status()
        conversation = response.json()
    except httpx.HTTPError as status:
        console.print(f"[bold red]Error: [/] {status}")
        return

    for message in conversation['messages']:
        console.print(
            f"[bold blue]{message['role']}[/]: {message['content']}"
        )

    # load conversation makes transition to chat
    app_context.current_conversation_id = conversation["conversation_id"]
    __chat(app_context)


def __conversation_rename(app_context: AppContext, conversation_id: int, new_name: str):
    client = app_context.client
    console = app_context.console
    try:
        response = client.put(
            url=f'/conversations/{conversation_id}',
            params={'new_name': new_name}
        )
        response.raise_for_status()
    except httpx.HTTPError as status:
        console.print(f"[bold red]Error: [/] {status}")
        return


def __conversation_save(app_context: AppContext, conversation_id: int):
    client = app_context.client
    console = app_context.console
    try:
        response = client.put(f'/conversations/{conversation_id}')
        response.raise_for_status()
    except httpx.HTTPError as status:
        console.print(f"[bold red]Error: [/] {status}")
        return


def __conversation_delete(app_context: AppContext, conversation_id: int):
    client = app_context.client
    console = app_context.console
    try:
        response = client.delete(f'/conversations/{conversation_id}')
        response.raise_for_status()
    except httpx.HTTPError as status:
        console.print(f"[bold red]Error: [/] {status}")
        return


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
