"""
Interfaces the AI Agent to the LLM Provider, model availability depends on
implemented prompts, to use a new model the relative prompts should be written.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx
from ollama import Client, ResponseError

from src.agent.memory.base import Role

AVAILABLE_MODELS = {
    'llama3': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        },
        'tools': True
    },
    'gemma:7b': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        },
        'tools': False
    },
    'gemma2:9b': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        },
        'tools': False
    },
    'mistral': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        },
        'tools': True
    },
}


@dataclass
class Provider(ABC):
    """Represents a LLM Provider"""
    model: str
    client_url: str = 'http://localhost:11434'
    api_key: str | None = None

    @abstractmethod
    def query(self, messages: list):
        """Implement to makes query to the LLM provider"""

    @abstractmethod
    def tool_query(self, messages: list, tools: list | None = None):
        """Implement for LLM tool calling"""

    @staticmethod
    def verify_messages_format(messages: list[dict]):
        """Format validation for messages."""
        # check types
        message_types_dict = [isinstance(msg, dict) for msg in messages]
        if not isinstance(messages, list) or \
                len(messages) == 0 or \
                False in message_types_dict:
            raise TypeError(f'messages must be a list[dict]: \n {messages}')

        # check format
        roles = [Role.SYS, Role.USER, Role.ASSISTANT]
        valid_roles = [str(role) for role in roles]
        err_message = f'expected {{"role": "{valid_roles}", "content": "..."}}'

        # check format - keys
        message_keys = [list(msg.keys()) for msg in messages]
        valid_keys = ['role' in keys and 'content' in keys and len(keys) == 2
                      for keys in message_keys]
        if False in valid_keys:
            raise ValueError(err_message + f'\nMessage Keys: {message_keys}')

        # check format = values
        message_roles = [msg['role'] in valid_roles for msg in messages]
        message_content = [len(msg['content']) != 0 for msg in messages]
        if False in message_roles or False in message_content:
            raise ValueError(err_message)


class ProviderError(Exception):
    """Just a wrapper to Exception for error handling
    when an error is caused by the LLM provider"""


@dataclass
class Ollama(Provider):
    """Ollama Interface"""
    client: Client | None = field(init=False, default=None)

    def __post_init__(self):
        if self.model not in AVAILABLE_MODELS.keys():
            raise ValueError(f'Model {self.model} is not available')
        try:
            self.client = Client(host=self.client_url)
        except Exception as err:
            raise RuntimeError('Initialization Failed') from err

    def query(self, messages: list):
        """Generator that returns response chunks."""
        try:
            self.verify_messages_format(messages)
        except (TypeError, ValueError) as input_err:
            raise input_err from input_err

        try:
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options=AVAILABLE_MODELS[self.model]['options']
            )
            for chunk in stream:
                yield chunk['message']['content']
        except (ResponseError, httpx.ConnectError) as err:
            raise ProviderError() from err

    def tool_query(self, messages: list, tools: list | None = None):
        """Implements LLM tool calling.
        :param messages:
            The current conversation provided as a list of messages in the
            format [{"role": "assistant/user/system", "content": "..."}, ...]
        :param tools:
            A list of tools in the format specified by `ollama-python`, the
            conversion is managed by `ToolRegistry` from `tool-parse` library.
        :return
            Ollama response with "message" : {"tool_calls": ...} or None.
        """
        if not AVAILABLE_MODELS[self.model]['tools']:
            raise NotImplementedError(f'{self.model} not support tool calling')

        try:
            self.verify_messages_format(messages)
        except (TypeError, ValueError) as input_err:
            raise input_err from input_err

        if not tools:
            raise ValueError('Empty tool list')

        tool_response = self.client.chat(
            model=self.model,
            messages=messages,
            tools=tools
        )

        return tool_response if tool_response['message'].get('tool_calls') \
            else None


@dataclass
class LLM:
    """LLM interface"""
    model: str
    client_url: str = 'http://localhost:11434'
    provider: Provider = None
    provider_class: Provider = Ollama
    api_key: str | None = None

    def __post_init__(self):
        self.provider = self.provider_class(
            model=self.model,
            client_url=self.client_url,
            api_key=self.api_key
        )

    def query(self, messages: list):
        """Generator that returns LLM response as a stream of string chunks.
        :param messages:
            The current conversation provided as a list of messages in the
            format [{"role": "assistant/user/system", "content": "..."}, ...]"""
        yield from self.provider.query(messages)

    def tool_query(self, messages: list, tools: list | None = None):
        """
        :param messages:
            The current conversation provided as a list of messages in the
            format [{"role": "assistant/user/system", "content": "..."}, ...]
        :param tools:
            A list of tools in the format specified by `ollama-python`,
            the conversion is managed by `tool-parse` library."""
        return self.provider.tool_query(messages, tools)
