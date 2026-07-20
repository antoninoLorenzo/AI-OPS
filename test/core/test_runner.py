import functools

import pytest

from litellm import (
    ChatCompletionUserMessage,
    ChatCompletionAssistantMessage,
    ChatCompletionToolMessage,
    ChatCompletionAssistantToolCall,
    ChatCompletionToolCallFunctionChunk
)
from ai_ops.core.schema import (
    AgentMode,
    UserMessageEvent,
    TextEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolConfirmationEvent,
    ToolResultEvent,
    StopEvent,
    ToolErrorFailure,
    ToolErrorEvent
)
import ai_ops.core.runner
from ai_ops.core.runner import AgentRunner, AgentConfig
from ai_ops.core.conversation import (
    Message, 
    ConversationStore, 
    Conversation, 
    get_conversation_store, 
    get_token_count
)

from test.core.mocks.agent import mock_aorchestrator, mock_orchestrator
from test.core.mocks.llm import mock_inference_client
from test.core.mocks.tool import (
    MockTool,
    MockConfirmTool,
    MockIn,
    MockOut,
    NOT_ADMITTED_VAL,
    register_mock_tool,
    register_mock_confirm_tool,
)


# Test cases follow the format 
# {
#   "events": List[Message | Event] | Exception (agent orchestartor output),
#   "persisted_messages": List[Message] (conversation content),
#   "expected_events": List[Event] (what the client receives)
# }
# What's not being tested:
# * empty user message, can't happen because pydantic would raise before
# * user sends message during agent loop, a pain in the ass to simulate
_RUNNER_RUN_TEST_CASES = [
    # Case 1
    # The agent calls a tool but doesn't provide any text -> content is None,
    # then we get a StopEvent (should be called as tool but keep it simple).
    # We expect that:
    # * the conversation contains Assistant and Tool messages.
    # * the client gets ToolCallEvent -> ToolResultEvent -> StopEvent.
    {
        "conversation_id": "case_1",
        "user_message": "Hello",
        "events": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        type="function",
                        id="1234",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments=MockIn(val=1).model_dump_json()
                        )
                    )
                ]
            )),
            ToolCallEvent(
                call_id="1234",
                name=MockTool.name,
                args=MockIn(val=1)
            ),
            ToolResultEvent(
                call_id="1234",
                name=MockTool.name,
                args=MockIn(val=1),
                result=MockOut(val=1)
            ),
            StopEvent(issuer="agent", reason="Done")
        ],
        "persisted_messages": [
            Message(message=ChatCompletionUserMessage(
                role="user",
                content="Hello"
            )),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        type="function",
                        id="1234",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments=MockIn(val=1).model_dump_json()
                        )
                    )
                ]
            )),
            Message(
                message=ChatCompletionToolMessage(
                    role="tool",
                    content="1",
                    tool_call_id="1234"
                ), 
                token_count=get_token_count(ChatCompletionToolMessage(
                    role="tool",
                    content="1",
                    tool_call_id="1234"
                ))
            )
        ],
        "expected_events": [
            ToolCallEvent(
                call_id="1234",
                name=MockTool.name,
                args=MockIn(val=1)
            ),
            ToolResultEvent(
                call_id="1234",
                name=MockTool.name,
                args=MockIn(val=1),
                result=MockOut(val=1)
            ),
            StopEvent(issuer="agent", reason="Done")
        ]
    },

    # Case 2
    # The agent generates some text and calls a tool with the wrong parameters.
    # We expect that:
    # * the conversation contains Assistant and Tool messages (the tool message
    #   contains an error in content so the agent can retry).
    # * the client gets TextEvent -> AgentErrorEvent -> StopEvent.
    {
        "conversation_id": "case_2",
        "user_message": "Hello",
        "events": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content="I'm a silly boi",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        type="function",
                        id="1234",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments="{}"
                        )
                    )
                ]
            )),
            ToolErrorEvent(
                failure=ToolErrorFailure.VALIDATION_ERROR,
                tool_call_id="1234",
                name=MockTool.name,
                error="Tool call with wrong arguments"
            ),
            StopEvent(issuer="agent")
        ],
        "persisted_messages": [
            Message(message=ChatCompletionUserMessage(
                role="user",
                content="Hello"
            )),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content="I'm a silly boi",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        type="function",
                        id="1234",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments="{}"
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                role="tool",
                content="Tool call with wrong arguments",
                tool_call_id="1234"
            ))
        ],
        "expected_events": [
            TextEvent(chunk="I'm a silly boi"),
            ToolErrorEvent(
                failure=ToolErrorFailure.VALIDATION_ERROR,
                tool_call_id="1234",
                name=MockTool.name,
                error="Tool call with wrong arguments"
            ),
            StopEvent(issuer="agent")
        ]
    },

    # Case 3
    # The agent calls a tool with correct parameter but execution fails.
    # We expect that:
    # * the conversation contains Assistant and Tool messages (the tool message
    #   contains an error in content so the agent can retry).
    # * the client gets TextEvent -> ToolCallEvent -> AgentErrorEvent -> StopEvent.
    {
        "conversation_id": "case_3",
        "user_message": "Hello",
        "events": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        type="function",
                        id="1234",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments=MockIn(val=1).model_dump_json()
                        )
                    )
                ]
            )),
            ToolCallEvent(
                call_id="1234",
                name=MockTool.name,
                args=MockIn(val=1)
            ),
            ToolErrorEvent(
                failure=ToolErrorFailure.EXECUTION_ERROR,
                tool_call_id="1234",
                name=MockTool.name,
                error="Execution failed"
            ),
            StopEvent(issuer="agent")
        ],
        "persisted_messages": [
            Message(message=ChatCompletionUserMessage(
                role="user",
                content="Hello"
            )),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        type="function",
                        id="1234",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments=MockIn(val=1).model_dump_json()
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                role="tool",
                content="Execution failed",
                tool_call_id="1234"
            ))
        ],
        "expected_events": [
            ToolCallEvent(
                call_id="1234",
                name=MockTool.name,
                args=MockIn(val=1)
            ),
            ToolErrorEvent(
                failure=ToolErrorFailure.EXECUTION_ERROR,
                tool_call_id="1234",
                name=MockTool.name,
                error="Execution failed"
            ),
            StopEvent(issuer="agent")
        ]
    },

    # Case 4
    # The model generates reasoning and then normal text, than the agent stops.
    # We expect that:
    # * the conversation contains Assistant message.
    # * the client gets ReasoningEvent -> TextEvent -> StopEvent.
    {
        "conversation_id": "case_4",
        "user_message": "Hello",
        "events": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content="yes 2+2=5",
                reasoning_content="let me think about it"
            )),
            StopEvent(issuer="agent")
        ],
        "persisted_messages": [
            Message(message=ChatCompletionUserMessage(
                role="user",
                content="Hello"
            )),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content="yes 2+2=5",
                reasoning_content="let me think about it"
            )),
        ],
        "expected_events": [
            ReasoningEvent(chunk="let me think about it"),
            TextEvent(chunk="yes 2+2=5"),
            StopEvent(issuer="agent")
        ]
    },

    # Case 5
    # The orchestrator raises an exception, the runner fails gracefully by
    # yielding a StopEvent with an error message.
    {
        "conversation_id": "case_5",
        "user_message": "Hello",
        "events": RuntimeError("The model provider cockblocked us again..."),
        "persisted_messages": [
            Message(message=ChatCompletionUserMessage(
                role="user",
                content="Hello"
            )),
        ],
        "expected_events": [
            StopEvent(
                issuer="agent",
                error="The model provider cockblocked us again..."
            )
        ]
    }
]


@pytest.mark.parametrize("test_case", _RUNNER_RUN_TEST_CASES)
def test_agent_runner_run(test_case, monkeypatch, register_mock_tool):
    monkeypatch.setattr(
        target=ai_ops.core.runner,
        name="orchestrator",
        value=functools.partial(mock_orchestrator, mock_events=test_case["events"])
    )

    # note: here for simplicity we are using the ConversationStore instead of mocking
    # it, this test will likely change in the future, when the store will implement 
    # persistence.
    conversation_store = get_conversation_store()
    conv = conversation_store.create()

    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool])
    )

    expected_events = test_case["expected_events"]
    event_stream = agent.run(
        user_message=UserMessageEvent(content=test_case["user_message"])
    )
    for idx, event in enumerate(event_stream):
        assert event == expected_events[idx]

    expected_messages = test_case["persisted_messages"]
    conv = conversation_store.get_by_uuid(conv.uuid)

    for expected, persisted in zip(expected_messages, conv.messages[1:]):
        assert persisted == expected


# --- confirmation wiring (arun)
# A stand-in aorchestrator that actually exercises the injected `confirm`
# callback: it yields a confirmation request, awaits the decision, then reports
# either the executed result or the not-admitted result.
async def _confirming_aorchestrator(*, tools, confirm, **kwargs):
    call = ToolCallEvent(
        call_id="c1", name=MockConfirmTool.name,
        args=MockIn(val=5), requires_confirmation=True
    )
    yield call

    approved = await confirm(call)
    tool = tools[MockConfirmTool.name]
    result = tool(MockIn(val=5)) if approved else tool.not_admitted_result(MockIn(val=5))

    yield ToolResultEvent(
        call_id="c1", name=MockConfirmTool.name, args=MockIn(val=5), result=result
    )
    yield StopEvent(issuer="agent")


async def test_agent_runner_arun_confirm_approved(monkeypatch, register_mock_confirm_tool):
    monkeypatch.setattr(
        target=ai_ops.core.runner, name="aorchestrator", value=_confirming_aorchestrator
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockConfirmTool])
    )

    results = []
    async for event in agent.arun(user_message=UserMessageEvent(content="Hello"), mode=AgentMode.SUPERVISED):
        if isinstance(event, ToolCallEvent) and event.requires_confirmation:
            # reply inline: the future is resolved before arun asks aorchestrator
            # for the next event, so the awaited `confirm` returns immediately.
            agent.confirm(ToolConfirmationEvent(call_id=event.call_id, approved=True))
        if isinstance(event, ToolResultEvent):
            results.append(event.result)

    assert results == [MockOut(val=5)]


async def test_agent_runner_arun_confirm_denied(monkeypatch, register_mock_confirm_tool):
    monkeypatch.setattr(
        target=ai_ops.core.runner, name="aorchestrator", value=_confirming_aorchestrator
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockConfirmTool])
    )

    results = []
    async for event in agent.arun(user_message=UserMessageEvent(content="Hello"), mode=AgentMode.SUPERVISED):
        if isinstance(event, ToolCallEvent) and event.requires_confirmation:
            agent.confirm(ToolConfirmationEvent(call_id=event.call_id, approved=False))
        if isinstance(event, ToolResultEvent):
            results.append(event.result)

    assert results == [MockOut(val=NOT_ADMITTED_VAL)]


async def test_agent_runner_arun_confirm_timeout(monkeypatch, register_mock_confirm_tool):
    # never call agent.confirm -> the confirm callback times out and the call is
    # treated as denied (not executed).
    monkeypatch.setattr(
        target=ai_ops.core.runner, name="aorchestrator", value=_confirming_aorchestrator
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockConfirmTool], confirmation_timeout_s=0.05)
    )

    results = []
    async for event in agent.arun(user_message=UserMessageEvent(content="Hello"), mode=AgentMode.SUPERVISED):
        if isinstance(event, ToolResultEvent):
            results.append(event.result)

    assert results == [MockOut(val=NOT_ADMITTED_VAL)]


@pytest.mark.parametrize("test_case", _RUNNER_RUN_TEST_CASES)
async def test_agent_runner_arun(test_case, monkeypatch, register_mock_tool):
    monkeypatch.setattr(
        target=ai_ops.core.runner,
        name="aorchestrator",
        value=functools.partial(mock_aorchestrator, mock_events=test_case["events"])
    )

    conversation_store = get_conversation_store()
    conv = conversation_store.create()

    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool])
    )

    expected_events = test_case["expected_events"]
    event_stream = agent.arun(
        user_message=UserMessageEvent(content=test_case["user_message"])
    )
    idx = 0
    async for event in event_stream:
        assert event == expected_events[idx]
        idx += 1

    expected_messages = test_case["persisted_messages"]
    conv = conversation_store.get_by_uuid(conv.uuid)

    for expected, persisted in zip(expected_messages, conv.messages[1:]):
        assert persisted == expected
