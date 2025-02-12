import os
import io
import sys
import json
import argparse
from enum import StrEnum
from functools import partial
from typing import Callable, Any, Dict, Type, Generator, List, Union, Iterable, Optional
from urllib.parse import urlparse

import httpx
import requests
from requests.exceptions import ConnectionError, HTTPError
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


class RequestMethod(StrEnum):
    GET = 'get'
    POST = 'post'
    PUT = 'put'
    DELETE = 'delete'


class RequestEndpoint(BaseModel):
    method: RequestMethod
    path: str


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
    request_endpoint: Optional[RequestEndpoint] = None
    requires_app_context: bool = False


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
                    command_schema=command_schema,                  # the schema contains parameters !!!
                    command_callback=cmd.command_callback,
                    request_endpoint=cmd.request_endpoint,
                    requires_app_context=cmd.requires_app_context
                )
                break
        return command


class AppContext:

    def __init__(self, client: httpx.Client, console: Console):
        # most commands need either access to stdout or api client
        self.client = client
        self.console = console


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


def __help(app_context: AppContext):
    # Basic Commands
    app_context.console.print("[bold white]Basic Commands[/]")
    app_context.console.print("- [bold blue]help[/]   : Show available commands.")
    app_context.console.print("- [bold blue]clear[/]  : Clears the terminal.")
    app_context.console.print("- [bold blue]exit[/]   : Exit the program")

    # Agent Related
    app_context.console.print("\n[bold white]Agent Related[/]")
    app_context.console.print("- [bold blue]chat[/]   : Open chat with the agent.")
    app_context.console.print("- [bold blue]back[/]   : Exit chat")

    # Session Related
    app_context.console.print("\n[bold white]Session Related[/]")
    app_context.console.print("- [bold blue]new[/]             : Create a new session.")
    app_context.console.print("- [bold blue]save[/]            : Save the current session.")
    app_context.console.print("- [bold blue]load[/]            : Opens a session.")
    app_context.console.print("- [bold blue]delete[/]          : Delete the current session from persistent sessions.")
    app_context.console.print("- [bold blue]rename[/]          : Rename the current session.")
    app_context.console.print("- [bold blue]list sessions[/]   : Show the saved sessions.")


def __clear():
    os.system(
        'cls' if os.name == 'nt'  # windows (its always him)
        else 'clear'  # unix
    )


COMMANDS = [
    # BASIC COMMANDS
    Command(
        command_schema=CommandSchema(command_name='help'),
        command_callback=__help,
        requires_app_context=True
    ),
    Command(
        command_schema=CommandSchema(command_name='clear'),
        command_callback=__clear
    ),
    # ASSISTANT INTERACTION
    Command(
        command_schema=CommandSchema(command_name='chat'),
        command_callback=lambda: print('chat')
    ),
    # CONVERSATION MANAGEMENT
    Command(
        command_schema=CommandSchema(command_name='conversation list'),
        command_callback=lambda: print('conversation list')
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation new',
            command_parameters=[
                CommandParameter(parameter_name='conversation_name')
            ]
        ),
        command_callback=lambda conversation_name: print(f'new conversation: {conversation_name}')
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation load',
            command_parameters=[
                CommandParameter(parameter_name='conversation_id')
            ]
        ),
        command_callback=lambda conversation_id: print(f'loaded conversation: {conversation_id}')
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation rename',
            command_parameters=[
                CommandParameter(parameter_name='conversation_id'),
                CommandParameter(parameter_name='new_name')
            ]
        ),
        command_callback=lambda conversation_id, new_name: print(f'renaming {conversation_id} as {new_name}')
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation save',
            command_parameters=[
                CommandParameter(parameter_name='conversation_id')
            ]
        ),
        command_callback=lambda conversation_id: print(f'saving conversation: {conversation_id}')
    ),
    Command(
        command_schema=CommandSchema(
            command_name='conversation delete',
            command_parameters=[
                CommandParameter(parameter_name='conversation_id')
            ]
        ),
        command_callback=lambda conversation_id: print(f'deleting conversation: {conversation_id}')
    )
]

# --- OLD STUFF

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


class AgentClient:
    """Client for Agent API"""

    def __init__(self, api_url: str = 'http://127.0.0.1:8000'):
        self.api_url = api_url
        self.client = requests.Session()
        self.console = Console()
        self.current_session = {'sid': 0, 'name': 'Undefined'}
        self.commands = {
            'help': self.help,
            'clear': AgentClient.clear_terminal,
            'exit': '',

            'chat': self.chat,

            'new': self.new_session,
            'save': self.save_session,
            'delete': self.delete_session,
            'rename': self.rename_session,
            'list sessions': self.list_sessions,
            'load': self.load_session,

            # 'list collections': self.list_collections,
            # 'create collection': self.create_collection
        }
        self.multiline_input = build_input_multiline()

        self.console.print("[bold blue]ai-ops-cli[/] (beta) starting.")
        try:
            response = self.client.get(f'{self.api_url}/ping', timeout=5)
            response.raise_for_status()
            self.console.print(f"Backend: [blue]online[/]")
            self.console.print(
                "[bold cyan]ℹ️  Tip:[/bold cyan] Press [bold green]Ctrl + ↓ (Down Arrow)[/bold green] to move to the next line while typing.",
                style="italic"
            )
        except (ConnectionError, HTTPError):
            self.console.print('Backend: [red]offline[/]')
            sys.exit(-1)
        self.console.print()

    def run(self):
        """Runs the main loop of the client"""
        while True:
            user_input = None
            try:
                user_input = Prompt.ask(
                    '[underline]ai-ops[/] >',
                    console=self.console,
                    choices=list(self.commands.keys()),
                    default='help',
                    show_choices=False,
                    show_default=False
                )
            except InvalidResponse:
                self.console.print('Invalid command', style='bold red')
                self.commands['help']()

            if user_input == 'exit':
                break

            self.commands[user_input]()

    def new_session(self):
        """Creates a new session and opens the related chat"""
        session_name = Prompt.ask(
            'Session Name',
            console=self.console
        )

        response = self.client.post(
            f'{self.api_url}/sessions',
            params={'name': session_name}
        )
        response.raise_for_status()

        self.current_session = {'sid': response.json()['sid'], 'name': session_name}
        self.chat(print_name=True)

    def save_session(self):
        """Save the current session"""
        response = self.client.put(
            f'{self.api_url}/sessions/{self.current_session["sid"]}/chat'
        )
        if response.status_code != 200:
            self.console.print(f'[!] Failed: {response.status_code}')
        else:
            self.console.print(f'[+] Saved')

    def rename_session(self):
        """Renames the current session"""
        session_name = Prompt.ask(
            'New Name',
            console=self.console
        )

        response = self.client.put(
            f'{self.api_url}/sessions/{self.current_session["sid"]}',
            params={'new_name': str(session_name)}
        )
        response.raise_for_status()
        self.current_session['name'] = str(session_name)
        self.chat(print_name=True)

    def delete_session(self):
        """Deletes a session"""
        session_id = Prompt.ask(
            'Enter session ID',
            console=self.console
        )
        if not session_id.isdigit():
            self.console.print('[-] Not a number', style='bold red')

        response = self.client.delete(
            f'{self.api_url}/sessions/{session_id}'
        )
        response.raise_for_status()
        body = response.json()
        self.console.print(f'[{"+" if body["success"] else "-"}] {body["message"]}')

    def list_sessions(self):
        """List all sessions"""
        response = self.client.get(
            f'{self.api_url}/sessions'
        )
        response.raise_for_status()
        body = response.json()
        if len(body) == 0:
            self.console.print('[+] No sessions found')
        else:
            tree = Tree("[+] Available Sessions:")
            for session in body:
                tree.add(f'({session["sid"]}) {session["name"]}')
            self.console.print(tree)

    def load_session(self):
        """Opens an existing session"""
        session_id = Prompt.ask(
            'Enter session ID',
            console=self.console
        )
        if not session_id.isdigit():
            self.console.print('[-] Not a number', style='bold red')
            self.load_session()

        response = self.client.get(
            f'{self.api_url}/sessions/{int(session_id)}/chat',
        )
        response.raise_for_status()

        body = response.json()
        if 'success' in body:
            self.console.print(f'No session for {session_id}', style='red')

        sid = body['sid']
        name = body['name']
        self.current_session = {'sid': sid, 'name': name}
        self.console.print(f'({sid}) [bold blue]{name}[/]')

        body['messages'] = body['messages'][1:]  # exclude system message
        for msg in body['messages']:
            self.console.print(f'[bold white]{msg["role"]}[/]: {msg["content"]}\n')
        self.chat(print_name=False)

    def chat(self, print_name=True):
        """Opens a chat with the Agent"""
        sid = self.current_session["sid"]
        query_url = f'{self.api_url}/sessions/{sid}/chat'

        if print_name:
            name = self.current_session["name"]
            self.console.print(f'({sid}) [bold blue]{name}[/]')

        while True:
            q = self.multiline_input.prompt()
            if q.startswith('back'):
                break
            self.__generate_response(query_url, q)

    def __generate_response(self, url: str, query: str):
        try:
            with self.client.post(
                    url,
                    json={'query': query},
                    headers=None,
                    stream=True
            ) as resp:
                resp.raise_for_status()

                response_text = '**Assistant**: '
                with Live(console=self.console, refresh_per_second=10) as live:
                    live.update(Markdown(response_text))
                    for chunk in resp.iter_content(decode_unicode=True):
                        if chunk:
                            try:
                                response_text += chunk.decode('utf-8')
                            except UnicodeDecodeError:
                                pass
                            live.update(Markdown(response_text))

                print()
        except requests.exceptions.HTTPError:
            if 400 <= resp.status_code < 500:
                self.console.print(f'[red]Client Error: {resp.status_code}[/]')
            else:
                self.console.print(f'[red]Server Error: {resp.status_code}[/]')

    # RAG is disabled in the current version
    def __list_collections(self):
        """Know what collections are available"""
        response = self.client.get(
            f'{self.api_url}/collections/list/'
        )
        response.raise_for_status()
        body = response.json()
        if len(body) == 0:
            self.console.print('[+] No collections found')
        else:
            tree = Tree("[+] Available Collections:")
            for collection in body:
                c_doc = f"[bold blue]{collection['title']}[/]\n"

                str_topics = ', '.join(collection['topics'])
                c_doc += f"[bold white]Topics[/]: {str_topics}\n"

                c_doc += "[bold white]Documents[/]:\n"
                for document in collection['documents']:
                    c_doc += f"- {document['name']}\n"

                tree.add(c_doc)

            self.console.print(tree)

    def __create_collection(self):
        """Upload a collection to RAG"""
        collection_title = Prompt.ask(
            prompt='Title: ',
            console=self.console
        )
        collection_path = Prompt.ask(
            prompt='Path (leave blank for nothing): ',
            console=self.console
        )

        try:
            if collection_path:
                with open(collection_path, 'rb') as collection_file:
                    response = requests.post(
                        url=f'{self.api_url}/collections/new',
                        data={'title': collection_title},
                        files={'file': collection_file}
                    )
            else:
                response = requests.post(
                    url=f'{self.api_url}/collections/new',
                    data={'title': collection_title}
                )

            response.raise_for_status()
            body: dict = response.json()

            if 'error' in body:
                self.console.print(f"[bold red][!] Failed: [/] {body['error']}")
            else:
                self.console.print(f"[bold blue][+] Success: [/] {body['success']}")

        except OSError as err:
            self.console.print(f"[bold red][!] Failed: [/] {err}")
        except requests.exceptions.HTTPError as http_err:
            self.console.print(f"[bold red][!] HTTP Error: [/] {http_err}")

    def help(self):
        """Print help message"""
        # Basic Commands
        self.console.print("[bold white]Basic Commands[/]")
        self.console.print("- [bold blue]help[/]   : Show available commands.")
        self.console.print("- [bold blue]clear[/]  : Clears the terminal.")
        self.console.print("- [bold blue]exit[/]   : Exit the program")

        # Agent Related
        self.console.print("\n[bold white]Agent Related[/]")
        self.console.print("- [bold blue]chat[/]   : Open chat with the agent.")
        self.console.print("- [bold blue]back[/]   : Exit chat")

        # Session Related
        self.console.print("\n[bold white]Session Related[/]")
        self.console.print("- [bold blue]new[/]             : Create a new session.")
        self.console.print("- [bold blue]save[/]            : Save the current session.")
        self.console.print("- [bold blue]load[/]            : Opens a session.")
        self.console.print("- [bold blue]delete[/]          : Delete the current session from persistent sessions.")
        self.console.print("- [bold blue]rename[/]          : Rename the current session.")
        self.console.print("- [bold blue]list sessions[/]   : Show the saved sessions.")

        # RAG Related
        # self.console.print("\n[bold white]RAG Related[/]")
        # self.console.print("- [bold blue]list collections[/]  : Lists all collections in RAG.")
        # self.console.print("- [bold blue]create collection[/] : Upload a collection to RAG.")

    @staticmethod
    def clear_terminal():
        os.system(
            'cls' if os.name == 'nt'  # windows (its always him)
            else 'clear'  # unix
        )


def validate_endpoint(api_endpoint: str):
    parsed_endpoint = urlparse(api_endpoint)
    protocol = parsed_endpoint.scheme

    if protocol not in ('http', 'https') or \
            parsed_endpoint.query:
        return None
    return api_endpoint


def old_main():
    startup_parser = argparse.ArgumentParser()

    startup_parser.add_argument(
        '--api',
        default='http://127.0.0.1:8000',
        help='The Agent API address',
        type=validate_endpoint
    )

    try:
        args = startup_parser.parse_args(sys.argv[1:])
        client = AgentClient(api_url=args.api)
        client.run()
    except KeyboardInterrupt:
        sys.exit()


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
