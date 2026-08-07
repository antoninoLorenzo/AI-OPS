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
        return None
    
    count = None
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

def is_valid_message_list(messages: list[Message]) -> bool:
    """Ensure the message list contains at least [system, user]."""
    if len(messages) < 2:
        return False

    has_system = messages[0].message.get("role", "") == "system"
    has_user = find_last_user_message_index(messages=messages) is not None

    return has_system and has_user


# --- conversation

class Conversation(BaseModel):
    uuid: str
    short_id: int
    messages: list[Message] = Field(default_factory=list)
