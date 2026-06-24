# Tests for agent tracing, for it's very nature it performs integration testing.
# The following env variables have to be set, otherwise tests will skip.
# AI_OPS_OBSERVABILITY_BACKEND=mlflow, 
# MLFLOW_TRACKING_URI
# MLFLOW_TRACKING_USERNAME
# MLFLOW_TRACKING_PASSWORD
# AI_OPS_TESTING_MODEL=provider/model_id + LLM_API_BASE, LLM_API_KEY (optional)
import os
import uuid
from typing import List, cast

import pytest
import litellm
import mlflow # TODO: that's optional, see pytest.importskip
from mlflow.entities import SpanType
from pydantic import BaseModel
from dotenv import load_dotenv

from ai_ops.core.schema import Event, ToolCallEvent, ToolResultEvent
from ai_ops.core.conversation import Conversation, Message
from ai_ops.core.tracing import agent_trace, mlflow_ready
from ai_ops.core._mlflow import AGENT_TRACE_NAME

load_dotenv()

# TODO: should delete the traces, however it seems like there's no way to do that from SDK

# conversation doesn't need to be passed, however that way we can specify a 
# session name to distinguish it from normal traces.
@agent_trace
def mock_agent_loop(conversation: Conversation, events: List[Event]):
    for event in events:
        yield event

class MockModel(BaseModel):
    val: int = 1
    
_TOOL_TRACING_TESTS = [
    {
        "conversation": Conversation(
            uuid=f"test_{str(uuid.uuid4())}",
            short_id=1,
            messages=[Message(message={"role": "user", "content": "asd"})]
        ),
        "events": [
            ToolCallEvent(call_id="123", name="mock_tool", args=MockModel()),
            ToolResultEvent(call_id="123", name="mock_tool", args=MockModel(), result=MockModel())
        ]
    }
]


@pytest.mark.skipif(not mlflow_ready(), reason="MLFlow disabled, skipping test.")
@pytest.mark.parametrize("test_case", _TOOL_TRACING_TESTS)
def test_tool_call_tracing(test_case):
    conv = test_case["conversation"]
    events = test_case["events"]
    for _ in mock_agent_loop(conversation=conv, events=events):
        pass

    trace_id = mlflow.get_last_active_trace_id()
    assert trace_id is not None, "No trace was created"

    trace = mlflow.get_trace(trace_id)
    assert trace is not None

    # verify orchestrator span exists
    agent_spans = trace.search_spans(span_type=SpanType.AGENT)
    assert len(agent_spans) == 1
    assert agent_spans[0].name == AGENT_TRACE_NAME

    # verify tool spans
    tool_spans = trace.search_spans(span_type=SpanType.TOOL)
    assert len(tool_spans) == 1
    assert tool_spans[0].name == "mock_tool"

    # verify inputs/outputs were captured
    assert tool_spans[0].inputs is not None
    assert tool_spans[0].outputs is not None

    # verify tool span is child of orchestrator
    assert tool_spans[0].parent_id == agent_spans[0].span_id


@agent_trace
def llm_agent_loop(conversation: Conversation):
    model = os.environ["AI_OPS_TESTING_MODEL"]
    api_base = os.environ.get("LLM_API_BASE")
    api_key = os.environ.get("LLM_API_KEY")
    
    response = litellm.completion(
        model=model,
        messages=conversation.messages,
        max_tokens=10,
        base_url=api_base,
        api_key=api_key
    )
    response_message = response.choices[0].message
    print(f'\nllm_agent_loop DEBUG: {response_message}') # use -s

    yield Message(
        message=cast(litellm.ChatCompletionAssistantMessage, response_message.model_dump()),
        token_count=litellm.token_counter(text=response_message.content or "")
    )


_LLM_TRACING_TESTS = [
    {
        "conversation": Conversation(
            uuid=f"test_{str(uuid.uuid4())}",
            short_id=1,
            messages=[Message(message={"role": "user", "content": "say hi"})]
        ),
    }
]

@pytest.mark.skipif(
    os.environ.get("AI_OPS_TESTING_MODEL", None) is None, 
    reason="Missing test model. Set AI_OPS_TESTING_MODEL env var."
)
@pytest.mark.parametrize("test_case", _LLM_TRACING_TESTS)
def test_llm_call_tracing(test_case):
    conv = test_case["conversation"]
    
    try:
        for _ in llm_agent_loop(conv):
            pass
    except Exception as llm_err:
        # note: this is in place to avoid false-positives due to some provider
        # or configuration error, but since the function is wrapped by agent_trace
        # it may reasonably be an error in the tracing code.
        pytest.skip(f"Failed generating response: {llm_err}")

    trace_id = mlflow.get_last_active_trace_id()
    assert trace_id is not None, "No trace was created"

    trace = mlflow.get_trace(trace_id)
    assert trace is not None

    llm_spans = trace.search_spans(span_type=SpanType.LLM)
    assert len(llm_spans) == 1


