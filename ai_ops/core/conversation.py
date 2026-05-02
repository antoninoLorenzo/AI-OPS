# Agent Orchestrator Implementation
import uuid
from typing import Annotated, Union, Optional, List, Dict

import litellm
from litellm import (
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage,
    ChatCompletionAssistantMessage,
    ChatCompletionToolMessage
)
from pydantic import BaseModel, Discriminator, Tag, Field


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
