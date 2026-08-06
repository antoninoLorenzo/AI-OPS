# Interface to LiteLLM
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Protocol, Tuple, Union, runtime_checkable

import litellm
from litellm import CustomStreamWrapper, ModelResponse, RetryPolicy, Router
from litellm.exceptions import (
    APIError,
    AuthenticationError,
    ContextWindowExceededError,
    JSONSchemaValidationError,
    RateLimitError,
)
from pydantic import BaseModel, SecretStr

from ai_ops.config import API_MODEL_MAX_CONTEXT_LENGTH
from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)


@runtime_checkable
class ChatCompletion(Protocol):
    def completion(self, model: str, **kwargs) -> Union[ModelResponse, CustomStreamWrapper]:
        pass

    async def acompletion(self, model: str, **kwargs) -> Union[ModelResponse, CustomStreamWrapper]:
        pass


class ModelConfig(BaseModel):
    model: str
    """Fully-qualified Model ID (ex. `provider/model_id`, `huggingface/namespace/repo`)."""
    api_base: Optional[str] = None
    """API endpoint for the LLM Provider."""
    api_key: Optional[SecretStr] = None
    """API key for the LLM Provider."""


class ModelMetadata(BaseModel):
    provider: str
    model_id: str
    max_context_length: Optional[int] = None
    tool_use: bool
    reasoning: bool
    response_format: bool   # JSON not guaranteed
    structured_output: bool # JSON guaranteed


@dataclass
class InferenceClient:
    metadata: ModelMetadata
    client: ChatCompletion

    @property
    def model(self) -> str:
        return self.metadata.model_id


async def aquery(
    client: InferenceClient,
    messages: List[dict],
    tools: Optional[List] = None,
    **kwargs
) -> ModelResponse | CustomStreamWrapper:
    """
    :param tools: Serialized tool list.
    :raises `RuntimeError`: Fatal unrecoverable error.
    """
    log_event(_logger, logging.DEBUG, "Starting async query", model=client.model)
    try:
        response = await client.client.acompletion(
            model=client.model,
            messages=messages,
            tools=tools,
            **kwargs
        )
        log_event(_logger, logging.DEBUG, "Completed async query", model=client.model)
    except RateLimitError as rate_limit:
        raise RuntimeError(f"Maximum retry limit reached: {rate_limit}")
    except APIError as fatal:
        log_event(
            _logger, logging.ERROR, "API Error", 
            status_code=fatal.status_code,
            error_message=fatal.message,
            model=fatal.model,
            provider=fatal.llm_provider
        )
        raise RuntimeError(f"APIError in query")

    return response


# query is a wrapper around litellm that does it's best to ensure what the orchestrator 
# requests is satisfied. 
# It gets an InferenceClient, in practice this is made up by litellm.Router, which gives
# some fault-tolerance guarantees (such as rate-limit retries) and a list of models that 
# are inthe same capability group (i.e either all or none support the same functionality,
# ex. structured output).
# So rate-limit handling is done by litellm, query does json schema enforcement (NOT 
# parameter validation) and fallback context trimming.
# https://docs.litellm.ai/docs/exception_mapping
def query(
    client: InferenceClient,
    messages: List,
    tools: Optional[List] = None,
    stream: bool = False,
    **kwargs # additional configs to pass to litellm
) -> Union[ModelResponse, CustomStreamWrapper]:
    """
    :param tools: Serialized tool list.
    :raises `RuntimeError`: Fatal unrecoverable error.
    """
    log_event(_logger, logging.INFO, "Starting query", model=client.model)

    try:
        response = client.client.completion(
            model=client.model,
            messages=messages,
            stream=stream,
            tools=tools,
            **kwargs
        )
    except RateLimitError as rate_limit:
        raise RuntimeError(f"Maximum retry limit reached: {rate_limit}")
    except litellm.exceptions.APIError as fatal:
        log_event(
            _logger, logging.ERROR, "API Error", 
            status_code=fatal.status_code,
            message=fatal.message,
            model=fatal.model,
            provider=fatal.llm_provider
        )
        raise RuntimeError(f"APIError in query")
        
    return response


def parse_model_string(model: str) -> Tuple[str, str]:
    """
    Takes in input the fully qualified model id and returns the provider and 
    the model name.
    :param model: 
        Model id in the format `provider/model` ex. `openai/gpt-4o`.
        > Note: for some use cases even three components are allowed, such as 
        `huggingface/namespace/repo`.
    :raises ValueError: the fully qualified model identifier is malformed.
    """
    # Some providers are not explicitly supported by litellm however they can 
    # still be used since they follow openai format.
    provider_mapping = {
        "lightning-ai": "openai"
    }

    m = re.match(pattern=r"(?P<provider>[^/]+)\/(?P<model>.+)", string=model)
    try:
        model_provider = m.group('provider')
        model_name = m.group('model')
        assert len(model_provider) > 0
        assert len(model_name) > 0

        if model_provider in provider_mapping:
            model_provider = provider_mapping[model_provider]

        return model_provider, model_name
    except (AttributeError, AssertionError):
        raise ValueError(f"Invalid model identifier {model}")


@lru_cache(maxsize=1)
def fetch_models_info(model: str):
    import json

    import requests
    response = requests.get(url="https://openrouter.ai/api/v1/models")
    try:
        return json.loads(response.content).get("data", [])
    except Exception:
        return []


def get_model_capabilities(provider: str, model_id: str, allow_requests: bool = True) -> List[str]:
    """
    Gets the list of supported parameters for the model.
    """
    # If litellm doesn't support the provider we use the OpenRouter API, however 
    # it still doesn't address all edge-cases. 
    # One is vLLM (/v1/models ???)
    try:
        model_info = litellm.get_model_info(model=f"{provider}/{model_id}")
        return {
            "supported_openai_params": model_info.get("supported_openai_params", []),
            "max_input_tokens": model_info.get("max_input_tokens", -1),
        }
    except Exception:
        if not allow_requests:
            return []

        available_models = fetch_models_info(model=model_id)
        if not available_models:
            return []

        model_info = list(
            filter(
                lambda info: model_id.lower() in info.get("id", "").lower(),
                available_models
            )
        )
        if not model_info:
            return []
        model_info = model_info[0]

        # conform to litellm naming
        model_info["supported_openai_params"] = model_info.pop("supported_parameters")
        model_info["max_input_tokens"] = model_info.pop("context_length")
        return model_info


def get_model_metadata(config: ModelConfig, allow_requests: bool = True) -> ModelMetadata:
    """
    Creates `ModelMetadata` from `ModelConfig`.
    
    :raises ValueError: `ModelConfig.model` is an invalid identifier.
    """
    metadata = {
        "provider": "",
        "model_id": "",
        "max_context_length": None,
        "tool_use": False,
        "reasoning": False,
        "response_format": False,
        "structured_output": False,
        "native_token_counting": False
    } 

    metadata['provider'], metadata['model_id'] = parse_model_string(config.model)
    model_info = get_model_capabilities(
        provider=metadata["provider"], 
        model_id=metadata["model_id"],
        allow_requests=allow_requests
    )

    if model_info:
        supported_params = model_info.get("supported_openai_params", [])
        metadata['tool_use'] = 'tools' in model_info
        metadata['reasoning'] = 'reasoning' in model_info
        metadata['response_format'] = 'response_format' in model_info
        metadata['structured_output'] = 'structured_output' in model_info
        metadata['max_context_length'] = model_info.get("max_input_tokens")

    # allow specifying model max context length (ex vLLM)
    env_value = os.environ.get(API_MODEL_MAX_CONTEXT_LENGTH)
    if env_value is not None:
        metadata['max_context_length'] = int(env_value)
    if metadata['max_context_length'] is not None and metadata['max_context_length'] <= 0:
        metadata['max_context_length'] = None

    log_event(
        _logger, logging.INFO, "Done loading ModelMetadata", 
        model=config.model, **metadata
    )

    return ModelMetadata(**metadata)


def build_inference_client(config: ModelConfig) -> InferenceClient:
    model_metadata = get_model_metadata(config)
    
    litellm_params = {
        "model": f"{model_metadata.provider}/{model_metadata.model_id}"
    }

    if config.api_base:
        litellm_params["api_base"] = config.api_base
    if config.api_key:
        litellm_params["api_key"] = config.api_key.get_secret_value()

    model_list = [
        {
            "model_name": model_metadata.model_id,
            "litellm_params": litellm_params
        }
    ]

    # note: retry policy manages the amount of retries, not the retry behaviour
    # RateLimitError (the main reason to use the Router in this use case) uses exp. backoff
    router = Router(
        model_list=model_list,
        # rate limits usually come in req/min so do the first retry after 30s, then do two
        # other attempts, at that point raise (maybe daily budget or smth is reached).
        retry_after=45, 
        retry_policy=RetryPolicy(
            # that's an issue in how the client interacts with different providers and
            # signals an issue in the agent code.
            BadRequestErrorRetries=0,
            AuthenticationErrorRetries=0, # doesn't make sense retrying an auth error
            ContentPolicyViolationErrorRetries=0, # fuck you
            InternalServerErrorRetries=1, # just once maybe was an isolated error
            TimeoutErrorRetries=1,
            RateLimitErrorRetries=5 # that's the whole reason to use the Router
        )
    )

    return InferenceClient(metadata=model_metadata, client=router)
