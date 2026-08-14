from typing import Annotated

import litellm
from litellm import (
    ChatCompletionAssistantMessage,
    ChatCompletionSystemMessage,
    ChatCompletionToolMessage,
    ChatCompletionUserMessage,
)
from pydantic import BaseModel, Discriminator, Field, Tag

from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)


def get_token_count(
    message: ChatCompletionSystemMessage | ChatCompletionUserMessage | ChatCompletionAssistantMessage | ChatCompletionToolMessage
) -> int | None:
    """
    Estimates the token count of a single chat message.

    Counting should happen only after the full message is available, which 
    keeps the behavior consistent between streaming and non-streaming.
    To keep the agent loop reliable it never raises, errors are logged and 
    the token count is set to None, which the `Message` model supports.

    The implementation uses `litellm.token_counter` with a known trade-off:
    `token_counter` defaults to tiktoken, so the count is an approximation 
    for most models, it supports huggingface tokenizers, however dyanmically 
    initializing one based on configs would be a pain in the ass.
    """
    text = message.get("content")
    tool_calls = message.get("tool_calls")

    if tool_calls:
        args_text = " ".join(
            tc.get("function", {}).get("arguments", "")
            if isinstance(tc, dict)
            else tc.function.arguments
            for tc in tool_calls
        )
        text = (text or "") + args_text

    if not text:
        log_event(
            _logger, logging.WARNING, "Unexpected empty text", 
            message_type=type(text) if text is not None else None
        )
        return 0
    
    count = 0
    try:
        # note: gpt-3.5-turbo is just a tokenizer hint, it will pick up 
        # tiktoken with cl100k_base under the hood.
        count = litellm.token_counter(model="gpt-3.5-turbo", text=text)
    except ValueError as err:
        log_event(_logger, logging.WARNING, "Failed counting tokens", error=f"\"{err}\"")

    return count

class Message(BaseModel):
    message: Annotated[
        Annotated[ChatCompletionSystemMessage, Tag("system")] | Annotated[ChatCompletionUserMessage, Tag("user")] | Annotated[ChatCompletionAssistantMessage, Tag("assistant")] | Annotated[ChatCompletionToolMessage, Tag("tool")],
        Discriminator(lambda v: v.get("role") if isinstance(v, dict) else None)
    ]
    """`ChatCompletionX` is just a `TypedDict` of OpenAI schemas."""
    # https://pydantic.dev/docs/validation/latest/concepts/unions/#discriminated-unions-with-callable-discriminator

    agent_id: str
    """Identifier of the agent that authored this message (see `AgentConfig.agent_id`)."""

    token_count: int | None = None
    """Required for context compaction."""

    model_id: str | None = None
    """Useful for analysis. System and user messages won't have this field."""



# --- message utilities

def count_tokens(messages: list[Message]) -> int:
    token_count = 0
    for message in messages:
        if message.token_count is None:
            message.token_count = get_token_count(message.message)
        token_count += message.token_count
    return token_count


def is_user_message(message: Message) -> bool:
    msg = message.message
    return msg.get("role", "") == "user"


def is_tool_call(message: Message, tool_name_key: str) -> tuple[bool, list[str] | None]:
    """
    Whether or not ChatCompletionAssistantMessage contains a tool call of 
    tool_name_key.
    Note: a single message can contain multiple tool calls, even of the same type.

    :returns: (False, None) or (True, [tool_call_id, ...])
    """
    msg = message.message
    if msg.get("role", "") != "assistant":
        return False, None
    
    tool_calls = msg.get("tool_calls")
    if tool_calls is None:
        return False, None

    ids = []
    for tool_call in tool_calls:
        function = tool_call.get("function")
        if function is None:
            continue

        tool_name = function.get("name")
        if tool_name == tool_name_key and tool_call.get("id"):
            ids.append(tool_call["id"])

    if len(ids):
        return True, ids

    return False, None


def find_tool_call_result(messages: list[Message], tool_call_id: str) -> int | None:
    """
    :returns: index of ChatCompletionToolMessage with tool_call_id or None
    """
    i, total = 0, len(messages)
    # note: can't do enumerate(reversed(...)), at most enumerate(list(reversed(...)))
    for message in reversed(messages): 
        i+= 1

        msg = message.message
        if msg.get("role", "") != "tool":
            continue

        if msg.get("tool_call_id", "") == tool_call_id:
            return total - i

    return None

def find_last_user_message_index(messages: list[Message]) -> int | None:
    """
    :returns: index of last ChatCompletionUserMessage or None
    """
    last_usr_idx = next(
        (
            idx for idx in range(len(messages)-1, -1 , -1)
            if messages[idx].message.get("role", "") == "user"
        ),
        None
    )
    return last_usr_idx


def find_parent_assistant_index(messages: list[Message], tool_result_idx: int)-> int | None:
    """
    Walk backwards to find the assistant message owning the tool result with `tool_result_idx`.

    :returns: index of the parent assistant message or None.
    """
    if tool_result_idx >= len(messages):
        return None
    
    tool_call_id = messages[tool_result_idx].message.get("tool_call_id")
    if not tool_call_id:
        return None

    for idx in range(tool_result_idx - 1, -1, -1):
        msg = messages[idx].message
        if msg["role"] != "assistant":
            continue

        for tool_call in msg.get("tool_calls", []):
            if tool_call.get("id", "") == tool_call_id:
                return idx
    
    return None
    

def is_valid_context(messages: list[Message]) -> tuple[bool, str | None]:
    """
    Verify a message list follows Chat Completion and application invariants.

    Application requires at least one system and one user message.
    > Chat Completions allows >=1 of type sys|usr|assistant.

    Chat Completion verified invariants:
    * Backward Paring : each tool message follows a preceding assistant message with tool_calls.
    * Dangling Calls  : right after an assistant message with N tool_calls there should be N tool 
                        messages corresponding to each tool_call_id.

    :returns: (True, None) -> valid; (False, str) -> invalid 
    """
    if len(messages) < 2:
        return False, "At least [sys, usr]"

    if not (
        messages[0].message["role"] == "system" 
        and messages[1].message["role"] == "user"
    ):
        return False, "At least [sys, usr]"

    tool_call_set = set()
    for rev_idx, message in enumerate(reversed(messages[2:])):
        msg = message.message
        msg_idx = len(messages) - rev_idx
        role = msg["role"]

        if role == "tool":
            tool_call_set.add(msg.get("tool_call_id"))
            continue
        
        if role == "assistant":
            tool_calls = msg.get("tool_calls", []) # tool_calls is reference!
            if len(tool_calls) != len(tool_call_set):
                return False, f"Assistant message at {msg_idx} has {len(tool_calls)} tool calls found {len(tool_call_set)} tool results"
            
            for tool_call in tool_calls:
                tc_id = tool_call.get("id", "")
                if tc_id not in tool_call_set:
                    return False, f"Assistant message at {msg_idx} has tool call {tc_id} not found in tool_call_set"
                tool_call_set.remove(tc_id)
            
            if len(tool_call_set) > 0:
                return False, f"Tool message(s) with no backward pair: {tool_call_set}"

            continue

        if len(tool_call_set) > 0:
            return False, f"Found {role} message in between assistant and tool calls"
            
    return True, None


# --- conversation

class Conversation(BaseModel):
    uuid: str
    short_id: int
    messages: list[Message] = Field(default_factory=list)
