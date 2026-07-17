# Agent Orchestrator Implementation
import abc
import json 
import uuid
from enum import StrEnum, auto
from pathlib import Path
from typing import Annotated, Dict, List, Tuple, Optional, Union, Type

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
from ai_ops.config import AI_OPS_BASE_DIR

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

def find_last_user_message_index(messages: List[Message]) -> int | None:
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

def is_valid_message_list(messages: List[Message]) -> bool:
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
    messages: List[Message] = Field(default_factory=list)


class AbstractConversationStore(abc.ABC):
    @abc.abstractmethod
    def create(self) -> Conversation:
        raise NotImplementedError()

    @abc.abstractmethod
    def from_conversation(self, conversation_id: str, conversation: Conversation):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_by_uuid(self, conversation_id: str) -> Conversation:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_by_short_id(self, short_id: int) -> Conversation:
        raise NotImplementedError()

    @abc.abstractmethod
    def append(self, conversation_id: str, message: Message) -> None:
        raise NotImplementedError()


class InMemoryConversationStore(AbstractConversationStore):
    def __init__(self):
        self.__storage: Dict[str, Conversation] = {}
        self.__short_id_idx: Dict[int, str] = {}
        self.__last_short_id = 0

    def create(self) -> Conversation:
        conversation_id = str(uuid.uuid4())
        short_id = self.__last_short_id + 1

        self.__storage[conversation_id] = Conversation(uuid=conversation_id, short_id=short_id)
        self.__short_id_idx[short_id] = conversation_id
        self.__last_short_id = short_id

        return self.__storage[conversation_id]

    def from_conversation(self, conversation_id: str, conversation: Conversation):
        self.__storage[conversation_id] = conversation
        self.__short_id_idx[conversation.short_id] = conversation_id

    def get_by_uuid(self, conversation_id: str) -> Conversation:
        conversation = self.__storage.get(conversation_id, None)
        if conversation is None:
            raise ValueError(f"No conversation for conversation_id={conversation_id}")
        return conversation

    def get_by_short_id(self, short_id: int) -> Conversation:
        conversation_id = self.__short_id_idx.get(short_id)
        if conversation_id is None:
            raise ValueError(f"No conversation for short_id={short_id}")
            
        return self.__storage[conversation_id]

    def append(self, conversation_id: str, message: Message) -> None:
        conversation = self.__storage.get(conversation_id, None)
        if conversation is None:
            raise ValueError(f"No conversation for conversation_id={conversation_id}")
        conversation.messages.append(message)


# note: could merge this in conversation store and the file handles returned by `open` 
# could be cached and deleted at object destruction.
def read_jsonl(file: Path):
    with open(str(file), 'r', encoding='utf-8') as fp:
        for line_no, line in enumerate(fp, start=1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                pass


def append_jsonl(file: Path, raw: str):
    with open(str(file), 'a', encoding='utf-8') as fp:
        fp.write(raw + "\n")
        

class JSONLConversationStore(AbstractConversationStore):
    MESSAGES_FILE = "messages.jsonl"

    def __init__(self):
        # note: paths need to be mocked in tests
        self.base_dir = AI_OPS_BASE_DIR / "conversations"
        self.index_path = AI_OPS_BASE_DIR / "index.json" 

        if not self.index_path.exists():
            self.__index: Dict[int, str] = {} # short_id -> uuid
            self.index_path.touch()
            with open(str(self.index_path), 'w') as fp:
                json.dump(self.__index, fp)

            self.__last_short_id = 0
        else:
            with open(str(self.index_path), 'r') as fp:
                raw_index = json.load(fp)
            self.__index = {int(k): v for k, v in raw_index.items()}

            short_ids = sorted(self.__index)
            self.__last_short_id = short_ids[-1] if len(short_ids) else 0

        self.__conversations = {}

    def __load_conversation(self, conversation_id: str) -> Conversation:
        messages_path = self.base_dir / conversation_id / self.MESSAGES_FILE
        if not messages_path.exists():
            raise RuntimeError(f"Conversation not found: {conversation_id}")
        
        # here we assume there's always a short id btw
        short_id = 0
        for sid, cid in self.__index.items():
            if cid == conversation_id:
                short_id = sid
                break

        conversation = Conversation(uuid=conversation_id, short_id=short_id)
        for raw_message in read_jsonl(messages_path):
            # read_jsonl already parses each line into a dict, so validate the
            # object rather than a JSON string.
            message = Message.model_validate(raw_message)
            conversation.messages.append(message)
        
        return conversation

    def __update_index(self, short_id: int, conversation_id: str):
        with open(str(self.index_path), 'r') as fp:
            index = json.load(fp)
        
        index[short_id] = conversation_id

        with open(str(self.index_path), 'w') as fp:
            json.dump(index, fp)

        self.__index[short_id] = conversation_id

    def create(self) -> Conversation:
        conversation_id = str(uuid.uuid4())
        short_id = self.__last_short_id + 1
        # collision realistically never happen within this scope so assume it never raises
        (self.base_dir / conversation_id).mkdir()

        conversation = Conversation(uuid=conversation_id, short_id=short_id)
        self.__conversations[conversation_id] = conversation
        self.__last_short_id = short_id
        self.__update_index(short_id=short_id, conversation_id=conversation_id)
        
        return conversation
    
    def from_conversation(self, conversation_id: str, conversation: Conversation):
        raise NotImplementedError()

    def get_by_uuid(self, conversation_id: str) -> Conversation:
        if conversation_id in self.__conversations:
            return self.__conversations[conversation_id]
        
        try:
            conversation = self.__load_conversation(conversation_id=conversation_id)
            self.__conversations[conversation_id] = conversation
            return conversation
        except RuntimeError:
            raise ValueError(f"No conversation for conversation_id={conversation_id}")
    
    def get_by_short_id(self, short_id: int) -> Conversation:
        conversation_id = self.__index.get(short_id)
        if conversation_id is None:
            raise ValueError(f"No conversation for short_id={short_id}")

        return self.get_by_uuid(conversation_id=conversation_id)
    
    def append(self, conversation_id: str, message: Message) -> None:
        # resolving the conversation first keeps the in-memory cache in sync with
        # what's persisted and mirrors InMemoryConversationStore by raising when the
        # conversation is unknown.
        conversation = self.get_by_uuid(conversation_id=conversation_id)

        messages_path = self.base_dir / conversation_id / self.MESSAGES_FILE
        raw_message = message.model_dump_json()
        append_jsonl(file=messages_path, raw=raw_message)

        conversation.messages.append(message)


class ConversationStore:
    def __init__(self, store_cls: Type[AbstractConversationStore]):
        self.__store = store_cls()

    def create(self) -> Conversation:
        return self.__store.create()

    def from_conversation(self, conversation_id: str, conversation: Conversation):
        self.__store.from_conversation(conversation_id=conversation_id, conversation=conversation)

    def get_by_uuid(self, conversation_id: str) -> Conversation:
        return self.__store.get_by_uuid(conversation_id=conversation_id)

    def get_by_short_id(self, short_id: int) -> Conversation:
        return self.__store.get_by_short_id(short_id=short_id)

    def append(self, conversation_id: str, message: Message) -> None:
        self.__store.append(conversation_id=conversation_id, message=message)


class ConversationStoreStrategy(StrEnum):
    IN_MEMORY = auto()
    JSONL = auto()


_CONVERSATION_STORE_IMPL = {
    ConversationStoreStrategy.IN_MEMORY: InMemoryConversationStore,
    ConversationStoreStrategy.JSONL: JSONLConversationStore
}
_CONVERSATION_STORE: ConversationStore | None = None


def get_conversation_store(strategy: ConversationStoreStrategy = ConversationStoreStrategy.IN_MEMORY) -> ConversationStore:
    global _CONVERSATION_STORE
    if _CONVERSATION_STORE is None:
        _CONVERSATION_STORE = ConversationStore(store_cls=_CONVERSATION_STORE_IMPL[strategy])
    return _CONVERSATION_STORE
