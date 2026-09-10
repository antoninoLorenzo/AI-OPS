import pytest
from litellm import (
    ChatCompletionAssistantMessage,
    ChatCompletionAssistantToolCall,
    ChatCompletionToolCallFunctionChunk,
    ChatCompletionToolMessage,
    ChatCompletionUserMessage,
)

from ai_ops.core.conversation import (
    is_tool_call,
    find_tool_call_result,
    is_valid_context,
    Message
)
from test.core.mocks.tool import MockTool
from test.core.utils import _system_message, _user_message, _tool_message


_IS_VALID_CONTEXT_TESTS = [
    {
        "name": "ValidMessageList",
        "messages": [
            _system_message("sys"),
            _user_message("usr"),
            Message(agent_id="react", message={
                "role": "assistant",
                "content": "Hi",
                "tool_calls": [
                    {
                        "id": "tc0",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    },
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    }
                ]
            }),
            # out-of-order allowed
            _tool_message("tc1"),
            _tool_message("tc0")
        ],
        "expected": (True, None)
    },
    {
        "name": "ToolCallsWithNoResults",
        "messages": [
            _system_message("Hi"),
            _user_message("Hi"),
            Message(agent_id="react", message={
                "role": "assistant",
                "content": "Hi",
                "tool_calls": [
                    {
                        "id": "0",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    },
                    {
                        "id": "2",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    }
                ]
            })
        ],
        "expected": (False, "")
    },
    {
        "name": "ToolCallsNotMatchingIds",
        "messages": [
            _system_message("Hi"),
            _user_message("Hi"),
            Message(agent_id="react", message={
                "role": "assistant",
                "content": "Hi",
                "tool_calls": [
                    {
                        "id": "tc0",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    },
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    }
                ]
            }),
            _tool_message("tc2"),
            _tool_message("tc0")
        ],
        "expected": (False, "")
    },
    {
        "name": "MessageBetweenToolResults",
        "messages": [
            _system_message("sys"),
            _user_message("usr"),
            Message(agent_id="role", message={
                "role": "assistant",
                "content": "Hi",
                "tool_calls": [
                    {
                        "id": "tc0",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    },
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    }
                ]
            }),
            _tool_message("tc1"),
            _user_message("usr got there"),
            _tool_message("tc0")
        ],
        "expected": (False, "")
    },
    {
        "name": "MissingToolResult",
        "messages": [
            _system_message("sys"),
            _user_message("usr"),
            Message(agent_id="react", message={
                "role": "assistant",
                "content": "Hi",
                "tool_calls": [
                    {
                        "id": "tc0",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    },
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    }
                ]
            }),
            _tool_message("tc1")
        ],
        "expected": (False, "")
    },
    {
        "name": "DanglingToolResultsAtStart",
        "messages": [
            _system_message("sys"),
            _user_message("usr"),
            _tool_message("tc0"),
            _tool_message("tc1"),
            Message(agent_id="react", message={
                "role": "assistant",
                "content": "Hi",
                "tool_calls": [
                    {
                        "id": "tc2",
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    }
                ]
            }),
            _tool_message("tc2")
        ],
        "expected": (False, "")
    }
]

@pytest.mark.parametrize("test_case", _IS_VALID_CONTEXT_TESTS, ids=lambda tc: tc["name"])
def test_is_valid_context(test_case):
    valid, err = is_valid_context(test_case["messages"])
    assert valid == test_case["expected"][0]

_IS_TOOL_CALL_TESTS = [
    # not assistant message
    {
        "name": "NotAssistantMessage",
        "message": Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content="hello")),
        "tool_name_key": MockTool.name,
        "expected": (False, None),
    },
    # assistant message with no tool_calls
    {
        "name": "NoToolCalls",
        "message": Message(agent_id="react", 
            message=ChatCompletionAssistantMessage(
                role="assistant",
                content="no tools here",
            )
        ),
        "tool_name_key": MockTool.name,
        "expected": (False, None),
    },
    # assistant message with tool_calls but wrong tool name
    {
        "name": "NotToolExpected",
        "message": Message(agent_id="react", 
            message=ChatCompletionAssistantMessage(
                role="assistant",
                content="calling something else",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="call_1",
                        type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name="other_tool",
                            arguments='{"val": 1}',
                        ),
                    )
                ],
            )
        ),
        "tool_name_key": MockTool.name,
        "expected": (False, None),
    },
    # assistant message with tool_calls but missing function name
    {
        "name": "ToolCallMalformedMissingFunctionName",
        "message": Message(agent_id="react", 
            message=ChatCompletionAssistantMessage(
                role="assistant",
                content="bad call",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="call_2",
                        type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=None,
                            arguments='{"val": 1}',
                        ),
                    )
                ],
            )
        ),
        "tool_name_key": MockTool.name,
        "expected": (False, None),
    },
    # assistant message with matching tool call
    {
        "name": "HappyToolCall",
        "message": Message(agent_id="react", 
            message=ChatCompletionAssistantMessage(
                role="assistant",
                content="calling mock tool",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="call_123",
                        type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments='{"val": 1}',
                        ),
                    )
                ],
            )
        ),
        "tool_name_key": MockTool.name,
        "expected": (True, ["call_123"]),
    },
    # assistant message with matching tool call but missing id
    {
        "name": "ToolCallMalformedMissingId",
        "message": Message(agent_id="react", 
            message=ChatCompletionAssistantMessage(
                role="assistant",
                content="calling mock tool",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id=None,
                        type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments='{"val": 1}',
                        ),
                    )
                ],
            )
        ),
        "tool_name_key": MockTool.name,
        "expected": (False, None),
    },
    # edge case: multiple tool calls of same type in same message
    {
        "name": "MultipleToolCalls",
        "message": Message(agent_id="react", 
            message=ChatCompletionAssistantMessage(
                role="assistant",
                content="calling mock tool",
                tool_calls=[
                    ChatCompletionAssistantToolCall(
                        id="123",
                        type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments='{"val": 1}',
                        ),
                    ),
                    ChatCompletionAssistantToolCall(
                        id="456",
                        type="function",
                        function=ChatCompletionToolCallFunctionChunk(
                            name=MockTool.name,
                            arguments='{"val": 1}',
                        ),
                    )
                ],
            )
        ),
        "tool_name_key": MockTool.name,
        "expected": (True, ["123", "456"]),
    }
]


@pytest.mark.parametrize("test_case", _IS_TOOL_CALL_TESTS, ids=lambda tc: tc["name"])
def test_is_tool_call(test_case):
    assert is_tool_call(test_case["message"], test_case["tool_name_key"]) == test_case["expected"]


_FIND_TOOL_CALL_RESULT_TESTS = [
    {
        "name": "no tool message in the list",
        "messages": [
            Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content="hello")),
            Message(agent_id="react", 
                message=ChatCompletionAssistantMessage(
                    role="assistant",
                    content="still no tool",
                )
            ),
        ],
        "tool_call_id": "call_1",
        "expected": None,
    },
    {
        "name": "matching tool message found",
        "messages": [
            Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content="hello")),
            Message(agent_id="react", 
                message=ChatCompletionAssistantMessage(
                    role="assistant",
                    content="calling tool",
                    tool_calls=[
                        ChatCompletionAssistantToolCall(
                            id="call_1",
                            type="function",
                            function=ChatCompletionToolCallFunctionChunk(
                                name=MockTool.name,
                                arguments='{"val": 1}',
                            ),
                        )
                    ],
                )
            ),
            Message(agent_id="react", 
                message=ChatCompletionToolMessage(
                    role="tool",
                    tool_call_id="call_1",
                    content="result",
                )
            ),
        ],
        "tool_call_id": "call_1",
        "expected": 2,
    },
    {
        "name": "returns the last matching tool message when there are multiple tool messages",
        "messages": [
            Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content="hello")),
            Message(agent_id="react", 
                message=ChatCompletionAssistantMessage(
                    role="assistant",
                    content="call one",
                )
            ),
            Message(agent_id="react", 
                message=ChatCompletionToolMessage(
                    role="tool",
                    tool_call_id="call_1",
                    content="first result",
                )
            ),
            Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content="more text")),
            Message(agent_id="react", 
                message=ChatCompletionToolMessage(
                    role="tool",
                    tool_call_id="call_1",
                    content="second result",
                )
            ),
        ],
        "tool_call_id": "call_1",
        "expected": 4,
    },
]


@pytest.mark.parametrize("test_case", _FIND_TOOL_CALL_RESULT_TESTS, ids=lambda tc: tc["name"])
def test_find_tool_call_result(test_case):
    assert find_tool_call_result(test_case["messages"], test_case["tool_call_id"]) == test_case["expected"]
