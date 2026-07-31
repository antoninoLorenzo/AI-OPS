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
# (user sends message during agent loop is covered by the send/drain tests below)
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
            Message(
                message=ChatCompletionToolMessage(
                    role="tool",
                    content="mock_tool validation_error: Tool call with wrong arguments",
                    tool_call_id="1234"
                ),
                token_count=get_token_count(ChatCompletionToolMessage(
                    role="tool",
                    content="mock_tool validation_error: Tool call with wrong arguments",
                    tool_call_id="1234"
                ))
            )
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
            Message(
                message=ChatCompletionToolMessage(
                    role="tool",
                    content="mock_tool execution_error: Execution failed",
                    tool_call_id="1234"
                ),
                token_count=get_token_count(ChatCompletionToolMessage(
                    role="tool",
                    content="mock_tool execution_error: Execution failed",
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


@pytest.mark.parametrize("test_case", _RUNNER_RUN_TEST_CASES)
async def test_agent_runner_arun_persists_events(test_case, monkeypatch, register_mock_tool):
    # every event the client receives is also written to the event store, and the
    # user turn is persisted ahead of them (via `_append_user_message`).
    monkeypatch.setattr(
        target=ai_ops.core.runner,
        name="aorchestrator",
        value=functools.partial(mock_aorchestrator, mock_events=test_case["events"])
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool])
    )

    async for _ in agent.arun(user_message=UserMessageEvent(content=test_case["user_message"])):
        pass

    expected_events = [UserMessageEvent(content=test_case["user_message"])] + test_case["expected_events"]
    persisted_events = agent._event_store.get_by_conversation_uuid(conv.uuid)
    assert persisted_events == expected_events


# --- send / drain (arun) -----------------------------------------------------
# `send` enqueues a user message mid-run; the runner drains it only once there
# are no pending tool calls (an assistant tool-call message must be immediately
# followed by its tool result). If the drain happens after a StopEvent, the
# orchestrator loop restarts to process the new turn.


async def test_agent_runner_send_drains_after_stop_and_restarts(monkeypatch, register_mock_tool):
    call_state = {"calls": 0}

    async def _orch(state, **kwargs):
        state["calls"] += 1
        yield StopEvent(issuer="agent")

    monkeypatch.setattr(
        target=ai_ops.core.runner,
        name="aorchestrator",
        value=functools.partial(_orch, call_state),
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool]),
    )

    sent = False
    async for event in agent.arun(user_message=UserMessageEvent(content="start")):
        if isinstance(event, StopEvent) and not sent:
            # queue a follow-up: it drains after this stop and restarts the loop.
            assert agent.send(UserMessageEvent(content="follow up")) is True
            sent = True

    # the orchestrator ran twice: once for the initial turn, once for the drained
    # follow-up message.
    assert call_state["calls"] == 2

    conv = get_conversation_store().get_by_uuid(conv.uuid)
    user_contents = [m.message.get("content") for m in conv.messages if m.message.get("role") == "user"]
    assert user_contents == ["start", "follow up"]

    persisted = agent._event_store.get_by_conversation_uuid(conv.uuid)
    assert any(isinstance(e, UserMessageEvent) and e.content == "follow up" for e in persisted)


async def test_agent_runner_send_preserves_ordering_under_pending_tool_calls(
    monkeypatch, register_mock_tool
):
    # a queued message must not slip between an assistant tool-call and its tool
    # result: the drain waits until pending tool calls reach zero.
    call_state = {"calls": 0}

    async def _orch(state, **kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            yield Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content="working",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        type="function",
                        id="1",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments=MockIn(val=1).model_dump_json(),
                        ),
                    )
                ],
            ))
            yield ToolResultEvent(
                call_id="1", name=MockTool.name, args=MockIn(val=1), result=MockOut(val=1)
            )
            yield StopEvent(issuer="agent")
        else:
            yield StopEvent(issuer="agent")

    monkeypatch.setattr(
        target=ai_ops.core.runner,
        name="aorchestrator",
        value=functools.partial(_orch, call_state),
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool]),
    )

    sent = False
    async for event in agent.arun(user_message=UserMessageEvent(content="start")):
        # send while a tool call is still pending (right after the assistant text)
        if isinstance(event, TextEvent) and not sent:
            assert agent.send(UserMessageEvent(content="mid")) is True
            sent = True

    conv = get_conversation_store().get_by_uuid(conv.uuid)
    roles = [m.message["role"] for m in conv.messages]
    # system, user(start), assistant(tool call), tool(result), user(mid)
    assert roles == ["system", "user", "assistant", "tool", "user"]
    assert conv.messages[-1].message["content"] == "mid"


async def test_agent_runner_send_then_stop_drops_pending_message(monkeypatch, register_mock_tool):
    # user sends then immediately stops: the stop wins, the enqueued message is
    # discarded, and a user-issued StopEvent is persisted.
    async def _orch(**kwargs):
        yield Message(message=ChatCompletionAssistantMessage(role="assistant", content="a"))
        yield StopEvent(issuer="agent")

    monkeypatch.setattr(target=ai_ops.core.runner, name="aorchestrator", value=_orch)

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool]),
    )

    async for event in agent.arun(user_message=UserMessageEvent(content="start")):
        if isinstance(event, TextEvent):
            assert agent.send(UserMessageEvent(content="ghost")) is True
            agent.stop()

    assert agent._pending_message is None

    conv = get_conversation_store().get_by_uuid(conv.uuid)
    user_contents = [m.message.get("content") for m in conv.messages if m.message.get("role") == "user"]
    assert "ghost" not in user_contents

    persisted = agent._event_store.get_by_conversation_uuid(conv.uuid)
    # the user-stop persists a StopEvent(issuer="user")...
    assert any(isinstance(e, StopEvent) and e.issuer == "user" for e in persisted)
    # ...and the discarded message never reaches the event store.
    assert not any(isinstance(e, UserMessageEvent) and e.content == "ghost" for e in persisted)


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
    # tightened contract: confirmation state is released once the call resolves,
    # so nothing lingers to leak futures or blocked-call entries.
    assert agent._confirmations == {}
    assert agent._blocked_calls == []


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
    # tightened contract: a denied call cleans up just like an approved one.
    assert agent._confirmations == {}
    assert agent._blocked_calls == []


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
    # tightened contract: a timed-out confirmation also releases its resources
    # (the `finally` in `_confirm` runs even on `TimeoutError`).
    assert agent._confirmations == {}
    assert agent._blocked_calls == []


# --- tightened contracts -----------------------------------------------------
# The following tests exercise the guards added to `AgentRunner`:
#   * `arun` may only drive one orchestrator at a time (`_running`).
#   * `send` cannot be spammed while a message is still pending.
#   * `confirm` refuses call ids that were never blocked, so it never allocates
#     a confirmation future that nothing will ever resolve.


async def test_agent_runner_arun_rejects_concurrent_call(monkeypatch, register_mock_tool):
    # A runner is tied to one conversation and runs a single orchestrator at a
    # time: while a run is in flight, a second `arun` must raise.
    monkeypatch.setattr(
        target=ai_ops.core.runner,
        name="aorchestrator",
        value=functools.partial(
            mock_aorchestrator, mock_events=[StopEvent(issuer="agent")]
        )
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool])
    )

    # first call sets `_running` (synchronously, before iteration begins)
    event_stream = agent.arun(user_message=UserMessageEvent(content="Hello"))
    assert agent.running is True

    with pytest.raises(RuntimeError):
        agent.arun(user_message=UserMessageEvent(content="Again"))

    # draining the first run releases the guard so the runner can be reused
    async for _ in event_stream:
        pass
    assert agent.running is False


def test_agent_runner_send_rejected_when_not_running(register_mock_tool):
    # `send` only enqueues while a run is active; otherwise there is nothing to
    # deliver the message to.
    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool])
    )

    assert agent.send(UserMessageEvent(content="nobody home")) is False

# TODO: this tests below could be parametrized AND should test `send` doesn't break ordering.
async def test_agent_runner_send_not_spammable(monkeypatch, register_mock_tool):
    # Only one message may be pending at a time: the first `send` is accepted and
    # locks out further sends until the runner processes an event.
    send_events = [
        Message(message=ChatCompletionAssistantMessage(role="assistant", content="a")),
        Message(message=ChatCompletionAssistantMessage(role="assistant", content="b")),
        StopEvent(issuer="agent"),
    ]
    monkeypatch.setattr(
        target=ai_ops.core.runner,
        name="aorchestrator",
        value=functools.partial(mock_aorchestrator, mock_events=send_events)
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockTool])
    )

    event_stream = agent.arun(user_message=UserMessageEvent(content="Hello"))

    assert agent.send(UserMessageEvent(content="first")) is True   # accepted, locks
    assert agent.send(UserMessageEvent(content="spam")) is False   # rejected
    assert agent.send(UserMessageEvent(content="spam")) is False   # still rejected

    # once the runner processes an event the lock is released and `send` is
    # accepted again (at most once more, then re-locked).
    accepted_again = False
    async for _ in event_stream:
        if agent.send(UserMessageEvent(content="later")):
            accepted_again = True
            break
    assert accepted_again is True

    # draining the run leaves the runner idle, so `send` is refused again
    async for _ in event_stream:
        pass
    assert agent.send(UserMessageEvent(content="done")) is False


def test_agent_runner_confirm_unknown_call_id_raises(register_mock_confirm_tool):
    # Confirming a call that was never blocked must raise and, crucially, must
    # not allocate a confirmation future that would never be resolved.
    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockConfirmTool])
    )

    with pytest.raises(RuntimeError):
        agent.confirm(ToolConfirmationEvent(call_id="never-blocked", approved=True))

    assert agent._confirmations == {}
    assert agent._blocked_calls == []


async def test_agent_runner_confirm_stale_call_raises(monkeypatch, register_mock_confirm_tool):
    # After a blocked call has been resolved it is removed from the blocked set,
    # so a late/duplicate `confirm` for the same id raises instead of resurrecting
    # a resolved call.
    monkeypatch.setattr(
        target=ai_ops.core.runner, name="aorchestrator", value=_confirming_aorchestrator
    )

    conv = get_conversation_store().create()
    agent = AgentRunner(
        conversation_id=conv.uuid,
        client=mock_inference_client,
        config=AgentConfig(tools=[MockConfirmTool])
    )

    call_id = None
    async for event in agent.arun(
        user_message=UserMessageEvent(content="Hello"), mode=AgentMode.SUPERVISED
    ):
        if isinstance(event, ToolCallEvent) and event.requires_confirmation:
            call_id = event.call_id
            agent.confirm(ToolConfirmationEvent(call_id=call_id, approved=True))
        if isinstance(event, ToolResultEvent):
            # the call has already resolved and been cleaned up
            with pytest.raises(RuntimeError):
                agent.confirm(ToolConfirmationEvent(call_id=call_id, approved=True))

    assert call_id is not None
    assert agent._confirmations == {}
    assert agent._blocked_calls == []


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
