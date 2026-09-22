import pytest

from litellm import ModelResponse, Choices, Usage
from litellm.exceptions import RateLimitError, APIError

from ai_ops.core.llm import (
    InferenceClient,
    ModelConfig,
    aquery,
    parse_model_string,
)
from ai_ops.config import API_MODEL_MAX_CONTEXT_LENGTH

from test.core.mocks.llm import MockChatCompletion, mock_model_config
from test.core.mocks.tool import MockTool


@pytest.fixture(scope="module")
def internet_available():
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        yield True
    except OSError:
        yield False


_PARSE_MODEL_STRING_TESTS = [
    { "model": "", "expected": ValueError },
    { "model": "random-string", "expected": ValueError },
    { 
        "model": "openai/gpt-4o", 
        "expected": {"provider": "openai", "model_id": "gpt-4o"} 
    },
    { 
        "model": "lightning-ai/gemma-4-31B-it", 
        "expected": {"provider": "openai", "model_id": "gemma-4-31B-it"} 
    },
    { 
        "model": "huggingface/meta-llama/Llama-2-7b", 
        "expected": {"provider": "huggingface", "model_id": "meta-llama/Llama-2-7b"} 
    }
]

@pytest.mark.parametrize("test_case", _PARSE_MODEL_STRING_TESTS)
def test_parse_model_string(test_case):
    expected = test_case["expected"]
    if isinstance(expected, dict):
        assert parse_model_string(test_case["model"]) == (
            expected["provider"], 
            expected["model_id"]
        )
    elif issubclass(expected, Exception):
        with pytest.raises(expected):
            parse_model_string(test_case["model"])

_ASYNC_QUERY_TESTS = [
    # completion raises RateLimitError -> RuntimeError
    {
        "parameters": {
            "client": InferenceClient(
                config=mock_model_config,
                client=MockChatCompletion(completion_output=RateLimitError(
                    message="u gotta pay", llm_provider="deez", model="nuts"
                ))
            ),
            "messages": [
                {"role": "system", "content": "YoU aRe aN Ay exPeRt!!1!"},
                {"role": "user", "content": "aaaaaaa"}
            ],
        },
        "expected": RuntimeError
    },
    # completion raises APIError -> RuntimeError
    {
        "parameters": {
            "client": InferenceClient(
                config=mock_model_config,
                client=MockChatCompletion(completion_output=APIError(
                    status_code=500, message="pov: google ai studio", 
                    llm_provider="agdsgd", model="AGI"
                ))
            ),
            "messages": [
                {"role": "system", "content": "YoU aRe aN Ay exPeRt!!1!"},
                {"role": "user", "content": "bbbbbbb"}
            ],
        },
        "expected": RuntimeError
    }
]

@pytest.mark.asyncio
@pytest.mark.parametrize("test_case", _ASYNC_QUERY_TESTS)
async def test_async_query(test_case):
    parameters = test_case["parameters"]
    expected = test_case["expected"]

    if issubclass(expected, Exception):
        with pytest.raises(expected):
            _ = await aquery(**parameters)
