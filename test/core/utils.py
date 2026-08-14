import json
from ai_ops.core.conversation import Message, get_token_count


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
