from typing import Union, Optional, List

from litellm import (
    ModelResponse, 
    CustomStreamWrapper, 
    Choices,
    Usage,
    Message as LiteLLMMessage
)

from ai_ops.core.llm import InferenceClient, ModelMetadata
from ai_ops.core.agent import StopTool

class MockChatCompletion:
    def __init__(
        self, 
        completion_output: ModelResponse | Exception | List[ModelResponse | Exception]
    ):
        if isinstance(completion_output, List):
            raise NotImplementedError()
        else:
            self.completion_output = completion_output

    def completion(
        self, 
        model: str,
        stream: bool = False, 
        **kwargs
    ) -> ModelResponse | CustomStreamWrapper:
        if stream:
            raise NotImplementedError()
        
        if isinstance(self.completion_output, Exception):
            raise self.completion_output
        elif isinstance(self.completion_output, ModelResponse):
            return self.completion_output

    async def acompletion(self, model: str, **kwargs) -> ModelResponse | CustomStreamWrapper:
        return self.completion(model=model, **kwargs)


def mock_query(client: InferenceClient, stream: bool = False, **kwargs) -> Union[ModelResponse, CustomStreamWrapper]:
    if stream:
        raise NotImplementedError()

    return client.client.completion(model=client.model, stream=stream)

async def mock_aquery(client: InferenceClient, stream: bool = False, **kwargs) -> Union[ModelResponse, CustomStreamWrapper]:
    if stream:
        raise NotImplementedError()

    return client.client.completion(model=client.model, stream=stream)

mock_model = ModelMetadata(
    provider="mock",
    model_id="mock",
    max_context_length=0,
    tool_use=True,
    reasoning=True,
    response_format=True,
    structured_output=True
)

mock_metadata = ModelMetadata(
    provider="mock_provider",
    model_id="mock_model_id",
    max_context_length=0,
    tool_use=True,
    reasoning=True,
    response_format=True,
    structured_output=True
)

mock_inference_client = InferenceClient(
    metadata=mock_metadata,
    client=MockChatCompletion(completion_output=ModelResponse(
        model="gpt-4o",
        choices=Choices(
            finish_reason="stop", index=0,
            message=LiteLLMMessage(role="assistant", content="content")
        ),
        usage=Usage(prompt_tokens=4, completion_tokens=4, total_tokens=8)
    ))
)