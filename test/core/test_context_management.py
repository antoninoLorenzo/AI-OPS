import pytest

from litellm import (
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage, 
    ChatCompletionAssistantMessage,
    ChatCompletionAssistantToolCall,
    ChatCompletionToolCallFunctionChunk,
    ChatCompletionToolMessage
)

from ai_ops.core.context_management import CheckpointCompaction, SlidingWindow
from ai_ops.core.conversation import Message, is_valid_context, count_tokens
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


# --- SlidingWindow

# Helpers that build messages with *explicit* token counts. SlidingWindow cuts
# using `message.token_count` and `count_tokens` sums the same field, so setting
# it explicitly makes the drop boundary (and the resulting window size) exactly
# predictable. `Message.token_count` is a mutable field (CheckpointCompaction
# already mutates it), so overriding it after construction is fine.

def _sized(message: Message, tokens: int) -> Message:
    message.token_count = tokens
    return message


def _sys(tokens: int = 5) -> Message:
    return _sized(_system_message("sys"), tokens)


def _usr(text: str = "usr", tokens: int = 5) -> Message:
    return _sized(_user_message(text), tokens)


def _a(tc_id: str, tokens: int) -> Message:
    """Assistant message issuing a single tool call `tc_id`."""
    return _sized(_assistant_message("a", tool_calls=[_tool_call(tc_id, "tool", {})]), tokens)


def _a_multi(tc_ids: list[str], tokens: int) -> Message:
    """Assistant message issuing several tool calls in one turn."""
    tool_calls = [_tool_call(tc_id, "tool", {}) for tc_id in tc_ids]
    return _sized(_assistant_message("a", tool_calls=tool_calls), tokens)


def _t(tc_id: str, tokens: int) -> Message:
    return _sized(_tool_message(tc_id), tokens)


def _case_no_compaction() -> dict:
    sys, usr = _sys(), _usr()
    a1, t1 = _a("c1", 10), _t("c1", 10)
    a2, t2 = _a("c2", 10), _t("c2", 10)
    a3, t3 = _a("c3", 10), _t("c3", 10)
    messages = [sys, usr, a1, t1, a2, t2, a3, t3]  # total ~70 <= _max_input=800
    return {
        "name": "NoCompactionNeeded",
        "messages": messages,
        "max_context_length": 1000,
        "expected": list(messages),
    }


def _case_drops_oldest_turns() -> dict:
    sys, usr = _sys(), _usr()
    a1, t1 = _a("c1", 40), _t("c1", 60)
    a2, t2 = _a("c2", 40), _t("c2", 60)
    a3, t3 = _a("c3", 40), _t("c3", 60)
    a4, t4 = _a("c4", 40), _t("c4", 60)
    a5, t5 = _a("c5", 40), _t("c5", 60)
    # total 510, _max_input=352, delta=158 -> drop the oldest 2 turns (200)
    messages = [sys, usr, a1, t1, a2, t2, a3, t3, a4, t4, a5, t5]
    return {
        "name": "DropsOldestTurns",
        "messages": messages,
        "max_context_length": 440,
        "expected": [sys, usr, a3, t3, a4, t4, a5, t5],
    }


def _case_keeps_only_most_recent_turn() -> dict:
    sys, usr = _sys(), _usr()
    a1, t1 = _a("c1", 40), _t("c1", 60)
    a2, t2 = _a("c2", 40), _t("c2", 60)
    a3, t3 = _a("c3", 40), _t("c3", 60)
    a4, t4 = _a("c4", 40), _t("c4", 60)
    # total 410, _max_input=150, delta=260 -> drop 3 turns, keep only the last
    messages = [sys, usr, a1, t1, a2, t2, a3, t3, a4, t4]
    return {
        "name": "KeepsOnlyMostRecentTurn",
        "messages": messages,
        "max_context_length": 188,
        "expected": [sys, usr, a4, t4],
    }


def _case_never_splits_multi_tool_turn() -> dict:
    sys, usr = _sys(), _usr()
    a0 = _a_multi(["c0a", "c0b"], 50)
    t0a, t0b = _t("c0a", 100), _t("c0b", 100)  # T0 = 250 across 3 messages
    a1, t1 = _a("c1", 40), _t("c1", 60)
    a2, t2 = _a("c2", 40), _t("c2", 60)
    # total 460, _max_input=250, delta=210 -> T0 (250) dropped whole, no orphan tool
    messages = [sys, usr, a0, t0a, t0b, a1, t1, a2, t2]
    return {
        "name": "NeverSplitsMultiToolTurn",
        "messages": messages,
        "max_context_length": 313,
        "expected": [sys, usr, a1, t1, a2, t2],
    }


def _case_preserves_interleaved_user_message() -> dict:
    # supervised mode (arun): a user message injected between turns must survive
    # even when it sits inside the dropped span.
    sys, usr = _sys(), _usr()
    a1, t1 = _a("c1", 40), _t("c1", 60)
    usr2 = _usr("usr2", tokens=5)
    a2, t2 = _a("c2", 40), _t("c2", 60)
    a3, t3 = _a("c3", 40), _t("c3", 60)
    a4, t4 = _a("c4", 40), _t("c4", 60)
    # total 415, _max_input=250, delta=165 -> drop T1 and T2; usr2 (between them,
    # index < cut) is still preserved by the sys/user branch of the rebuild loop.
    messages = [sys, usr, a1, t1, usr2, a2, t2, a3, t3, a4, t4]
    return {
        "name": "PreservesInterleavedUserMessage",
        "messages": messages,
        "max_context_length": 313,
        "expected": [sys, usr, usr2, a3, t3, a4, t4],
    }


_SLIDING_WINDOW_TESTS = [
    _case_no_compaction(),
    _case_drops_oldest_turns(),
    _case_keeps_only_most_recent_turn(),
    _case_never_splits_multi_tool_turn(),
    _case_preserves_interleaved_user_message(),
]


@pytest.mark.parametrize("test_case", _SLIDING_WINDOW_TESTS, ids=lambda tc: tc["name"])
def test_sliding_window(test_case):
    transform = SlidingWindow(max_context_length=test_case["max_context_length"])
    context = transform(test_case["messages"])

    valid, err = is_valid_context(context)
    assert valid, err
    assert count_tokens(context) <= transform._max_input
    assert context == test_case["expected"], print_decent(context, test_case["expected"])
