from typing import Tuple, Generator
from dataclasses import dataclass

import httpx
from ollama import Client, ResponseError
from pydantic import validate_call

from src.core.llm.schema import Provider, ProviderError
from src.core.memory import Conversation
from src.utils import get_logger
import json


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
    # Added proper configuration for deepseek-r1:14b
    'deepseek-r1': {
        'options': {
            'temperature': 0.5,
            'num_ctx': 16384
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
            # Use the configured endpoint and model instead of hardcoding
            # self.inference_endpoint is already set from the parent class
            # self.model is already set from the parent class
            self.client = Client(host=self.inference_endpoint)
            logger.info(f"Connected to Ollama at {self.inference_endpoint}")
            logger.info(f"Using model: {self.model}")
        except Exception as err:
            logger.error(f"Failed to connect to Ollama: {str(err)}")
            raise RuntimeError('Initialization Failed') from err

    @staticmethod
    def user_message_token_length(
        conversation: Conversation,
        full_input_tokens: int,
        system_prompt_tokens: int
    ) -> int:
        # assumes conversation contains at least system prompt and usr message
        if len(conversation) < 2:
            return 0

        if len(conversation) == 2:
            return full_input_tokens - system_prompt_tokens
        else:
            user_message_tokens = full_input_tokens - system_prompt_tokens
            # currently conversation.messages contains all messages
            # except the assistant response, so last message must be excluded
            for message in conversation.messages[:-1]:
                user_message_tokens -= message.get_tokens()
            return user_message_tokens

    @validate_call
    def query(
        self,
        messages: Conversation
    ) -> Generator[Tuple[str, int, int], None, None]:
        """Generator that returns a tuple containing:
         (response_chunk, user message tokens, assistant message tokens)"""
        try:
            # Get model options
            base_model = self.__match_model()
            options = AVAILABLE_MODELS[base_model]['options']

            # Add these lines before your connections
            print(f"Attempting to connect to Ollama at: {self.inference_endpoint}")
            print(f"Using model: {self.model}")
            print(f"Request payload: {json.dumps(messages.model_dump())[:500]}...")
            
            # Log query attempt
            logger.debug(f"Sending query to {self.model} with {len(messages)} messages")
            
            try:
                # Create a streaming request
                stream = self.client.chat(
                    model=self.model,
                    messages=messages.model_dump(),
                    stream=True,
                    options=options
                )
                
                c = None  # Last chunk for token counting
                for chunk in stream:
                    c = chunk
                    # Handle different response formats
                    if 'message' in chunk and 'content' in chunk['message']:
                        # Standard format
                        yield chunk['message']['content'], 0, 0
                    elif 'response' in chunk:
                        # Older format
                        yield chunk['response'], 0, 0
                    else:
                        # Log unexpected chunk format
                        logger.warning(f"Unexpected chunk format: {chunk}")
                
                # The last chunk in the ollama stream contains:
                # - `prompt_eval_count` -> input prompt tokens
                # - `eval_count` -> output tokens
                if c:
                    # Check if token counts are available
                    prompt_tokens = c.get('prompt_eval_count', 0)
                    response_tokens = c.get('eval_count', 0)
                    
                    # Calculate user message tokens
                    system_prompt_length_estimate = int(len(messages.messages[0].content) / 4)
                    user_msg_tokens = Ollama.user_message_token_length(
                        conversation=messages,
                        full_input_tokens=prompt_tokens,
                        system_prompt_tokens=system_prompt_length_estimate
                    )
                    
                    # Final yield with token counts
                    yield "", user_msg_tokens, response_tokens
                    
                    # Log token usage
                    logger.debug(f"Query completed. Tokens: {prompt_tokens} input, {response_tokens} output")
                else:
                    # No chunks were received
                    logger.warning("No response chunks received from Ollama")
                    yield "", 0, 0
                    
            except Exception as e:
                # Handle specific errors
                error_msg = str(e)
                logger.error(f"Error during streaming: {error_msg}")
                
                # Try fallback to non-streaming for some models
                if "deepseek" in self.model.lower():
                    logger.info("Attempting fallback to non-streaming mode for deepseek model")
                    try:
                        response = self.client.chat(
                            model=self.model,
                            messages=messages.model_dump(),
                            stream=False,
                            options=options
                        )
                        
                        # Return the complete response
                        if 'message' in response and 'content' in response['message']:
                            yield response['message']['content'], 0, 0
                            
                            # Add token counts if available
                            prompt_tokens = response.get('prompt_eval_count', 0)
                            response_tokens = response.get('eval_count', 0)
                            yield "", prompt_tokens, response_tokens
                        else:
                            logger.warning(f"Unexpected response format in fallback: {response}")
                            yield "", 0, 0
                    except Exception as fallback_err:
                        logger.error(f"Fallback also failed: {str(fallback_err)}")
                        raise ProviderError(f"Streaming and fallback failed: {str(e)} -> {str(fallback_err)}")
                else:
                    # Re-raise the original error
                    raise
                    
        except (ResponseError, httpx.ConnectError) as err:
            logger.error(f"Provider error: {str(err)}")
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

        try:
            tool_response = self.client.chat(
                model=self.model,
                messages=messages.model_dump(),
                tools=tools
            )

            return tool_response if tool_response['message'].get('tool_calls') \
                else None
        except Exception as err:
            logger.error(f"Tool query error: {str(err)}")
            raise ProviderError(f"Tool query failed: {str(err)}") from err

    def __match_model(self) -> str | None:
        """Check if a model is supported, the model availability on Ollama
        is upon the user; ProviderError is raised if not available."""
        for model in list(AVAILABLE_MODELS.keys()):
            if self.model.startswith(model):
                return model
        return None