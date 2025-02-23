import sys
from functools import partial
from typing import List,Optional

import httpx
from rich.console import Console
from rich.prompt import Prompt


from cli.commands import Command, CommandParser, CommandRegistry, ParserException


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
