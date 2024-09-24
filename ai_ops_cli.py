"""
CLI Client for the Agent API, is useful for development and
when executing the frontend is not convenient.

"""
import argparse
import os
import sys
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import InvalidResponse, Prompt
from rich.tree import Tree


VERSION = "0.0.0"


class AgentClient:
    """Client for Agent API"""

    def __init__(self, api_url: str = 'http://127.0.0.1:8000'):
        self.api_url = api_url
        self.client = requests.Session()
        self.console = Console()
        self.current_session = {'sid': 0, 'name': 'Undefined'}
        self.commands = {
            'help': self.help,
            'chat': self.chat,
            'new': self.new_session,
            'save': self.save_session,
            'rename': self.rename_session,
            'delete': self.delete_session,
            'list sessions': self.list_sessions,
            'list collections': self.list_collections,
            'load': self.load_session,
            'exec': self.execute_plan,
            'plans': self.list_plans,
            'clear': AgentClient.clear_terminal,
            'exit': ''
        }

        self.console.print("[bold blue]ai-ops-cli[/] (beta) starting.")
        try:
            self.client.get(self.api_url, timeout=20)
            self.console.print(f"Backend: [blue]online[/]")
        except ConnectionError:
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

        response = self.client.get(
            f'{self.api_url}/session/new',
            params={'name': session_name}
        )
        response.raise_for_status()

        self.current_session = {'sid': response.json()['sid'], 'name': session_name}
        self.chat(print_name=True)

    def save_session(self):
        """Save the current session"""
        response = self.client.get(
            f'{self.api_url}/session/{self.current_session["sid"]}/save'
        )
        if response.status_code != 200:
            self.console.print(f'[!] Failed: {response.status_code}')
        else:
            self.console.print(f'[+] Saved')

    def rename_session(self):
        """Renames the current session"""
        session_name = Prompt(
            'New Name',
            console=self.console
        )

        response = self.client.get(
            f'{self.api_url}/session/{self.current_session["sid"]}/rename',
            params={'new_name': str(session_name)}
        )
        response.raise_for_status()
        self.current_session['name'] = str(session_name)
        self.chat(print_name=True)

    def delete_session(self):
        """Deletes the current session"""
        response = self.client.get(
            f'{self.api_url}/session/{self.current_session["sid"]}/delete'
        )
        response.raise_for_status()
        body = response.json()
        self.console.print(f'[{"+" if body["success"] else "-"}] {body["message"]}')

    def list_sessions(self):
        """List all sessions"""
        response = self.client.get(
            f'{self.api_url}/session/list/'
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
            f'{self.api_url}/session/get/',
            params={'sid': int(session_id)}
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
        query_url = f'{self.api_url}/session/{sid}/query'

        if print_name:
            name = self.current_session["name"]
            self.console.print(f'({sid}) [bold blue]{name}[/]')

        while True:
            self.console.print("[bold white]User:[/] ", end='')
            q = self.__input_multiline()
            if q == '-1':
                break

            with self.client.post(query_url, json={'query': q}, headers=None, stream=True) as resp:
                resp.raise_for_status()

                response_text = '**Assistant**: '
                with Live(console=self.console, refresh_per_second=10) as live:
                    live.update(Markdown(response_text))
                    for chunk in resp.iter_content():
                        if chunk:
                            response_text += chunk.decode()
                            live.update(Markdown(response_text))

                print()

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

    def execute_plan(self):
        """Plan execution"""
        with self.client.get(
                f'{self.api_url}/session/{self.current_session["sid"]}/plan/execute',
                headers=None,
                stream=True
        ) as resp:
            self.console.print(f'[+] Tasks\n')
            for task_str in resp.iter_content():
                if task_str:
                    self.console.print(task_str.decode(), end='')
            print()
        self.chat()

    def list_plans(self):
        """Retrieve the plans in the current session and
        prints the last execution status."""
        response = self.client.get(
            f'{self.api_url}/session/{self.current_session["sid"]}/plan/list'
        )
        response.raise_for_status()

        body: dict = response.json()

        if 'error' in body:
            self.console.print(f'[bold red][!][/] {body["error"]}')
        else:
            for i, plan in body.items():
                tasks = ''
                for task in plan:
                    tasks += f'ai-ops:~$ {task["command"]}\n'
                    if len(task['output']) > 0:
                        tasks += f'\n{task["output"]}\n'

                self.console.print(f'[+] Plan {i}\n\n'
                                   f'{tasks}')

    def __input_multiline(self) -> str:
        input_text = ""
        while True:
            line = self.console.input("")
            if line == "":
                break
            input_text += line + "\n"
        return input_text

    def help(self):
        """Print help message"""
        # Basic Commands
        self.console.print("[bold white]Basic Commands[/]")
        self.console.print("- [bold blue]help[/]   : Show available commands.")
        self.console.print("- [bold blue]clear[/]  : Clears the terminal.")
        self.console.print("- [bold blue]bye[/]    : Exit the program")

        # Agent Related
        self.console.print("\n[bold white]Agent Related[/]")
        self.console.print("- [bold blue]chat[/]   : Open chat with the agent.")
        self.console.print("- [bold blue]-1[/]     : Exit chat")
        self.console.print("- [bold blue]exec[/]   : Execute the last plan generated by the agent.")
        self.console.print("- [bold blue]plans[/]  : Lists all plans in the current session.")

        # Session Related
        self.console.print("\n[bold white]Session Related[/]")
        self.console.print("- [bold blue]new[/]             : Create a new session.")
        self.console.print("- [bold blue]save[/]            : Save the current session.")
        self.console.print("- [bold blue]delete[/]          : Delete the current session from persistent sessions.")
        self.console.print("- [bold blue]list sessions[/]   : Show the saved sessions.")
        self.console.print("- [bold blue]load[/]            : Opens a session.")

        # RAG Related
        self.console.print("\n[bold white]RAG Related[/]")
        self.console.print("- [bold blue]list collections[/]: Lists all collections in rag.")

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
