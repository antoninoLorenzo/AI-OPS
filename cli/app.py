import sys
from functools import partial
from typing import List,Optional

import httpx
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import InMemoryHistory

from cli.commands import (
    Command, 
    CommandParser, 
    CommandRegistry, 
    CommandCompleter,
    ParserException
)


class AppContext:
    """Stores App objects that are injected into commands."""

    def __init__(self, client: httpx.Client, console: Console):
        # most commands need either access to stdout or api client
        self.client = client
        self.console = console
        # runtime settings
        self.model_name = 'unspecified'
        self.current_conversation: Optional[dict] = None
        self.in_chat = False


class App:
    """Implements Read-Eval-Print Loop to interact with AI-OPS Assistant."""

    def __init__(
            self,
            api_url: str,
            commands: List[Command]
    ):
        self.__parser = CommandParser()
        self.__registry = CommandRegistry()
        self.__registry.register(commands)
        self.__command_completer = CommandCompleter(commands)

        # health-check
        try:
            self.__context = AppContext(
                httpx.Client(base_url=api_url, timeout=15.0),
                Console(force_terminal=True)
            )

            response = self.__context.client.get('/ping', timeout=5)
            response.raise_for_status()
            # fetch model name from API, wheter it is running locally or remotely
            self.__context.model_name = response.json()['model']

            self.__context.console.print("Backend: [blue]online[/]")
            self.__context.console.print(
                "[bold cyan]ℹ️  Tip:[/bold cyan] Press [bold green]Ctrl + ↓ (Down Arrow)[/bold green] to move to the next line while typing.",
                style="italic"
            )
        except Exception:
            self.__context.console.print('Backend: [red]offline[/]\n')
            sys.exit(-1)

    def run(self):
        history = InMemoryHistory()
        while True:
            user_input = PromptSession(
                    history=history,
                    completer=self.__command_completer,
                    complete_while_typing=True
            ).prompt(self.prompt_text())

            # Remove any control characters
            user_input = ''.join(ch for ch in user_input if ord(ch) >= 32)

            # user_input = Prompt.ask(
            #     '[underline]ai-ops[/] >',
            #     console=self.__context.console,
            #     default='help',
            #     show_default=False
            # )
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
            if not command:
                self.__context.console.print(
                    f"[red]Error:[/] command {user_input} not found."
                )
                continue
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

    def prompt_text(self):
        """Returns a stylized prompt text"""
        if hasattr(self.__context, 'in_chat') and self.__context.in_chat:
            conversation = self.__context.current_conversation
            conversation_name = conversation.get('name', 'Unknown')
            conversation_id = conversation.get('conversation_id', '?')
            return ANSI(f"\033[38;5;196m\033[1m {conversation_name} \033[0m (\033[90m{conversation_id}\033[0m) > ")
        else:
            return ANSI("\033[38;5;196m\033[1m ai-ops \033[0m > ")
