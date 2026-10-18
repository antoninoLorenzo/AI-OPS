import json
from ai_ops.core.conversation import Message, get_token_count
from ai_ops.core.schema import Event


DUMMY_SESSION_ID = "test-session"
_VOLATILE_EVENT_FIELDS = {"session_id", "timestamp"}


def event_payload(event: Event) -> dict:
    """Event dump excluding fields that differ per construction (`session_id`,
    `timestamp`), so events can be compared by their meaningful content."""
    return event.model_dump(exclude=_VOLATILE_EVENT_FIELDS)


def assert_events_equal(actual: Event, expected: Event) -> None:
    assert type(actual) is type(expected), f"{type(actual)} != {type(expected)}"
    assert event_payload(actual) == event_payload(expected)


def assert_event_lists_equal(actual: list[Event], expected: list[Event]) -> None:
    assert len(actual) == len(expected), f"len {len(actual)} != {len(expected)}"
    for a, e in zip(actual, expected):
        assert_events_equal(a, e)


def _system_message(text: str) -> Message:
    raw_msg = {"role": "system", "content": text}
    return Message(agent_id="react", message=raw_msg, token_count=get_token_count(raw_msg))


def _user_message(text: str) -> Message:
    raw_msg = {"role": "user", "content": text}
    return Message(agent_id="react", message=raw_msg, token_count=get_token_count(raw_msg))


def _assistant_message(content: str, tool_calls: list[dict] | None = None) -> Message:
    raw_msg = {"role": "assistant", "content": content}
    if tool_calls:
        raw_msg["tool_calls"] = tool_calls
        
    return Message(agent_id="react", message=raw_msg, token_count=get_token_count(raw_msg))


def _tool_call(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)}
    }


def _tool_message(tc_id: str) -> Message:
    raw_msg = {"role": "tool", "content": "res", "tool_call_id": tc_id}
    return Message(agent_id="react", message=raw_msg, token_count=get_token_count(raw_msg))
