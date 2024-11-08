"""
Interfaces the AI Agent to the LLM Provider, model availability depends on
implemented prompts, to use a new model the relative prompts should be written.
"""
from abc import ABC, abstractmethod
from typing import Tuple
from dataclasses import dataclass, field

import httpx
from ollama import Client, ResponseError

from src.agent.memory.base import Role

AVAILABLE_MODELS = {
    'mistral': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 8192
        },
        'tools': True
    },
    'llama3.1': {
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
}


@dataclass
class Provider(ABC):
    """Represents a LLM Provider"""
    model: str
    inference_endpoint: str = 'http://localhost:11434'
    api_key: str | None = None

    @abstractmethod
    def query(self, messages: list) -> Tuple[str, Tuple]:
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
        roles = [Role.SYS, Role.USER, Role.ASSISTANT, Role.TOOL]
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
        if self.__match_model() is None:
            raise ValueError(f'Model {self.model} is not supported.')
        try:
            self.client = Client(host=self.inference_endpoint)
        except Exception as err:
            raise RuntimeError('Initialization Failed') from err

    def query(self, messages: list) -> Tuple[str, int]:
        """Generator that returns a tuple containing:
         (response_chunk, token_usage)"""
        try:
            self.verify_messages_format(messages)
        except (TypeError, ValueError) as input_err:
            raise input_err from input_err

        try:
            options = AVAILABLE_MODELS[self.__match_model()]['options']
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options=options
            )
            for chunk in stream:
                if 'eval_count' and 'prompt_eval_count' in chunk:
                    yield "", chunk['prompt_eval_count']

                yield chunk['message']['content'], None
        except (ResponseError, httpx.ConnectError) as err:
            raise ProviderError(err) from err

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

    def __match_model(self) -> str | None:
        """Check if a model is supported, the model availability on Ollama
        is upon the user; ProviderError is raised if not available."""
        for model in list(AVAILABLE_MODELS.keys()):
            if self.model.startswith(model):
                return model
        return None


@dataclass
class LLM:
    """LLM interface"""
    model: str
    inference_endpoint: str = 'http://localhost:11434'
    provider: Provider = Ollama
    api_key: str | None = None

    def __post_init__(self):
        self.provider = self.provider(
            model=self.model,
            inference_endpoint=self.inference_endpoint,
            api_key=self.api_key
        )

    def query(self, messages: list) -> Tuple[str, int]:
        """Generator that returns LLM response in a tuple containing:
        (chunk, token_usage).

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


if __name__ == "__main__":

    Ollama(model='mistral', inference_endpoint='some')
    Ollama(model='mistral:7b-instruct-v0.3-q8_0', inference_endpoint='some')
    Ollama(model='gpt', inference_endpoint='some')
