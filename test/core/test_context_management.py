import pytest
import requests
from litellm import (
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage, 
    ChatCompletionAssistantMessage,
    ChatCompletionAssistantToolCall,
    ChatCompletionToolCallFunctionChunk,
    ChatCompletionToolMessage
)

from ai_ops.core.context_management import RawContextView, LayeredContextView
from ai_ops.core.conversation import Message
from ai_ops.core.tools.whiteboard import (
    WhiteboardEntry,
    WhiteboardWriteRequest,
    WhiteboardResult,
    WhiteboardRead, 
    WhiteboardWrite
)
from ai_ops.core.tools.think import ThinkTool
from ai_ops.core.tools.terminal.terminal import Terminal
from ai_ops.core.conversation import get_token_count


def test_raw_context_view_deep_copy():
    context_fn = RawContextView()

    messages = [
        Message(message={"role": "system", "content": "U're a good boy"}),
        Message(message={"role": "user", "content": "Wyd u up?"})
    ]

    context = context_fn(messages)
    context[1].message["content"] += "Ephemeral info"

    assert "Ephemeral info" not in messages[1].message["content"]


# --- LayeredContextView

_SEARCH_CHECKPOINT_TESTS = [
    {
        "name": "NoWhiteboardWrite",
        "messages": [
            Message(message=ChatCompletionUserMessage(role="user", content="Hi")),
            Message(message=ChatCompletionAssistantMessage(role="assistant", content="wassup"))
        ],
        "expected": None
    },
    {
        "name": "WhiteboardWriteNoResult",
        "messages": [
            Message(message=ChatCompletionUserMessage(role="user", content="Hi")),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant", 
                content="wassup",
                tool_calls=[ChatCompletionAssistantToolCall(
                    id="123", type="function", 
                    function=ChatCompletionToolCallFunctionChunk(
                        name=WhiteboardWrite.name,
                        arguments="asd" # here tool call validation is not happening (right?)
                    )
                )] 
            ))
        ],
        "expected": None
    },
    {
        "name": "WhiteboardWriteLastMessage",
        "messages": [
            Message(message=ChatCompletionUserMessage(role="user", content="Hi")),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant", 
                content="wassup",
                tool_calls=[ChatCompletionAssistantToolCall(
                    id="123", type="function", 
                    function=ChatCompletionToolCallFunctionChunk(
                        name=WhiteboardWrite.name,
                        arguments="asd" # here tool call validation is not happening (right?)
                    )
                )] 
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="123", role="tool",
                content="this is always str"
            ))
        ],
        "expected": 2
    },
    {
        "name": "WhiteboardWriteWithMoreMessages",
        "messages": [
            Message(message=ChatCompletionUserMessage(role="user", content="Hi")),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant", 
                content="wassup",
                tool_calls=[ChatCompletionAssistantToolCall(
                    id="123", type="function", 
                    function=ChatCompletionToolCallFunctionChunk(
                        name=WhiteboardWrite.name,
                        arguments="asd"
                    )
                )] 
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="123", role="tool",
                content="this is always str"
            )),
            Message(message=ChatCompletionAssistantMessage(role="assistant", content="what's next?"))
        ],
        "expected": 2
    }
]

@pytest.mark.parametrize("test_case", _SEARCH_CHECKPOINT_TESTS, ids=lambda tc: tc["name"])
def test_search_checkpoint(test_case):
    context_fn = LayeredContextView(max_window_tokens=1024)
    assert context_fn.search_checkpoint(messages=test_case["messages"]) == test_case["expected"]


def fetch_content(url: str) -> str:
    response = requests.get(url=url)
    response.raise_for_status()
    return response.text


def _make_terminal_truncation_test(url: str) -> dict:
    long_output = fetch_content(url)
    tool_msg = ChatCompletionToolMessage(
        tool_call_id="123", role="tool", content=long_output
    )
    token_count = get_token_count(tool_msg)
    assert token_count is not None, "get_token_count(tool_msg) returned None"

    # same calculation in apply_active_window
    max_window_tokens = 1024
    truncation_threshold = 0.5
    max_tool_tokens = int(max_window_tokens * truncation_threshold)

    truncation_char_count = (token_count - max_tool_tokens) * 4
    truncated_content = "[truncated...]" + long_output[truncation_char_count:]

    truncated_tool_msg = ChatCompletionToolMessage(
        tool_call_id="123", role="tool", content=truncated_content
    )
    truncated_token_count = get_token_count(truncated_tool_msg)
    assert truncated_token_count is not None, "get_token_count(truncated_tool_msg) returned None"

    terminal_call = ChatCompletionAssistantToolCall(
        id="123", type="function",
        function=ChatCompletionToolCallFunctionChunk(
            name=Terminal.name, arguments="{}"
        )
    )

    return {
        "name": "TerminalOutputTruncated",
        "context_view_params": {
            "max_window_tokens": max_window_tokens, 
            "truncation_threshold": truncation_threshold
        },
        "messages": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant", content=None, tool_calls=[terminal_call]
            )),
            Message(message=tool_msg, token_count=token_count),
        ],
        "expected": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant", content=None, tool_calls=[terminal_call]
            )),
            Message(
                message=truncated_tool_msg,
                token_count=truncated_token_count
            ),
        ],
    }


def _make_two_terminal_truncation_test(url: str) -> dict:
    long_output = fetch_content(url)

    tool_msg_1 = ChatCompletionToolMessage(tool_call_id="111", role="tool", content=long_output)
    tool_msg_2 = ChatCompletionToolMessage(tool_call_id="222", role="tool", content=long_output)
    token_count = get_token_count(tool_msg_1)
    assert token_count is not None

    max_window_tokens = 1024
    truncation_threshold = 0.5
    max_tool_tokens = int(max_window_tokens * truncation_threshold)

    truncation_char_count = (token_count - max_tool_tokens) * 4
    truncated_content = "[truncated...]" + long_output[truncation_char_count:]

    truncated_msg_1 = ChatCompletionToolMessage(tool_call_id="111", role="tool", content=truncated_content)
    truncated_msg_2 = ChatCompletionToolMessage(tool_call_id="222", role="tool", content=truncated_content)
    truncated_token_count = get_token_count(truncated_msg_1)
    assert truncated_token_count is not None

    terminal_calls = ChatCompletionAssistantMessage(
        role="assistant",
        content=None,
        tool_calls=[
            ChatCompletionAssistantToolCall(
                id="111", type="function",
                function=ChatCompletionToolCallFunctionChunk(name=Terminal.name, arguments="{}")
            ),
            ChatCompletionAssistantToolCall(
                id="222", type="function",
                function=ChatCompletionToolCallFunctionChunk(name=Terminal.name, arguments="{}")
            ),
        ]
    )

    return {
        "name": "TwoTerminalCallsTruncated",
        "context_view_params": {
            "max_window_tokens": max_window_tokens,
            "truncation_threshold": truncation_threshold,
        },
        "messages": [
            Message(message=terminal_calls),
            Message(message=tool_msg_1, token_count=token_count),
            Message(message=tool_msg_2, token_count=token_count),
        ],
        "expected": [
            Message(message=terminal_calls),
            Message(message=truncated_msg_1, token_count=truncated_token_count),
            Message(message=truncated_msg_2, token_count=truncated_token_count),
        ],
    }



_APPLY_ACTIVE_WINDOW_TESTS = [
    # Think calls out of the max_think window are dropped
    {
        "name": "DropThink",
        "context_view_params": { "max_window_tokens": 1024,  "max_think": 1 },
        "messages": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant", 
                content="wassup",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="123", type="function", 
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name,
                            arguments="asd"
                        )
                    ),
                    ChatCompletionAssistantToolCall(
                        id="456", type="function", 
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name,
                            arguments="asd"
                        )
                    ),
                ] 
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="123", role="tool",
                content="this is always str"
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="456", role="tool",
                content="this is always str"
            )),
        ],
        "expected": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant", 
                content="wassup",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="456", type="function", 
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name,
                            arguments="asd"
                        )
                    ),
                ] 
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="456", role="tool",
                content="this is always str"
            )),
        ]
    },
    # Think calls in separate messages, oldest message has tool_calls emptied,
    # its result is dropped. Newest think is within window and untouched.
    {
        "name": "DropThinkAcrossMessages",
        "context_view_params": {"max_window_tokens": 1024, "max_think": 1},
        "messages": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="aaa", type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name, arguments="asd"
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="aaa", role="tool",
                content="old think result"
            )),
            # newer think within window, kept
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="bbb", type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name, arguments="asd"
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="bbb", role="tool",
                content="new think result"
            )),
        ],
        "expected": [
            # result for "aaa" is dropped (not in output)
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="bbb", type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name, arguments="asd"
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="bbb", role="tool",
                content="new think result"
            )),
        ]
    },
    #  All think calls within window -> nothing should be dropped or modified
    {
        "name": "NoDropWithinWindow",
        "context_view_params": {"max_window_tokens": 1024, "max_think": 3},
        "messages": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="111", type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name, arguments="asd"
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="111", role="tool",
                content="think result"
            )),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="222", type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name, arguments="asd"
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="222", role="tool",
                content="think result"
            )),
        ],
        "expected": [
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="111", type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name, arguments="asd"
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="111", role="tool",
                content="think result"
            )),
            Message(message=ChatCompletionAssistantMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="222", type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=ThinkTool.name, arguments="asd"
                        )
                    )
                ]
            )),
            Message(message=ChatCompletionToolMessage(
                tool_call_id="222", role="tool",
                content="think result"
            )),
        ]
    },
    # Terminal output gets truncated after threshold
    _make_terminal_truncation_test("https://raw.githubusercontent.com/danielmiessler/SecLists/refs/heads/master/Passwords/Common-Credentials/10k-most-common.txt"),
    _make_two_terminal_truncation_test("https://raw.githubusercontent.com/danielmiessler/SecLists/refs/heads/master/Passwords/Common-Credentials/10k-most-common.txt")
]


@pytest.mark.parametrize("test_case", _APPLY_ACTIVE_WINDOW_TESTS, ids=lambda tc: tc["name"])
def test_apply_active_window(test_case):
    context_fn = LayeredContextView(**test_case["context_view_params"])
    actual = context_fn.apply_active_window(test_case["messages"])
    expected = test_case["expected"]

    assert len(actual) == len(expected), f"length mismatch: {len(actual)} vs {len(expected)}"
    for i, (a, e) in enumerate(zip(actual, expected)):
        ac = a.message.get("content") or ""
        ec = e.message.get("content") or ""
        assert a.internal == e.internal, f"[{i}] internal: {a.internal} vs {e.internal}"
        assert a.message.get("role") == e.message.get("role"), f"[{i}] role mismatch"
        assert a.message.get("tool_call_id") == e.message.get("tool_call_id"), f"[{i}] tool_call_id mismatch"
        assert len(ac) == len(ec), f"[{i}] content length: actual={len(ac)} vs expected={len(ec)}"
        assert ac[:80] == ec[:80], f"[{i}] content start:\n  actual:   {ac[:80]!r}\n  expected: {ec[:80]!r}"
        assert ac[-80:] == ec[-80:], f"[{i}] content end:\n  actual:   {ac[-80:]!r}\n  expected: {ec[-80:]!r}"
        assert a.token_count == e.token_count, f"[{i}] token_count: {a.token_count} vs {e.token_count}"
