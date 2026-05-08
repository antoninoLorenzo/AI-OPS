from litellm import (
    ModelResponse, 
    CustomStreamWrapper, 
    Choices,
    Usage
)

from ai_ops.core.llm import InferenceClient, ModelMetadata


class MockChatCompletion:
    def completion(
        self, 
        model: str, 
        stream: bool = False, 
        **kwargs
    ) -> ModelResponse | CustomStreamWrapper:
        if stream:
            raise NotImplementedError()
        message = {"role": "assistant", "content": "hi"}
        return ModelResponse(
            model=model,
            choices=[Choices(message=message)],
            usage=Usage(
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                reasoning_tokens=None
            )
        )

    async def acompletion(self, model: str, **kwargs) -> ModelResponse | CustomStreamWrapper:
        raise NotImplementedError()


mock_inference_client = InferenceClient(
    models=[
        ModelMetadata(
            provider="mock",
            model_id="mock",
            max_context_length=0,
            tool_use=True,
            reasoning=True,
            response_format=True,
            structured_output=True
        )
    ],
    client=MockChatCompletion()
)