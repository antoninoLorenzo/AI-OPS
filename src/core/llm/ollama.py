from typing import Tuple
from dataclasses import dataclass

import httpx
from ollama import Client, ResponseError
from pydantic import validate_call

from src.core.llm.schema import Provider, ProviderError
from src.core.memory import Conversation
from src.utils import get_logger


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
    }
}
logger = get_logger(__name__)


@dataclass
class Ollama(Provider):
    """Client for Ollama."""
    client: Client | None = None

    def __post_init__(self):
        if self.__match_model() is None:
            raise ValueError(f'Model {self.model} is not supported.')
        try:
            self.client = Client(host=self.inference_endpoint)
        except Exception as err:
            raise RuntimeError('Initialization Failed') from err

    @validate_call
    def query(
        self,
        messages: Conversation
    ) -> Tuple[str, int]:
        """Generator that returns a tuple containing:
         (response_chunk, token_usage)"""
        try:
            options = AVAILABLE_MODELS[self.__match_model()]['options']
            stream = self.client.chat(
                model=self.model,
                messages=messages.model_dump(),
                stream=True,
                options=options
            )
            for chunk in stream:
                if 'eval_count' and 'prompt_eval_count' in chunk:
                    yield "", chunk['prompt_eval_count']

                yield chunk['message']['content'], None
        except (ResponseError, httpx.ConnectError) as err:
            raise ProviderError(err) from err

    @validate_call
    def tool_query(
        self,
        messages: Conversation,
        tools: list | None = None
    ):
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
        base_model = self.__match_model()
        if base_model is None:
            raise ValueError(f'Model {self.model} is not supported.')
        if not AVAILABLE_MODELS[base_model]['tools']:
            raise NotImplementedError(f'{self.model} not support tool calling')

        if not tools:
            raise ValueError('Empty tool list')

        tool_response = self.client.chat(
            model=self.model,
            messages=messages.model_dump(),
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
