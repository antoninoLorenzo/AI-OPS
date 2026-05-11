# Agent Orchestrator Implementation
import uuid
from typing import Annotated, Dict, List, Optional, Union

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
        count = litellm.token_counter(text=text)
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


class Conversation(BaseModel):
    id: str
    messages: List[Message] = Field(default_factory=list)


class ConversationStore:
    def __init__(self):
        # in this phase implementation is only in-memory
        self.__storage: Dict[str, Conversation] = {}

    def create(self, system_prompt: str) -> Conversation:
        conversation_id = str(uuid.uuid4())

        messages = [Message(
            message=ChatCompletionSystemMessage(role='system', content=system_prompt),
            token_count=litellm.token_counter(text=system_prompt)
        )]

        self.__storage[conversation_id] = Conversation(id=conversation_id, messages=messages)
        return self.__storage[conversation_id]

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
