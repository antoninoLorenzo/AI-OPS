# Interface to LiteLLM
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, runtime_checkable

import litellm
from litellm import CustomStreamWrapper, ModelResponse, RetryPolicy, Router
from litellm.exceptions import (
    APIError,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ai_ops.config import (
    API_MODEL_MAX_CONTEXT_LENGTH,
    DEFAULT_MAX_CONTEXT_LENGTH,
    DEFAULT_TEMPERATURE,
    TEMPERATURE_ENV,
    env_or_default,
)
from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)


@runtime_checkable
class ChatCompletion(Protocol):
    def completion(self, model: str, **kwargs) -> ModelResponse | CustomStreamWrapper:
        pass

    async def acompletion(self, model: str, **kwargs) -> ModelResponse | CustomStreamWrapper:
        pass


class ModelConfig(BaseModel):
    # frozen -> hashable, so it can key the inference-client cache below.
    model_config = ConfigDict(frozen=True)

    model: str
    """Fully-qualified Model ID (ex. `provider/model_id`, `huggingface/namespace/repo`)."""
    
    api_base: str | None = None
    """API endpoint for the LLM Provider."""

    api_key: SecretStr | None = None
    """API key for the LLM Provider."""
 
    temperature: float = Field(
        default_factory=lambda: env_or_default(TEMPERATURE_ENV, DEFAULT_TEMPERATURE, float)
    )

    max_context_length: int = Field(
        default_factory=lambda: env_or_default(API_MODEL_MAX_CONTEXT_LENGTH, DEFAULT_MAX_CONTEXT_LENGTH, int)
    )
    """Maximum context length supported by LLM/API."""


@dataclass
class InferenceClient:
    config: ModelConfig
    client: ChatCompletion

    @property
    def model_id(self) -> str:
        # this exists because litellm Router wants only the model_id on completion
        _, model_name = parse_model_string(self.config.model)
        return model_name

    @property
    def model_provider(self) -> str:
         # this exists because litellm Router wants only the model_id on completion
        model_provider, _ = parse_model_string(self.config.model)
        return model_provider


async def aquery(
    client: InferenceClient,
    messages: list[dict],
    tools: list | None = None,
    **kwargs
) -> ModelResponse | CustomStreamWrapper:
    """
    :param tools: Serialized tool list.
    :raises `RuntimeError`: Fatal unrecoverable error.
    """
    log_event(_logger, logging.DEBUG, "Starting async query", model=client.model_id)
    try:
        response = await client.client.acompletion(
            model=client.model_id,
            messages=messages,
            tools=tools,
            temperature=client.config.temperature,
            **kwargs
        )
        log_event(_logger, logging.DEBUG, "Completed async query", model=client.model_id)
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
        raise RuntimeError("APIError in query")

    return response


def query(
    client: InferenceClient,
    messages: list,
    tools: list | None = None,
    stream: bool = False,
    **kwargs # additional configs to pass to litellm
) -> ModelResponse | CustomStreamWrapper:
    """
    :param tools: Serialized tool list.
    :raises `RuntimeError`: Fatal unrecoverable error.
    """
    log_event(_logger, logging.INFO, "Starting query", model=client.model_id)

    try:
        response = client.client.completion(
            model=client.model_id,
            messages=messages,
            stream=stream,
            tools=tools,
            temperature=client.config.temperature,
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
        raise RuntimeError("APIError in query")
        
    return response


@lru_cache(maxsize=3)
def parse_model_string(model: str) -> tuple[str, str]:
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


# Inference clients cached by `ModelConfig`
_INFERENCE_CLIENTS: dict[ModelConfig, InferenceClient] = {}


def build_inference_client(config: ModelConfig) -> InferenceClient:
    cached = _INFERENCE_CLIENTS.get(config)
    if cached is not None:
        return cached

    model_provider, model_name = parse_model_string(config.model)
    litellm_params = {
        "model": f"{model_provider}/{model_name}"
    }

    if config.api_base:
        litellm_params["api_base"] = config.api_base
    if config.api_key:
        litellm_params["api_key"] = config.api_key.get_secret_value()

    model_list = [
        {
            "model_name": model_name,
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

    client = InferenceClient(config=config, client=router)
    _INFERENCE_CLIENTS[config] = client
    return client


def get_inference_client(config: ModelConfig) -> InferenceClient:
    """Resolve (and cache) the `InferenceClient` for a `ModelConfig`."""
    return build_inference_client(config)


def check_inference_client(client: InferenceClient) -> None:
    """Startup sanity check, raise if err."""
    query(
        client=client,
        messages=[{"role": "user", "content": "ping"}],
        tools=None,
        max_tokens=1
    )
