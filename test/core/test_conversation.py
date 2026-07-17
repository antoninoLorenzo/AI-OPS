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
    Message,
    Conversation,
    InMemoryConversationStore,
    JSONLConversationStore,
    read_jsonl,
)
from test.core.mocks.tool import MockTool


def _user_message(text: str) -> Message:
    return Message(message=ChatCompletionUserMessage(role="user", content=text))


_IS_TOOL_CALL_TESTS = [
    # not assistant message
    {
        "name": "NotAssistantMessage",
        "message": Message(message=ChatCompletionUserMessage(role="user", content="hello")),
        "tool_name_key": MockTool.name,
        "expected": (False, None),
    },
    # assistant message with no tool_calls
    {
        "name": "NoToolCalls",
        "message": Message(
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
        "message": Message(
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
        "message": Message(
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
        "message": Message(
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
        "message": Message(
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
        "message": Message(
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
            Message(message=ChatCompletionUserMessage(role="user", content="hello")),
            Message(
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
            Message(message=ChatCompletionUserMessage(role="user", content="hello")),
            Message(
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
            Message(
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
            Message(message=ChatCompletionUserMessage(role="user", content="hello")),
            Message(
                message=ChatCompletionAssistantMessage(
                    role="assistant",
                    content="call one",
                )
            ),
            Message(
                message=ChatCompletionToolMessage(
                    role="tool",
                    tool_call_id="call_1",
                    content="first result",
                )
            ),
            Message(message=ChatCompletionUserMessage(role="user", content="more text")),
            Message(
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


# --- conversation stores

@pytest.fixture
def jsonl_base(tmp_path, monkeypatch):
    """Point JSONLConversationStore at an isolated base dir and return it."""
    monkeypatch.setattr("ai_ops.core.conversation.AI_OPS_BASE_DIR", tmp_path)
    (tmp_path / "conversations").mkdir()
    return tmp_path


@pytest.fixture(params=["in_memory", "jsonl"])
def store(request, jsonl_base):
    """A fresh, empty store for each supported strategy."""
    if request.param == "in_memory":
        return InMemoryConversationStore()
    return JSONLConversationStore()


# behavior shared by every AbstractConversationStore implementation, run against
# each strategy via the parametrized `store` fixture.

def test_create_returns_fresh_conversation(store):
    conversation = store.create()

    assert isinstance(conversation, Conversation)
    assert conversation.uuid
    assert conversation.short_id == 1
    assert conversation.messages == []


def test_create_increments_short_id(store):
    first = store.create()
    second = store.create()

    assert first.short_id == 1
    assert second.short_id == 2
    assert first.uuid != second.uuid


def test_get_by_uuid_returns_created(store):
    created = store.create()

    assert store.get_by_uuid(created.uuid).uuid == created.uuid


def test_get_by_short_id_returns_created(store):
    created = store.create()

    assert store.get_by_short_id(created.short_id).uuid == created.uuid


def test_append_then_retrieve(store):
    created = store.create()
    store.append(created.uuid, _user_message("hello"))

    conversation = store.get_by_uuid(created.uuid)
    assert len(conversation.messages) == 1
    assert conversation.messages[0].message.get("content") == "hello"


_UNKNOWN_LOOKUP_TESTS = [
    {"name": "get_by_uuid unknown", "method": "get_by_uuid", "arg": "does-not-exist"},
    {"name": "get_by_short_id unknown", "method": "get_by_short_id", "arg": 999},
]


@pytest.mark.parametrize("test_case", _UNKNOWN_LOOKUP_TESTS, ids=lambda tc: tc["name"])
def test_unknown_lookup_raises(store, test_case):
    with pytest.raises(ValueError):
        getattr(store, test_case["method"])(test_case["arg"])


def test_append_unknown_conversation_raises(store):
    with pytest.raises(ValueError):
        store.append("does-not-exist", _user_message("hello"))


# InMemoryConversationStore specifics

def test_in_memory_from_conversation():
    store = InMemoryConversationStore()
    conversation = Conversation(uuid="abc", short_id=7, messages=[_user_message("hi")])

    store.from_conversation("abc", conversation)

    assert store.get_by_uuid("abc") is conversation
    assert store.get_by_short_id(7) is conversation


# JSONLConversationStore specifics

def test_jsonl_from_conversation_not_implemented(jsonl_base):
    store = JSONLConversationStore()
    with pytest.raises(NotImplementedError):
        store.from_conversation("abc", Conversation(uuid="abc", short_id=1))


def test_jsonl_persists_across_instances(jsonl_base):
    store_a = JSONLConversationStore()
    created = store_a.create()
    store_a.append(created.uuid, _user_message("persisted"))

    # a fresh instance over the same base dir must reload everything from disk
    store_b = JSONLConversationStore()

    by_uuid = store_b.get_by_uuid(created.uuid)
    assert by_uuid.short_id == created.short_id
    assert len(by_uuid.messages) == 1
    assert by_uuid.messages[0].message.get("content") == "persisted"

    assert store_b.get_by_short_id(created.short_id).uuid == created.uuid


def test_jsonl_short_id_counter_resumes_across_instances(jsonl_base):
    first = JSONLConversationStore().create()
    second = JSONLConversationStore().create()

    assert first.short_id == 1
    assert second.short_id == 2


def test_read_jsonl_skips_malformed_lines(tmp_path):
    path = tmp_path / "messages.jsonl"
    path.write_text('{"a": 1}\nnot json\n{"b": 2}\n', encoding="utf-8")

    assert list(read_jsonl(path)) == [{"a": 1}, {"b": 2}]