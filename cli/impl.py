"""Implements logic for each command."""
import os

import httpx
from rich.live import Live
from rich.markdown import Markdown
from rich.tree import Tree
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.keys import Keys
from pygments.lexers import MarkdownLexer

from cli.app import AppContext


def build_input_multiline(current_conversation, api_url, model_name):
    """Creates an input prompt that includes conversation name, API URL and model name"""
    bindings = KeyBindings()

    @bindings.add(Keys.ControlDown, eager=True)
    def _(event):
        event.current_buffer.newline()

    return PromptSession(
        ANSI(
            f"\033[38;5;124m {current_conversation.get('name', 'unknown')}\033[38;5;245m@\033[38;5;246m{api_url} :: "
            f"\033[38;5;160m[{model_name}]\n"
            f"\033[38;5;196m> \033[0m"
        ),
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
    """
    Chat Read-Eval-Print Loop

    :param app_context: chat requires the API client, the console and the current conversation_id.
    """
    client = app_context.client
    console = app_context.console

    # when user directly invokes chat just create an 'untitled' conversation
    if app_context.current_conversation is None:
        __conversation_new(app_context, conversation_name='untitled')
        return
    if app_context.current_conversation.get('conversation_id', -2) < 0:
        console.print("[bold red]Error: [/]invalid conversation id")

    multiline_input = build_input_multiline(
        current_conversation=app_context.current_conversation,
        api_url=client.base_url,
        model_name=app_context.model_name
    )

    app_context.in_chat = True
    conversation_id = app_context.current_conversation.get('conversation_id')
    try:
        while True:
            user_input = multiline_input.prompt()
            if user_input.startswith('back'):
                break

            with client.stream(
                method='POST',
                url=f'/conversations/{conversation_id}/chat',
                json={'query': user_input}
            ) as response_stream:
                # handle errors:
                # - invalid conversation_id (404)
                # - empty message (400)
                try:
                    response_stream.raise_for_status()
                except httpx.HTTPError as _:
                    # Trying to get the detail is a bit tricky with response stream.
                    # httpx.ResponseNotRead:
                    # Attempted to access streaming response content, without having called `read()`.
                    console.print("[bold red]Error: [/]failed sending message")
                    break
                except httpx.ReadTimeout as _:
                    console.print("[bold red]Error: [/]timeout reached")
                    break

                console.print('[bold blue]Assistant[/]: ')
                response_text = ''
                with Live(console=console, refresh_per_second=10) as live_console:
                    live_console.update(Markdown(response_text))
                    for chunk in response_stream.iter_text():
                        response_text += chunk
                        live_console.update(Markdown(response_text))
    finally:
        app_context.in_chat = False


def __conversation_list(app_context: AppContext):
    """Prints existing conversations."""
    client = app_context.client
    console = app_context.console
    try:
        response = client.get('/conversations')
        response.raise_for_status()
        conversations = response.json()
    except httpx.HTTPStatusError as _:
        console.print("[bold red]Error: [/]failed getting conversation list")
        return

    if len(conversations) == 0:
        console.print("No Conversations.")
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
    except httpx.HTTPError as err:
        console.print(f"[bold red]Error: [/]{err.response.status_code}")
        return

    console.print(f'[{conversation["conversation_id"]}]: {conversation["name"]}')
    # new conversation makes transition to chat
    app_context.current_conversation = conversation
    __chat(app_context)


def __conversation_load(app_context: AppContext, conversation_id: int):
    """
    Opens a conversation by conversation_id, sets it as current conversation 
    and calls __chat REPL.
    """
    client = app_context.client
    console = app_context.console
    try:
        response = client.get(f'/conversations/{conversation_id}')
        response.raise_for_status()
        conversation = response.json()
    except httpx.HTTPError as _:
        # optional: consider implementing logging
        console.print(f"[bold red]Error: [/]invalid conversation_id: {conversation_id}")
        return

    for message in conversation['messages']:
        console.print(
            f"[bold blue]{message['role']}[/]: {message['content']}"
        )

    # load conversation makes transition to chat
    app_context.current_conversation = conversation
    __chat(app_context)


def __conversation_rename(app_context: AppContext, conversation_id: int, new_name: str):
    client = app_context.client
    console = app_context.console
    try:
        response = client.post(
            url=f'/conversations/{conversation_id}',
            params={'new_name': new_name}
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        try:
            error_data = exc.response.json()
            error_detail = error_data.get("detail")
        except ValueError:
            error_detail = 'failed renaming conversation'

        console.print(f"[bold red]Error: [/]{error_detail}")


def __conversation_save(app_context: AppContext, conversation_id: int):
    client = app_context.client
    console = app_context.console
    try:
        response = client.put(f'/conversations/{conversation_id}')
        response.raise_for_status()
    except httpx.HTTPError as _:
        console.print("[bold red]Error: [/]failed saving conversation")


def __conversation_delete(app_context: AppContext, conversation_id: int):
    client = app_context.client
    console = app_context.console
    try:
        response = client.delete(f'/conversations/{conversation_id}')
        response.raise_for_status()
    except httpx.HTTPError as _:
        console.print("[bold red]Error: [/]failed deleting conversation")
