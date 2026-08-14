import pytest

from litellm import (
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage, 
    ChatCompletionAssistantMessage,
    ChatCompletionAssistantToolCall,
    ChatCompletionToolCallFunctionChunk,
    ChatCompletionToolMessage
)

from ai_ops.core.context_management import CheckpointCompaction
from ai_ops.core.conversation import Message, is_valid_context
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

from test.core.mocks.tool import (
    MockIn, MockOut,
    MockTool,
    MockSkipCompactionTool,
    MockPreserveStateTool,
    register_mock_tool,
    register_mock_skip_compaction_tool,
    register_mock_carry_state_tool
)
from test.core.utils import _system_message, _user_message, _assistant_message, _tool_call, _tool_message


_whiteboard_write_request = WhiteboardWriteRequest(
    name="test", 
    description="test", 
    content="test"
).model_dump()

_CHECKPOINT_COMPACTION_TESTS = [
    {
        "name": "SkipCompactionBeforeCheckpoint",
        "tools": [MockSkipCompactionTool()],
        "messages": [
            _system_message("sys"),
            _user_message("usr"),
            _assistant_message("ass", tool_calls=[
                _tool_call("tc0", MockSkipCompactionTool.name, MockIn(val=1).model_dump()),
                _tool_call("tc1", MockTool.name, MockIn(val=2).model_dump())
            ]),
            _tool_message("tc0"),
            _tool_message("tc1"),
            _assistant_message("ass", tool_calls=[
                _tool_call("tc_whiteboard", WhiteboardWrite.name, _whiteboard_write_request),
            ]),
            _tool_message("tc_whiteboard"),
        ],
        "expected": [
            _system_message("sys"),
            _user_message("usr"),
            _assistant_message("ass", tool_calls=[
                _tool_call("tc0", MockSkipCompactionTool.name, MockIn(val=1).model_dump()),
            ]),
            _tool_message("tc0"),
            _assistant_message("ass", tool_calls=[
                _tool_call("tc_whiteboard", WhiteboardWrite.name, _whiteboard_write_request),
            ]),
            _tool_message("tc_whiteboard"),
        ],
    },
    {
        "name": "InjectToolState",
        "tools": [MockPreserveStateTool()],
        "messages": [
            _system_message("sys"),
            _user_message("usr"),
            _assistant_message("ass", tool_calls=[
                _tool_call("tc0", MockPreserveStateTool.name, MockIn(val=1).model_dump()),
                _tool_call("tc1", MockTool.name, MockIn(val=2).model_dump_json())
            ]),
            _tool_message("tc0"),
            _tool_message("tc1"),
            _assistant_message("ass", tool_calls=[
                _tool_call("tc_whiteboard", WhiteboardWrite.name, _whiteboard_write_request),
            ]),
            _tool_message("tc_whiteboard"),
        ],
        "expected": [
            _system_message("sys"),
            _user_message("usr"),
            _assistant_message("ass", tool_calls=[
                _tool_call("tc_whiteboard", WhiteboardWrite.name, _whiteboard_write_request),
            ]),
            _tool_message("tc_whiteboard"),
            _user_message(MockPreserveStateTool.expected_state)
        ],
    },
    # {
    #     "name": "",
    #     "tools": [MockPreserveStateTool(), MockSkipCompactionTool()],
    #     "messages": [],
    #     "expected": []
    # }
]

def print_decent(res: list[Message], exp: list[Message]):
    import json

    def fck(messages: list[Message]):
        raw_list = [msg.message for msg in messages]
        return json.dumps(raw_list, indent=4)
    
    print("--- Result \n" + fck(res))
    print("--- Expected \n" + fck(exp))


@pytest.mark.parametrize("test_case", _CHECKPOINT_COMPACTION_TESTS, ids=lambda tc: tc["name"])
def test_checkpoint_compaction(
    test_case, 
    # can I put those fixtures inside a single one?
    register_mock_tool,
    register_mock_carry_state_tool, 
    register_mock_skip_compaction_tool
):
    transform = CheckpointCompaction(tools=test_case["tools"])
    context = transform(test_case["messages"])
    valid, err = is_valid_context(context)
    assert valid == True, err
    assert context == test_case["expected"], print_decent(context, test_case["expected"])
