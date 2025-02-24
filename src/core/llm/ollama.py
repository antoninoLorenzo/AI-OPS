from typing import Tuple
from dataclasses import dataclass

import httpx
from ollama import Client, ResponseError
from pydantic import validate_call

from src.core.memory import Conversation, Role
from src.core.llm.schema import Provider, ProviderError
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
    },
    # The version `deepseek-r1:14b-qwen-distill-q4_K_M` seems promising.
    # This also thanks to the ollama system prompt for deepseek-r1 that
    # generate reasoning in `<think>...</think>` tags.
    # However, those tags content should be masked from the user and, the
    # current code isn't flexible enough in order to handle custom outputs
    # for a specific model.
    # 'deepseek-r1': {
    #     'options': {
    #         'temperature': 0.5,
    #         'num_ctx': 16384
    #     },
    #     'tools': False
    # }
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
            raise RuntimeError('Ollama: invalid endpoint') from err

    @staticmethod
    def user_message_token_length(
        conversation: Conversation,
        full_input_tokens: int,
    ) -> int:
        print(f'conversation: {conversation}, ({len(conversation)})')
        print(f'counting tokens, full input length: {full_input_tokens}')
        # if conversation contains a system prompt its length must be subtracted
        subtract = 0
        if conversation.messages[0].role == Role.SYS:
            print('system prompt found')
            subtract = int(len(conversation.messages[0].content) / 4)

        # considering User + Assistant
        if len(conversation) == 2:
            return full_input_tokens - subtract
        
        else:
            user_message_tokens = full_input_tokens - subtract
            print(f'{full_input_tokens} - {subtract} = {user_message_tokens}')
            # exclude system prompt
            for message in conversation.messages[1:]:
                prev = user_message_tokens
                user_message_tokens -= message.get_tokens()
                print(f'{prev} - {message.get_tokens()} = {user_message_tokens}')
            return user_message_tokens

    @validate_call
    def query(
        self,
        conversation: Conversation
    ):
        """Generator that returns a tuple containing:
         (response_chunk, user message tokens, assistant message tokens)"""
        # validation: conversation should contain messages
        if not conversation.messages:
            raise ProviderError('Error: empty conversation')
        last_message = conversation.messages[-1]
        if not last_message.role == Role.USER or not last_message.content:
            raise ProviderError('Error: last message is not user message')
        
        try:
            options = AVAILABLE_MODELS[self.__match_model()]['options']
            stream = self.client.chat(
                model=self.model,
                messages=[message.model_dump() for message in conversation.messages],
                stream=True,
                options=options
            )
            c = None
            for chunk in stream:
                c = chunk
                yield chunk['message']['content'], 0, 0

            # The last chunk in the ollama stream contains:
            # - `prompt_eval_count` -> input prompt tokens
            # - `eval_count` -> output tokens
            # The input prompt contains system prompt + entire conversation.
            user_msg_tokens = Ollama.user_message_token_length(
                conversation=conversation,
                full_input_tokens=c['prompt_eval_count']
            )
            assistant_msg_tokens = c['eval_count']

            yield "", user_msg_tokens, assistant_msg_tokens
        except (ResponseError, httpx.ConnectError) as err:
            raise ProviderError(err) from err

    @validate_call
    def tool_query(
        self,
        conversation: Conversation,
        tools: list | None = None
    ):
        """Implements LLM tool calling.
        :param conversation:
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
            messages=[message.model_dump() for message in conversation.messages],
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
