"""
Tests for `ai_ops.core.storage.session`.

`SessionStore` merges the old `ConversationStore` (messages) and `EventStore`
(events) into a single `Session` keyed by uuid/short_id. Behaviour shared by
every `AbstractSessionStore` implementation runs against each strategy via the
parametrized `store` fixture; the JSONL- and in-memory-specific bits get their
own sections.

`JSONLSessionStore` computes its base dir from `AI_OPS_BASE_DIR` at
construction, so the `jsonl_base` fixture monkeypatches that symbol *before* any
store is built and lays down the `sessions/` root the store expects (in
production `ai_ops.config.build_environment` creates it).
"""
import json

import pytest
from litellm import ChatCompletionUserMessage

from ai_ops.core.conversation import Message
from ai_ops.core.schema import (
    UserMessageEvent,
    TextEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolResultEvent,
    StopEvent,
    EventType,
)
from ai_ops.core.storage import StorageStrategy
from ai_ops.core.storage.session import (
    Session,
    SessionStore,
    JSONLSessionStore,
    InMemorySessionStore,
    get_session_store,
)
import ai_ops.core.storage.session as session_mod

from test.core.mocks.tool import MockTool, MockIn, MockOut, register_mock_tool  # noqa: F401


def _user_message(text: str) -> Message:
    return Message(agent_id="react", message=ChatCompletionUserMessage(role="user", content=text))


@pytest.fixture
def jsonl_base(tmp_path, monkeypatch):
    """Point JSONLSessionStore at an isolated base dir and return it."""
    monkeypatch.setattr("ai_ops.core.storage.session.AI_OPS_BASE_DIR", tmp_path)
    (tmp_path / "sessions").mkdir()
    return tmp_path


@pytest.fixture(params=["in_memory", "jsonl"])
def store(request, jsonl_base):
    """A fresh, empty store for each supported strategy."""
    if request.param == "in_memory":
        return InMemorySessionStore()
    return JSONLSessionStore()


# --- behaviour shared by every AbstractSessionStore implementation ------------

def test_create_returns_fresh_session(store):
    session = store.create_session()

    assert isinstance(session, Session)
    assert session.uuid
    assert session.short_id == 1
    assert session.messages == []
    assert session.events == []


def test_create_increments_short_id(store):
    first = store.create_session()
    second = store.create_session()

    assert first.short_id == 1
    assert second.short_id == 2
    assert first.uuid != second.uuid


def test_get_session_uuid_returns_created(store):
    created = store.create_session()

    assert store.get_session_uuid(created.short_id) == created.uuid


def test_get_session_by_uuid_returns_created(store):
    created = store.create_session()

    assert store.get_session_by_uuid(created.uuid).uuid == created.uuid


def test_append_message_then_retrieve(store):
    created = store.create_session()
    store.append_message(created.uuid, _user_message("hello"))

    messages = store.get_messages_by_uuid(created.uuid)
    assert len(messages) == 1
    assert messages[0].message.get("content") == "hello"


def test_append_event_then_retrieve(store):
    created = store.create_session()
    store.append_event(created.uuid, UserMessageEvent(content="hello"))

    events = store.get_events_by_uuid(created.uuid)
    assert len(events) == 1
    assert events[0].content == "hello"


def test_messages_and_events_are_independent(store):
    created = store.create_session()
    store.append_message(created.uuid, _user_message("m"))
    store.append_event(created.uuid, TextEvent(chunk="e"))

    assert len(store.get_messages_by_uuid(created.uuid)) == 1
    assert len(store.get_events_by_uuid(created.uuid)) == 1


_UNKNOWN_LOOKUP_TESTS = [
    {"name": "get_session_uuid unknown", "method": "get_session_uuid", "arg": 999},
    {"name": "get_session_by_uuid unknown", "method": "get_session_by_uuid", "arg": "does-not-exist"},
    {"name": "get_messages_by_uuid unknown", "method": "get_messages_by_uuid", "arg": "does-not-exist"},
    {"name": "get_events_by_uuid unknown", "method": "get_events_by_uuid", "arg": "does-not-exist"},
]


@pytest.mark.parametrize("test_case", _UNKNOWN_LOOKUP_TESTS, ids=lambda tc: tc["name"])
def test_unknown_lookup_raises(store, test_case):
    with pytest.raises(ValueError):
        getattr(store, test_case["method"])(test_case["arg"])


def test_append_message_unknown_session_raises(store):
    with pytest.raises(ValueError):
        store.append_message("does-not-exist", _user_message("hello"))


def test_append_event_unknown_session_raises(store):
    with pytest.raises(ValueError):
        store.append_event("does-not-exist", StopEvent(issuer="agent"))


# --- JSONLSessionStore specifics ---------------------------------------------

def test_jsonl_persists_across_instances(jsonl_base):
    store_a = JSONLSessionStore()
    created = store_a.create_session()
    store_a.append_message(created.uuid, _user_message("persisted"))
    store_a.append_event(created.uuid, TextEvent(chunk="persisted-event"))

    # a fresh instance over the same base dir must reload everything from disk
    store_b = JSONLSessionStore()

    reloaded = store_b.get_session_by_uuid(created.uuid)
    assert reloaded.short_id == created.short_id
    assert len(reloaded.messages) == 1
    assert reloaded.messages[0].message.get("content") == "persisted"
    assert len(reloaded.events) == 1
    assert reloaded.events[0].chunk == "persisted-event"

    assert store_b.get_session_uuid(created.short_id) == created.uuid


def test_jsonl_short_id_counter_resumes_across_instances(jsonl_base):
    first = JSONLSessionStore().create_session()
    second = JSONLSessionStore().create_session()

    assert first.short_id == 1
    assert second.short_id == 2


def test_jsonl_roundtrip_preserves_event_polymorphism(jsonl_base, register_mock_tool):
    # every concrete event type reloads as its own class via the AnyEvent
    # discriminated union (keyed on `kind`).
    store = JSONLSessionStore()
    created = store.create_session()

    written = [
        UserMessageEvent(content="go"),
        ReasoningEvent(chunk="thinking"),
        ToolCallEvent(call_id="1", name=MockTool.name, args=MockIn(val=1)),
        ToolResultEvent(call_id="1", name=MockTool.name, args=MockIn(val=1), result=MockOut(val=1)),
        StopEvent(issuer="agent"),
    ]
    for event in written:
        store.append_event(created.uuid, event)

    # a fresh instance reads the serialized jsonl back from disk.
    reloaded = JSONLSessionStore().get_events_by_uuid(created.uuid)
    assert [type(e) for e in reloaded] == [type(e) for e in written]


def test_jsonl_roundtrip_preserves_tool_payload_types(jsonl_base, register_mock_tool):
    # tool args and result are `SerializeAsAny[BaseModel]`, the persist -> load
    # roundtrip has to preserve the tool in/out base models.
    store = JSONLSessionStore()
    created = store.create_session()

    store.append_event(
        created.uuid,
        ToolResultEvent(
            call_id="1", name=MockTool.name,
            args=MockIn(val=42), result=MockOut(val=42)
        ),
    )

    reloaded = JSONLSessionStore().get_events_by_uuid(created.uuid)[0]
    assert isinstance(reloaded.args, MockIn)
    assert isinstance(reloaded.result, MockOut)
    assert reloaded.args.val == 42
    assert reloaded.result.val == 42

    dumped = reloaded.model_dump(mode="json")
    assert dumped["args"] == {"val": 42}
    assert dumped["result"] == {"val": 42}


def test_jsonl_malformed_events_file_raises_runtime_error(jsonl_base):
    store = JSONLSessionStore()
    created = store.create_session()

    # valid JSON but not a valid event -> ValidationError, wrapped as RuntimeError.
    events_path = jsonl_base / "sessions" / created.uuid / JSONLSessionStore.EVENTS_FILE
    events_path.write_text(json.dumps({"kind": "not-a-real-kind"}) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError):
        store.get_events_by_uuid(created.uuid)


# --- get_session_store singleton ---------------------------------------------

def test_get_session_store_is_singleton(jsonl_base):
    session_mod._SESSION_STORE = None
    first = get_session_store()
    second = get_session_store()
    assert first is second


def test_get_session_store_selects_impl_by_strategy(jsonl_base):
    session_mod._SESSION_STORE = None
    store = get_session_store(strategy=StorageStrategy.IN_MEMORY)
    assert isinstance(store._store, InMemorySessionStore)


def test_get_session_store_default_is_jsonl(jsonl_base):
    session_mod._SESSION_STORE = None
    store = get_session_store()
    assert isinstance(store._store, JSONLSessionStore)
