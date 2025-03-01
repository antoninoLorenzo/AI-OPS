import argparse
import os
import sys
import json
from typing import Callable, Any, Dict, Type, Generator
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError, HTTPError
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import InvalidResponse, Prompt
from rich.markup import escape
from prompt_toolkit.formatted_text import ANSI
from rich.tree import Tree
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers import MarkdownLexer
from prompt_toolkit.keys import Keys
from pydantic import BaseModel, validate_call

VERSION = "0.0.0"


def build_input_multiline(current_session, api_url, model_name):
    """Creates an input prompt that incluye session name, API URL and model name"""
    bindings = KeyBindings()

    @bindings.add(Keys.ControlDown, eager=True)
    def _(event):
        event.current_buffer.newline()

    return PromptSession(
        ANSI(
            f"\033[38;5;124m {current_session.get('name', 'unknown')}\033[38;5;245m@\033[38;5;246m{api_url} :: "
            f"\033[38;5;160m[{model_name}]\n"
            f"\033[38;5;196m> \033[0m"
        ),
        key_bindings=bindings,
        lexer=PygmentsLexer(MarkdownLexer)
    )




class CommandCompleter(Completer):
    def __init__(self, commands):
        self.commands = commands

    def get_completions(self, document, complete_event):
        # Get word being completed
        word = document.get_word_before_cursor()
        
        # Return matching commands
        for cmd in self.commands:
            if cmd.startswith(word):
                yield Completion(cmd, start_position=-len(word))


class AgentClient:
    """Client for Agent API"""

    def __init__(self, api_url: str = 'http://127.0.0.1:8000', model_name: str = 'mistral'):
        self.api_url = api_url
        self.client = requests.Session()
        self.console = Console(force_terminal=True)
        self.current_session = {'sid': 0, 'name': 'Undefined'}
        self.model_name = model_name  # O el modelo que uses por defecto

        self.multiline_input = build_input_multiline(
            self.current_session,
            self.api_url,
            self.model_name
        )

        self.show_thinking = True
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
            

            # RAG is disabled in the current version
            # 'list collections': self.__list_collections,
            # 'create collection': self.__create_collection

            # Add new command to toggle thinking
            'toggle thinking': self.toggle_thinking,
        }

        self.console.print("[bold blue]ai-ops-cli[/] (beta) starting.")
        # Display thinking status on startup
        self.console.print(f"Thinking mode: [{'green' if self.show_thinking else 'red'}]{'On' if self.show_thinking else 'Off'}[/]")
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
        # Create a history object for command history
        history = InMemoryHistory()
        
        # Create command completer for tab completion
        completer = CommandCompleter(self.commands.keys())
        
        # Set in_chat flag
        self.in_chat = False
        
        while True:
            try:
                # Use prompt_toolkit with dynamic prompt
                user_input = PromptSession(
                    history=history,
                    completer=completer,
                    complete_while_typing=True
                ).prompt(self.prompt_text())
            
                # Remove any control characters
                user_input = ''.join(ch for ch in user_input if ord(ch) >= 32)
                
                if not user_input:
                    continue
                    
                if user_input == 'exit':
                    break
                    
                # Execute command if valid
                if user_input in self.commands:
                    self.commands[user_input]()
                else:
                    closest = self.find_closest_command(user_input)
                    if closest:
                        self.console.print(f"Using command: [bold blue]{closest}[/]")
                        self.commands[closest]()
                    else:
                        self.console.print('Command not recognized. Try "help" for available commands.', style='bold red')
                        self.commands['help']()
                    
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            except Exception as e:
                self.console.print(f'[red]Error: {e}[/]')
                continue

    def find_closest_command(self, input_text):
        """Find the closest matching command for a given input"""
        # Exact match first
        if input_text in self.commands:
            return input_text
            
        # Check for partial matches
        partial_matches = [cmd for cmd in self.commands.keys() if input_text in cmd]
        if len(partial_matches) == 1:
            return partial_matches[0]
            
        # Look for close matches (allowing for typos)
        close_matches = []
        for cmd in self.commands.keys():
            # Calculate how different the input is from each command
            if len(input_text) > 2 and len(cmd) > 2:  # Only for inputs of reasonable length
                # Simple distance calculation - count different characters
                distance = sum(1 for a, b in zip(input_text, cmd) if a != b)
                # Add penalty for length difference
                distance += abs(len(input_text) - len(cmd))
                
                if distance <= 3:  # Allow up to 3 differences
                    close_matches.append((cmd, distance))
        
        # Sort by distance (closest first)
        close_matches.sort(key=lambda x: x[1])
        
        # Return the closest match if there is one
        if close_matches:
            return close_matches[0][0]
            
        return None
    

    def new_session(self):
        """Creates a new session and updates the prompt"""
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

        
        self.multiline_input = build_input_multiline(
            self.current_session, 
            self.api_url, 
            self.model_name  
        )

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
            self.console.print(f'Session: [bold blue]{name}[/] (ID: {sid})')

        # Set in chat mode
        self.in_chat = True
        
        try:
            while True:
                q = self.multiline_input.prompt()
                if q.startswith('back'):
                    break
                self.__generate_response(query_url, q)
        finally:
            # Always reset chat mode when exiting
            self.in_chat = False

    def toggle_thinking(self):
        """Toggle the display of LLM thinking process"""
        self.show_thinking = not self.show_thinking
        status = "On" if self.show_thinking else "Off"
        status_color = "green" if self.show_thinking else "red"
        self.console.print(f"Thinking mode: [{status_color}]{status}[/]")

    def __generate_response(self, url: str, query: str):
        """Generate a response from the API with thinking process handling"""
        try:
            with self.client.post(
                    url,
                    json={'query': query},
                    headers=None,
                    stream=True
            ) as resp:
                resp.raise_for_status()

                response_text = '**Assistant**: '
                
                # Variables to track thinking blocks
                in_thinking = False
                thinking_buffer = ""
                
                with Live(console=self.console, refresh_per_second=10) as live:
                    live.update(Markdown(response_text))
                    for chunk in resp.iter_content(decode_unicode=True):
                        if chunk:
                            try:
                                # Convert bytes to string if needed
                                if isinstance(chunk, bytes):
                                    chunk = chunk.decode('utf-8')
                                
                                # Process the chunk character by character to handle thinking tags
                                for char in chunk:
                                    if not in_thinking:
                                        # Look for start of thinking tag
                                        if response_text.endswith("<think"):
                                            response_text += char
                                            if response_text.endswith("<think>"):
                                                in_thinking = True
                                                thinking_buffer = ""
                                                # Remove the tag from visible response
                                                response_text = response_text[:-7]
                                        else:
                                            response_text += char
                                    else:  # We're inside a thinking block
                                        thinking_buffer += char
                                        # Check for end of thinking tag
                                        if thinking_buffer.endswith("</think>"):
                                            in_thinking = False
                                            # Extract the thinking content without the end tag
                                            thinking_content = thinking_buffer[:-8]
                                            
                                            # Display thinking if enabled
                                            if self.show_thinking:
                                                self.console.print("\n[bold yellow]Thinking:[/bold yellow]", style="yellow")
                                                self.console.print(thinking_content, style="dim yellow")
                                                self.console.print("[yellow]End of thinking[/yellow]\n")
                                            
                                            thinking_buffer = ""
                                            # Update the live display without the thinking content
                                            live.update(Markdown(response_text))
                                
                                # Update the live display with the processed content
                                live.update(Markdown(response_text))
                            except UnicodeDecodeError:
                                pass

                print()
        except requests.exceptions.HTTPError:
            if 400 <= resp.status_code < 500:
                self.console.print(f'[red]Client Error: {resp.status_code}[/]')
            else:
                self.console.print(f'[red]Server Error: {resp.status_code}[/]')
        except requests.exceptions.ConnectionError:
            self.console.print('[red]Connection Error[/]')
        except requests.exceptions.Timeout:
            self.console.print('[red]Timeout Error[/]')
        except requests.exceptions.RequestException as e:
            self.console.print(f'[red]Error: {e}[/]')
        except KeyboardInterrupt:
            self.console.print('[red]Interrupted[/]')
        except Exception as e:
            self.console.print(f'[red]Error: {e}[/]')
        
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
        except requests.exceptions.RequestException as req_err:
            self.console.print(f"[bold red][!] Request Error: [/] {req_err}")

    def prompt_text(self):
        """Returns a stylized prompt text"""
        if hasattr(self, 'in_chat') and self.in_chat:
            session_name = self.current_session.get('name', 'Unknown')
            session_id = self.current_session.get('sid', '?')
            return ANSI(f"\033[38;5;196m\033[1m {session_name} \033[0m (\033[90m{session_id}\033[0m) > ")
        else:
            return ANSI("\033[38;5;196m\033[1m ai-ops \033[0m > ")



    def help(self):
        """Print help message"""
        # Basic Commands
        self.console.print("\n[bold white]Basic Commands[/]")
        self.console.print("- [bold blue]help[/]   : Show available commands.")
        self.console.print("- [bold blue]clear[/]  : Clears the terminal.")
        self.console.print("- [bold blue]exit[/]   : Exit the program")

        # Agent Related
        self.console.print("\n[bold white]Agent Related[/]")
        self.console.print("- [bold blue]chat[/]   : Open chat with the agent.")
        self.console.print("- [bold blue]back[/]   : Exit chat")
        self.console.print("- [bold blue]toggle thinking[/] : Toggle thinking mode")

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

        self.console.print("\n")

    @staticmethod
    def clear_terminal():
        os.system(
            'cls' if os.name == 'nt'    # windows (its always him)
            else 'clear'                # unix
        )


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
        model = os.getenv('MODEL', 'mistral')  # Usa os.getenv en vez de acceder a os.environ directamente

        client = AgentClient(api_url=args.api, model_name=model)
        client.run()
    except KeyboardInterrupt:
        sys.exit()

if __name__ == "__main__":
    main()
