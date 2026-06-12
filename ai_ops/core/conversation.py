# Agent Orchestrator Implementation
import uuid
from typing import Annotated, Dict, List, Tuple, Optional, Union

import litellm
from litellm import (
    ChatCompletionAssistantMessage,
    ChatCompletionSystemMessage,
    ChatCompletionToolMessage,
    ChatCompletionUserMessage,
)
from pydantic import (
    BaseModel, 
    Discriminator, 
    Field, Tag
)

from ai_ops.core.log import get_logger, log_event, logging


_logger = get_logger(__name__)


def get_token_count(
    message: Union[
        ChatCompletionSystemMessage,
        ChatCompletionUserMessage,
        ChatCompletionAssistantMessage,
        ChatCompletionToolMessage
    ]
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
    # https://pydantic.dev/docs/validation/latest/concepts/unions/#discriminated-unions-with-callable-discriminator
    message: Annotated[
        Union[
            Annotated[ChatCompletionSystemMessage, Tag("system")],
            Annotated[ChatCompletionUserMessage, Tag("user")],
            Annotated[ChatCompletionAssistantMessage, Tag("assistant")],
            Annotated[ChatCompletionToolMessage, Tag("tool")],
        ],
        Discriminator(lambda v: v.get("role") if isinstance(v, dict) else None)
    ]
    token_count: Optional[int] = None
    internal: bool = False


# --- message utilities

def is_tool_call(message: Message, tool_name_key: str) -> Tuple[bool, List[str] | None]:
    """
    Whether or not ChatCompletionAssistantMessage contains a tool call of 
    tool_name_key.
    Note: a single message can contain multiple tool calls, even of the same type.

    :returns: (False, None) or (True, [tool_call_id, ...])
    """
    msg = message.message
    if not msg.get("role", "") == "assistant":
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


def find_tool_call_result(messages: List[Message], tool_call_id: str) -> int | None:
    """
    :returns: index of ChatCompletionToolMessage with tool_call_id or None
    """
    i, total = 0, len(messages)
    # note: can't do enumerate(reversed(...)), at most enumerate(list(reversed(...)))
    for message in reversed(messages): 
        i+= 1

        msg = message.message
        if not msg.get("role", "") == "tool":
            continue

        if msg.get("tool_call_id", "") == tool_call_id:
            return total - i

    return None


# --- conversation

class Conversation(BaseModel):
    id: str
    messages: List[Message] = Field(default_factory=list)


class ConversationStore:
    def __init__(self):
        # in this phase implementation is only in-memory
        self.__storage: Dict[str, Conversation] = {}

    def create(self, system_prompt: str) -> Conversation:
        conversation_id = str(uuid.uuid4())

        system_prompt_message = ChatCompletionSystemMessage(role='system', content=system_prompt)
        messages = [Message(
            message=system_prompt_message,
            token_count=get_token_count(system_prompt_message)
        )]

        self.__storage[conversation_id] = Conversation(id=conversation_id, messages=messages)
        return self.__storage[conversation_id]

    def from_conversation(self, conversation_id: str, conversation: Conversation):
        self.__storage[conversation_id] = conversation

    def get(self, conversation_id: str) -> Conversation:
        conversation = self.__storage.get(conversation_id, None)
        if conversation is None:
            raise ValueError(f"No conversation for conversation_id={conversation_id}")
        return conversation

    def append(self, conversation_id: str, message: Message):
        conversation = self.__storage.get(conversation_id, None)
        if conversation is None:
            raise ValueError(f"No conversation for conversation_id={conversation_id}")
        conversation.messages.append(message)


_CONVERSATION_STORE: ConversationStore | None = None

def get_conversation_store() -> ConversationStore:
    global _CONVERSATION_STORE
    if _CONVERSATION_STORE is None:
        _CONVERSATION_STORE = ConversationStore()
    return _CONVERSATION_STORE
