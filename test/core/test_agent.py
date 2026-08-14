import pytest

from litellm import (
    ModelResponse,
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage,
    ChatCompletionAssistantMessage,
    ChatCompletionMessageToolCall,
    Choices, Usage, Function,
    Message as LiteLLMMessage
)

import ai_ops.core.agent    # we need to mock query so that it takes our mock_inference_client and raises on demand
import ai_ops.core.tracing  # we need to mock mlflow_ready to disable @agent_trace
from ai_ops.core.schema import (
    AgentMode,
    StopEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from ai_ops.core.conversation import Message
from ai_ops.core.storage import Session
from ai_ops.core.agent import aorchestrator, orchestrator

from test.core.mocks.llm import InferenceClient, MockChatCompletion, mock_aquery, mock_model, mock_query
from test.core.mocks.tool import MockTool, MockConfirmTool, MockIn, MockOut, NOT_ADMITTED_VAL
from ai_ops.core.tools import StopReason, StopTool


_message_list = [
    Message(agent_id="react", message=ChatCompletionSystemMessage(role="system", content="content")),
    Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content="content"))
]
_AGENT_LOOP_TESTS = [
    # --- stop conditions
    # any error from query (RuntimeError) should be caught and the orchestrator 
    # should yield a StopEvent with an `error` reason.
    {
        "parameters": {
            "client": InferenceClient(
                metadata=mock_model,
                client=MockChatCompletion(RuntimeError("whatever"))
            ),
            "session": Session(uuid="1234", short_id="1234", messages=_message_list),
            "tools": {MockTool.name : MockTool()},
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
            "session": Session(uuid="1234", short_id="1234", messages=_message_list),
            "tools": {MockTool.name : MockTool()},
        },
        "expected": [
            Message(agent_id="react", 
                message={"role": "assistant", "content": "content", "tool_calls": None, "function_call": None}, 
                token_count=1,
                model_id=mock_model.model_id
            ),
            StopEvent(issuer="agent")
        ]
    },
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


@pytest.mark.parametrize("test_case", _AGENT_LOOP_TESTS)
async def test_agent_loop_async(test_case, monkeypatch):
    monkeypatch.setattr(
        target=ai_ops.core.tracing,
        name="mlflow_ready",
        value=lambda: False
    )

    # mock aquery to completely isolate the agent loop from external code.
    monkeypatch.setattr(
        target=ai_ops.core.agent,
        name="aquery",
        value=mock_aquery
    )

    event_stream = aorchestrator(**test_case["parameters"])
    if isinstance(test_case["expected"], list):
        expected = iter(test_case["expected"])
        async for event in event_stream:
            assert event == next(expected)
    elif issubclass(test_case["expected"], Exception):
        with pytest.raises(test_case["expected"]):
            async for event in event_stream:
                pass


# --- confirmation flow (aorchestrator only)
# These drive a single blocked tool call (MockConfirmTool always blocks) and
# assert the admission/confirmation branch. Iterations are bounded to 1 since the
# mock model keeps returning the same tool call.

_CONFIRM_MESSAGE_LIST = [
    Message(agent_id="react", message=ChatCompletionSystemMessage(role="system", content="content")),
    Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content="content"))
]


def _tool_call_response(tool_name: str, args_json: str, call_id: str = "call_1") -> ModelResponse:
    return ModelResponse(
        model="gpt-4o",
        choices=[Choices(
            finish_reason="tool_calls", index=0,
            message=LiteLLMMessage(
                role="assistant", content=None,
                tool_calls=[ChatCompletionMessageToolCall(
                    id=call_id, type="function",
                    function=Function(name=tool_name, arguments=args_json)
                )]
            )
        )],
        usage=Usage(prompt_tokens=4, completion_tokens=4, total_tokens=8)
    )


def _stop_tool_parameters():
    return {
        "client": InferenceClient(
            metadata=mock_model,
            client=MockChatCompletion(_tool_call_response(
                StopTool.name,
                StopReason(reason="objective reached").model_dump_json(),
                call_id="stop1",
            ))
        ),
        "session": Session(uuid="1234", short_id="1234", messages=list(_message_list)),
        "tools": {MockTool.name: MockTool()},
    }


def test_orchestrator_stop_tool_carries_call_id(monkeypatch):
    # the stop tool is an orchestration primitive; the StopEvent must carry the
    # stop tool_call id so the runner can answer it with a synthetic tool result.
    monkeypatch.setattr(target=ai_ops.core.tracing, name="mlflow_ready", value=lambda: False)
    monkeypatch.setattr(target=ai_ops.core.agent, name="query", value=mock_query)

    stop_events = [e for e in orchestrator(**_stop_tool_parameters()) if isinstance(e, StopEvent)]
    assert stop_events == [StopEvent(issuer="agent", reason="objective reached", call_id="stop1")]


async def test_aorchestrator_stop_tool_carries_call_id(monkeypatch):
    monkeypatch.setattr(target=ai_ops.core.tracing, name="mlflow_ready", value=lambda: False)
    monkeypatch.setattr(target=ai_ops.core.agent, name="aquery", value=mock_aquery)

    events = await _collect_events(aorchestrator(**_stop_tool_parameters()))
    stop_events = [e for e in events if isinstance(e, StopEvent)]
    assert stop_events == [StopEvent(issuer="agent", reason="objective reached", call_id="stop1")]


async def _collect_events(event_stream):
    """Drain an aorchestrator stream, keeping only Event instances (dropping the
    raw assistant Message whose token_count is brittle to assert on)."""
    events = []
    async for event in event_stream:
        if isinstance(event, (ToolCallEvent, ToolResultEvent, StopEvent)):
            events.append(event)
    return events


def _run_confirm_case(monkeypatch, mode, confirm, call_id="call_1", val=5):
    monkeypatch.setattr(target=ai_ops.core.tracing, name="mlflow_ready", value=lambda: False)
    monkeypatch.setattr(target=ai_ops.core.agent, name="aquery", value=mock_aquery)

    client = InferenceClient(
        metadata=mock_model,
        client=MockChatCompletion(_tool_call_response(
            tool_name=MockConfirmTool.name,
            args_json=MockIn(val=val).model_dump_json(),
            call_id=call_id
        ))
    )
    return aorchestrator(
        client=client,
        session=Session(uuid="1234", short_id="1234", messages=_CONFIRM_MESSAGE_LIST),
        tools={MockConfirmTool.name: MockConfirmTool()},
        mode=mode,
        max_iterations=1,
        confirm=confirm
    )


async def test_aorchestrator_unsupervised_blocked_skips(monkeypatch):
    # UNSUPERVISED: a blocked call is not executed and `confirm` is never awaited.
    async def confirm_must_not_be_called(_):
        raise AssertionError("confirm should not be called in UNSUPERVISED mode")

    events = await _collect_events(_run_confirm_case(
        monkeypatch, AgentMode.UNSUPERVISED, confirm_must_not_be_called
    ))

    assert events == [
        ToolCallEvent(call_id="call_1", name=MockConfirmTool.name, args=MockIn(val=5), requires_confirmation=False),
        ToolResultEvent(call_id="call_1", name=MockConfirmTool.name, args=MockIn(val=5), result=MockOut(val=NOT_ADMITTED_VAL)),
    ]


async def test_aorchestrator_supervised_blocked_approved_executes(monkeypatch):
    # SUPERVISED: a blocked call prompts; on approval it executes normally.
    async def approve(_):
        return True

    events = await _collect_events(_run_confirm_case(
        monkeypatch, AgentMode.SUPERVISED, approve
    ))

    assert events == [
        ToolCallEvent(call_id="call_1", name=MockConfirmTool.name, args=MockIn(val=5), requires_confirmation=True),
        ToolResultEvent(call_id="call_1", name=MockConfirmTool.name, args=MockIn(val=5), result=MockOut(val=5)),
    ]


async def test_aorchestrator_supervised_blocked_denied_skips(monkeypatch):
    # SUPERVISED: a blocked call prompts; on denial it is not executed.
    async def deny(_):
        return False

    events = await _collect_events(_run_confirm_case(
        monkeypatch, AgentMode.SUPERVISED, deny
    ))

    assert events == [
        ToolCallEvent(call_id="call_1", name=MockConfirmTool.name, args=MockIn(val=5), requires_confirmation=True),
        ToolResultEvent(call_id="call_1", name=MockConfirmTool.name, args=MockIn(val=5), result=MockOut(val=NOT_ADMITTED_VAL)),
    ]

