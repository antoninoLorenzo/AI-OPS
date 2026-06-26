import pytest

from litellm import (
    ModelResponse, 
    ChatCompletionSystemMessage, 
    ChatCompletionUserMessage,
    ChatCompletionAssistantMessage,
    Choices, Usage,
    Message as LiteLLMMessage
)

import ai_ops.core.agent    # we need to mock query so that it takes our mock_inference_client and raises on demand
import ai_ops.core.tracing  # we need to mock mlflow_ready to disable @agent_trace
from ai_ops.core.schema import AgentMode, StopEvent
from ai_ops.core.conversation import Conversation, Message
from ai_ops.core.context_management import RawContextView
from ai_ops.core.agent import orchestrator

from test.core.mocks.llm import InferenceClient, MockChatCompletion, mock_model, mock_query
from test.core.mocks.tool import MockTool


_message_list = [
    Message(message=ChatCompletionSystemMessage(role="system", content="content")),
    Message(message=ChatCompletionUserMessage(role="user", content="content"))
]
_AGENT_LOOP_TESTS = [
    # --- pre-conditions
    # if the given conversation doesn't have at least [system, user] messages 
    # the orchestrator raises ValueError.
    {
        "parameters": {
            "client": InferenceClient(
                metadata=mock_model,
                client=MockChatCompletion(RuntimeError("whatever"))
            ),
            "conversation": Conversation(uuid="1234", short_id="1234", messages=[_message_list[0]]),
            "tools": {MockTool.name : MockTool()},
            "context_fn": RawContextView()
        },
        "expected": ValueError
    },
    # --- stop conditions
    # any error from query (RuntimeError) should be caught and the orchestrator 
    # should yield a StopEvent with an `error` reason.
    {
        "parameters": {
            "client": InferenceClient(
                metadata=mock_model,
                client=MockChatCompletion(RuntimeError("whatever"))
            ),
            "conversation": Conversation(uuid="1234", short_id="1234", messages=_message_list),
            "tools": {MockTool.name : MockTool()},
            "context_fn": RawContextView()
        },
        "expected": [StopEvent(issuer="agent", error="whatever")]
    },
    # when the agent doesn't call any tool the orchestrator yields a StopEvent
    {
        "parameters": {
            "client": InferenceClient(
                metadata=mock_model,
                client=MockChatCompletion(ModelResponse(
                    model="gpt-4o",
                    choices=[Choices(
                        finish_reason="stop", index=0,
                        message=LiteLLMMessage(role="assistant", content="content")
                    )],
                    usage=Usage(prompt_tokens=4, completion_tokens=4, total_tokens=8)
                ))
            ),
            "conversation": Conversation(uuid="1234", short_id="1234", messages=_message_list),
            "tools": {MockTool.name : MockTool()},
            "context_fn": RawContextView()
        },
        "expected": [
            Message(
                message=ChatCompletionAssistantMessage(
                    role="assistant", content="content",
                    tool_calls=None, function_call=None
                ), 
                token_count=1
            ),
            StopEvent(issuer="agent")
        ]
    },
    # when max_iterations is reached orchestrator yields a StopEvent with the 
    # `max_iteration` flag set.
    # TODO: can't really test this without MockChatCompletion getting a list of responses
]


@pytest.mark.parametrize("test_case", _AGENT_LOOP_TESTS)
def test_agent_loop(test_case, monkeypatch):
    monkeypatch.setattr(
        target=ai_ops.core.tracing,
        name="mlflow_ready",
        value=lambda: False
    )

    # mock query to completely isolate the agent_loop from external code, even though 
    # we can just pass mock_inference_client and it would be called in query.
    monkeypatch.setattr(
        target=ai_ops.core.agent,
        name="query",
        value=mock_query
    )

    event_stream = orchestrator(**test_case["parameters"])
    if isinstance(test_case["expected"], list):
        for event, expected in zip(event_stream, test_case["expected"]):
            assert event == expected
    elif issubclass(test_case["expected"], Exception):
        with pytest.raises(test_case["expected"]):
            for event in event_stream:
                pass

