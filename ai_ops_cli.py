"""
CLI Client for the Agent API, is useful for development and
when executing the frontend is not convenient.

"""
import argparse
import os
import sys
from urllib.parse import urlparse

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

VERSION = "0.0.0"


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

            'list collections': self.list_collections,
            'create collection': self.create_collection
        }
        self.multiline_input = build_input_multiline()

        self.console.print("[bold blue]ai-ops-cli[/] (beta) starting.")
        try:
            response = self.client.get(f'{self.api_url}/ping', timeout=20)
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

            try:
                with self.client.post(query_url, json={'query': q}, headers=None, stream=True) as resp:
                    resp.raise_for_status()

                    response_text = '**Assistant**: '
                    with Live(console=self.console, refresh_per_second=10) as live:
                        live.update(Markdown(response_text))
                        for chunk in resp.iter_content():
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

    def list_collections(self):
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

    def create_collection(self):
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
        self.console.print("\n[bold white]RAG Related[/]")
        self.console.print("- [bold blue]list collections[/]  : Lists all collections in RAG.")
        self.console.print("- [bold blue]create collection[/] : Upload a collection to RAG.")

    @staticmethod
    def clear_terminal():
        os.system('cls' if os.name == 'nt' else 'clear')


class ValidateURLAction(argparse.Action):
    """
    Checks if the URL string for the API is valid.
    A valid url in this context has:
    - http/https scheme
    - the path is empty
    """

    def __call__(self, parser, namespace, values, option_string=None):
        parsed = urlparse(values)
        url_scheme = parsed.scheme
        url_path = parsed.path

        try:
            valid_scheme = url_scheme in ('http', 'https') if url_scheme else False
            valid_path = len(url_path) <= 1  # consider "/"
            assert valid_scheme and valid_path
        except AssertionError:
            print(f'[!] Invalid URL: {values}')
            sys.exit(-1)

        setattr(namespace, self.dest, values)


def main():
    """Main function for AI-OPS CLI client"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--api',
        default='http://127.0.0.1:8000',
        help='The Agent API address',
        action=ValidateURLAction
    )

    try:
        args = parser.parse_args(sys.argv[1:])
        client = AgentClient(api_url=args.api)
        client.run()
    except KeyboardInterrupt:
        sys.exit()


if __name__ == "__main__":
    main()
