"""
Tests for `ai_ops.core.event_store`.

Per the review scope only the JSONL-backed store and the `get_event_store`
singleton are exercised (the in-memory store is a thin dict wrapper).

`JSONLEventStore` computes its base dir from `AI_OPS_BASE_DIR` at construction,
so the `jsonl_base` fixture monkeypatches that symbol *before* any store is
built and lays down the `conversations/` root the store expects.
"""
import json

import pytest

from ai_ops.core.schema import (
    UserMessageEvent,
    TextEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolResultEvent,
    StopEvent,
    EventType,
)
from ai_ops.core.conversation import StorageStrategy
from ai_ops.core.event_store import (
    EventStore,
    JSONLEventStore,
    InMemoryEventStore,
    get_event_store,
)
import ai_ops.core.event_store as event_store_mod

from test.core.mocks.tool import MockTool, MockIn, MockOut, register_mock_tool


@pytest.fixture
def jsonl_base(tmp_path, monkeypatch):
    """Point JSONLEventStore at an isolated base dir and return it."""
    monkeypatch.setattr("ai_ops.core.event_store.AI_OPS_BASE_DIR", tmp_path)
    (tmp_path / "conversations").mkdir()
    return tmp_path


def _conversation_dir(jsonl_base, conversation_id: str):
    """Create and return the on-disk dir a conversation's events live under."""
    path = jsonl_base / "conversations" / conversation_id
    path.mkdir()
    return path


# --- JSONLEventStore ---------------------------------------------------------

def test_get_unknown_conversation_returns_empty(jsonl_base):
    store = JSONLEventStore()
    assert store.get_by_conversation_uuid("does-not-exist") == []


def test_append_unknown_conversation_raises(jsonl_base):
    # append refuses to create the events file when the conversation dir is
    # absent (the conversation must have been created first).
    store = JSONLEventStore()
    with pytest.raises(ValueError):
        store.append("does-not-exist", StopEvent(issuer="agent"))


def test_append_then_get_roundtrips(jsonl_base):
    store = JSONLEventStore()
    _conversation_dir(jsonl_base, "conv-1")

    store.append("conv-1", UserMessageEvent(content="hello"))
    store.append("conv-1", TextEvent(chunk="hi there"))
    store.append("conv-1", StopEvent(issuer="agent", reason="done"))

    events = store.get_by_conversation_uuid("conv-1")
    assert [e.kind for e in events] == [
        EventType.USER_MESSAGE, EventType.TEXT, EventType.STOP
    ]
    assert events[0].content == "hello"
    assert events[1].chunk == "hi there"
    assert events[2].issuer == "agent" and events[2].reason == "done"


def test_persists_across_instances(jsonl_base):
    _conversation_dir(jsonl_base, "conv-2")
    JSONLEventStore().append("conv-2", TextEvent(chunk="persisted"))

    # a fresh instance over the same base dir reloads from disk.
    reloaded = JSONLEventStore().get_by_conversation_uuid("conv-2")
    assert len(reloaded) == 1
    assert isinstance(reloaded[0], TextEvent)
    assert reloaded[0].chunk == "persisted"


def test_roundtrip_preserves_event_polymorphism(jsonl_base):
    # every concrete event type reloads as its own class via the AnyEvent
    # discriminated union (keyed on `kind`).
    store = JSONLEventStore()
    _conversation_dir(jsonl_base, "conv-3")

    written = [
        UserMessageEvent(content="go"),
        ReasoningEvent(chunk="thinking"),
        ToolCallEvent(call_id="1", name=MockTool.name, args=MockIn(val=1)),
        ToolResultEvent(call_id="1", name=MockTool.name, args=MockIn(val=1), result=MockOut(val=1)),
        StopEvent(issuer="agent"),
    ]
    for event in written:
        store.append("conv-3", event)

    reloaded = store.get_by_conversation_uuid("conv-3")
    assert [type(e) for e in reloaded] == [type(e) for e in written]


def test_malformed_events_file_raises_runtime_error(jsonl_base):
    conv_dir = _conversation_dir(jsonl_base, "conv-4")
    # valid JSON but not a valid event -> ValidationError, wrapped as RuntimeError.
    (conv_dir / JSONLEventStore.EVENTS_FILE).write_text(
        json.dumps({"kind": "not-a-real-kind"}) + "\n", encoding="utf-8"
    )

    with pytest.raises(RuntimeError):
        JSONLEventStore().get_by_conversation_uuid("conv-4")


def test_roundtrip_preserves_tool_payload_types(jsonl_base, register_mock_tool):
    # tool args and result are `SerializeAsAny[BaseModel]`, the persist -> load
    # roundtrip has to preserve the tool in/out base models.
    store = JSONLEventStore()
    _conversation_dir(jsonl_base, "conv-5")

    store.append(
        "conv-5",
        ToolResultEvent(
            call_id="1", name=MockTool.name,
            args=MockIn(val=42), result=MockOut(val=42)
        ),
    )

    # note: the event store doesn't have an in-memory cache so this actually 
    # reads from the serialized jsonl
    reloaded = store.get_by_conversation_uuid("conv-5")[0]
    assert isinstance(reloaded.args, MockIn)
    assert isinstance(reloaded.result, MockOut)
    assert reloaded.args.val == 42
    assert reloaded.result.val == 42
    
    dumped = reloaded.model_dump(mode="json")
    assert dumped["result"] == {"val": 42}
    assert dumped["args"] == {"val": 42}


# --- get_event_store singleton ----------------------------------------------

def test_get_event_store_is_singleton(jsonl_base):
    first = get_event_store()
    second = get_event_store()
    assert first is second


def test_get_event_store_selects_impl_by_strategy(jsonl_base):
    # the root autouse fixture reset the singleton, so this call builds it.
    store = get_event_store(strategy=StorageStrategy.JSONL)
    assert isinstance(store._store, JSONLEventStore)


def test_get_event_store_default_is_in_memory(jsonl_base):
    store = get_event_store()
    assert isinstance(store._store, InMemoryEventStore)
