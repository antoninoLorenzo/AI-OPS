# Interface to LiteLLM
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, Union, List, Optional, runtime_checkable

import litellm
from litellm import (
    ModelResponse, 
    CustomStreamWrapper, 
    Router, 
    RetryPolicy
)
from litellm.exceptions import (
    RateLimitError,
    AuthenticationError,
    JSONSchemaValidationError,
    ContextWindowExceededError
)
from pydantic import BaseModel, SecretStr

from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)
MODEL_ID_REGEX = r"(?P<provider>.*)\/(?P<model>.*)"


# Interface for litellm.completion, in practice it's used to swap litellm.completion,
# Router.completion and mocked completion during tests through DI in query(..., client).
# Note: litellm has a mock_response for testing purposes but it only allows to return
# responses, not to raise exceptions too (i.e error handling wouldn't get tested).
@runtime_checkable
class ChatCompletion(Protocol):
    def completion(self, model: str, **kwargs) -> Union[ModelResponse, CustomStreamWrapper]:
        pass

    async def acompletion(self, model: str, **kwargs) -> Union[ModelResponse, CustomStreamWrapper]:
        pass

# litellm_params for litellm.Router, model is the "provider/model_id" string used by the router, 
# different from the `model_name` key that is what is used client side.
# See https://docs.litellm.ai/docs/routing
class ModelConfig(BaseModel):
    model: str
    api_base: Optional[str] = None
    api_key: Optional[SecretStr] = None


class ModelMetadata(BaseModel):
    provider: str
    model_id: str
    max_context_length: int
    tool_use: bool
    reasoning: bool
    response_format: bool   # JSON not guaranteed
    structured_output: bool # JSON guaranteed


@dataclass
class InferenceClient:
    models: List[ModelMetadata]
    client: ChatCompletion

    def __post_init__(self):
        if not self.models:
            raise ValueError("InferenceClient must contain at least one model")

        def all_equal(values: list) -> bool:
            return len(set(values)) == 1

        if not all_equal([m.tool_use for m in self.models]):
            raise ValueError("Not all models have the same tool_use capability")
        if not all_equal([m.reasoning for m in self.models]):
            raise ValueError("Not all models have the same reasoning capability")
        if not all_equal([m.response_format for m in self.models]):
            raise ValueError("Not all models have the same response_format capability")
        if not all_equal([m.structured_output for m in self.models]):
            raise ValueError("Not all models have the same structured_output capability")
        
        if not isinstance(self.client, ChatCompletion):
            raise ValueError("client must implement ChatCompletion protocol")

    @property
    def model(self) -> str:
        return self.models[0].model_id

    @property
    def metadata(self) -> ModelMetadata:
        return self.models[0]
    

# query is a wrapper around litellm that does it's best to ensure what the orchestrator 
# requests is satisfied. 
# It gets an InferenceClient, in practice this is made up by litellm.Router, which gives
# some fault-tolerance guarantees (such as rate-limit retries) and a list of models that 
# are inthe same capability group (i.e either all or none support the same functionality,
# ex. structured output).
# So rate-limit handling is done by litellm, query does json schema enforcement (NOT 
# parameter validation) and fallback context trimming.
def query(
    client: InferenceClient,
    messages: List,
    stream: bool = False,
    response_format: Optional[BaseModel] = None,
    max_response_format_retries: int = 3,
    tools: Optional[List] = None,
    **kwargs # additional configs to pass to litellm
) -> Union[ModelResponse, CustomStreamWrapper]:
    if response_format and not client.metadata.response_format:
        # can prompt the model to try outputting JSON
        raise NotImplementedError(f"{client.model} doesn't support response format")
    if tools and not client.metadata.tool_use:
        # can prompt the model to try
        raise NotImplementedError(f"{client.model} doesn't support tool use")

    log_event(_logger, logging.INFO, "Starting query", model=client.model)

    json_retries = 0
    trim_context = False
    while True:
        try:
            response = client.client.completion(
                model=client.model,
                messages=messages if not trim_context else litellm.utils.trim_messages(messages),
                stream=stream,
                response_format=response_format,
                tools=tools,
                **kwargs
            )

            break
        except RateLimitError as rate_limit:
            # litellm.Router did it's best, at that point rate limits can't be ignored anymore
            raise RuntimeError(f"Maximum retry limit reached: {rate_limit}")
        except ContextWindowExceededError:
            # in the possibility the context window is exceeded, retry with truncation of the context
            # length as *last resort fallback*. This gives some reliability guarantees, however to 
            # avoid degradation in the agent performance the caller (orchestrator) should employ a 
            # context management policy. 
            trim_context = True
            log_event(_logger, logging.ERROR, "Context limit exceeded", model=client.model)
            continue
        except JSONSchemaValidationError as json_err:
            # If the model supports response_format but not structured_output then JSON is not guaranteed.
            # The model is notified with a volatile message that the response was not valid JSON and the 
            # request is retried up to `max_response_format_retries`.
            json_retries += 1
            log_event(_logger, logging.ERROR, "JSON Error", retry=json_retries, model=client.model)
            if json_retries >= max_response_format_retries:
                raise RuntimeError(f"{client.model} failed generating JSON {max_response_format_retries} times: {json_err}")
            messages = messages + [
                {"role": "assistant", "content": json_err.raw_response},
                {"role": "user", "content": f"Your response was not valid JSON matching the required schema. Schema: {response_format.model_json_schema()}. Respond with only valid JSON."}
            ]
            continue

    return response


@lru_cache(maxsize=1)
def fetch_models_info():
    import requests, json
    response = requests.get(url="https://openrouter.ai/api/v1/models")
    try:
        return json.loads(response.content).get("data", [])
    except Exception:
        return []


def get_model_metadata(config: ModelConfig) -> ModelMetadata:
    metadata = {
        "provider": "",
        "model_id": "",
        "max_context_length": -1,
        "tool_use": False,
        "reasoning": False,
        "response_format": False,
        "structured_output": False,
        "native_token_counting": False
    } 

    m = re.match(pattern=MODEL_ID_REGEX, string=config.model)
    try:
        metadata['provider'] = m.group('provider')
        metadata['model_id'] = m.group('model')
        assert len(metadata['provider']) > 0
        assert len(metadata['model_id']) > 0

        # for cloud based openai compatible replace with openai, litellm
        # internally uses the openai api client with different base_url
        if metadata['provider'] == 'lightning-ai':
            metadata['provider'] = 'openai'

    except (AttributeError, AssertionError):
        raise ValueError(f"Invalid model identifier {config.model}")
    
    found_info = list(filter(
        lambda info: metadata['model_id'].lower() in info.get("id", "").lower(), 
        fetch_models_info()
    ))
    if len(found_info) > 0:
        supported_params = found_info[0].get("supported_parameters", [])
        metadata['tool_use'] = 'tools' in supported_params
        metadata['reasoning'] = 'reasoning' in supported_params
        metadata['response_format'] = 'response_format' in supported_params
        metadata['structured_output'] = 'structured_output' in supported_params

    # TODO: 
    #   identify supported context length by provider (not by model, ex. self hosted
    #   may have reduced ctx length due to ops constraints)
    #   
    #   identify tokenizer used by litellm, needed to determine whether token counting
    #   is accurate; for open-weight this could help fallback to transformers tokenizers
    log_event(
        _logger, logging.INFO, "Done loading ModelMetadata", 
        model=config.model, **metadata
    )

    return ModelMetadata(**metadata)


def build_inference_client(models: List[ModelConfig]) -> InferenceClient:
    metadata = []
    model_list = []

    for config in models:
        meta = get_model_metadata(config)
        metadata.append(meta)
        model_list.append(
            {
                "model_name": meta.model_id,
                "litellm_params": {
                    "model": f"{meta.provider}/{meta.model_id}",
                    "api_base": config.api_base,
                    # that could leak from Router logs based on what they're doing btw
                    "api_key": config.api_key.get_secret_value() 
                }
            }
        )

    # note: retry policy manages the amount of retries, not the retry behaviour
    # RateLimitError (the main reason to use the Router in this use case) uses exp. backoff
    router = Router(
        model_list=model_list,
        # rate limits usually come in req/min so do the first retry after 30s, then do two
        # other attempts, at that point raise (maybe daily budget or smth is reached).
        retry_after=30, 
        retry_policy=RetryPolicy(
            # that's an issue in how the client interacts with different providers and
            # signals an issue in the agent code.
            BadRequestErrorRetries=0,
            AuthenticationErrorRetries=0, # doesn't make sense retrying an auth error
            ContentPolicyViolationErrorRetries=0, # fuck you
            InternalServerErrorRetries=1, # just once maybe was an isolated error
            TimeoutErrorRetries=1,
            RateLimitErrorRetries=3 # that's the whole reason to use the Router
        )
    )

    return InferenceClient(models=metadata, client=router)
