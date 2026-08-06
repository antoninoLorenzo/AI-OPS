import pytest

from litellm import ModelResponse, Choices, Usage
from litellm.exceptions import RateLimitError, APIError

from ai_ops.core.llm import (
    InferenceClient,
    ModelMetadata,
    ModelConfig,
    aquery,
    parse_model_string,
    get_model_capabilities,
    get_model_metadata,
)
from ai_ops.config import API_MODEL_MAX_CONTEXT_LENGTH

from test.core.mocks.llm import MockChatCompletion, mock_metadata
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


_GET_MODEL_CAPABILITIES_TESTS = [
    {
        "parameters": {"provider": "", "model_id": "", "allow_requests": False},
        "expected": {}
    },
    {
        "parameters": {"provider": "openai", "model_id": "nonexistent-model-xyz", "allow_requests": False},
        "expected": {}
    },
    {
        "parameters": {"provider": "openai", "model_id": "gemma-4-31B-it", "allow_requests": True},
        "expected": {
            # not the full list just the ones we will use
            "supported_openai_params": ["reasoning", "response_format", "tool_choice"],
            "max_input_tokens": 262144
        }
    },
    {
        "parameters": {"provider": "openai", "model_id": "gpt-4o", "allow_requests": False},
        "expected": {
            "supported_openai_params": ["response_format", "tools", "tool_choice"],
            "max_input_tokens": 128000
        }
    }
]


# get_model_metadata now treats max_context_length as Optional[int]: absent info
# or a non-positive value collapses to None, and the env override wins when set.
# allow_requests=False keeps these offline (model_info stays empty).
_MAX_CONTEXT_LENGTH_CASES = [
    {"name": "no info, no env -> None", "env": None, "expected": None},
    {"name": "env sets a positive value", "env": "128000", "expected": 128000},
    {"name": "env zero collapses to None", "env": "0", "expected": None},
    {"name": "env negative collapses to None", "env": "-5", "expected": None},
]


@pytest.mark.parametrize("test_case", _MAX_CONTEXT_LENGTH_CASES, ids=lambda tc: tc["name"])
def test_get_model_metadata_max_context_length(test_case, monkeypatch):
    if test_case["env"] is None:
        monkeypatch.delenv(API_MODEL_MAX_CONTEXT_LENGTH, raising=False)
    else:
        monkeypatch.setenv(API_MODEL_MAX_CONTEXT_LENGTH, test_case["env"])

    metadata = get_model_metadata(
        ModelConfig(model="provider/model-id"), allow_requests=False
    )
    assert metadata.max_context_length == test_case["expected"]


@pytest.mark.parametrize("test_case", _GET_MODEL_CAPABILITIES_TESTS)
def test_get_model_capabilities(test_case, internet_available):
    parameters = test_case["parameters"]
    expected = test_case["expected"]

    if parameters["allow_requests"] and not internet_available:
        pytest.skip("No internet connection available.")

    result = get_model_capabilities(**parameters)

    if not expected:
        assert not result
    else:
        assert result.get("max_input_tokens") == expected["max_input_tokens"]
        for param in expected["supported_openai_params"]:
            assert param in result.get("supported_openai_params", [])


_ASYNC_QUERY_TESTS = [
    # completion raises RateLimitError -> RuntimeError
    {
        "parameters": {
            "client": InferenceClient(
                metadata=mock_metadata,
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
                metadata=mock_metadata,
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