import abc
import json
import uuid
from enum import StrEnum, auto
from typing import List, Dict, Type

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ai_ops.config import AI_OPS_BASE_DIR
from ai_ops.core.schema import Event, EventType, AnyEvent
from ai_ops.core.tools import resolve_args_type, resolve_result_type
from ai_ops.core.conversation import Message
from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core.storage.json_utils import read_jsonl, append_jsonl


_logger = get_logger(__name__)
_event_adapter = TypeAdapter(AnyEvent)


class Session(BaseModel):
    uuid: str
    short_id: int
    events: List[AnyEvent] = Field(default_factory=list)
    messages: List[Message] = Field(default_factory=list)
    # note: messages already carry model_id and agent_id


class StorageStrategy(StrEnum):
    IN_MEMORY = auto()
    JSONL = auto()


class AbstractSessionStore(abc.ABC):
    @abc.abstractmethod
    def create_session(self) -> Session:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_session_uuid(self, short_id: int) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_session_by_uuid(self, session_id: str) -> Session:
        raise NotImplementedError()

    @abc.abstractmethod
    def append_message(self, session_id: str, message: Message) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def append_event(self, session_id: str, event: Event) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_messages_by_uuid(self, session_id: str) -> List[Message]:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_events_by_uuid(self, session_id: str) -> List[Event]:
        raise NotImplementedError()


def _hydrate_tool_payload(raw: dict) -> dict:
    # deserialization of ToolCallEvent/ToolResultEvent is tricky because the Event 
    # schema uses `SerializeAsAny[BaseModel]` so we need to resolve the actual BaseModel 
    # on the way back to keep type-safety.
    kind = raw.get("kind")
    if kind not in (EventType.TOOL_CALL, EventType.TOOL_RESULT):
        return raw

    name = raw.get("name")

    args_type = resolve_args_type(name)
    if isinstance(raw.get("args"), dict):
        if args_type is not None:
            raw["args"] = args_type.model_validate(raw["args"])
        else:
            log_event(_logger, logging.WARNING, "Unresolvable tool args type", tool_name=name)

    if kind == EventType.TOOL_RESULT and isinstance(raw.get("result"), dict):
        result_type = resolve_result_type(name)
        if result_type is not None:
            raw["result"] = result_type.model_validate(raw["result"])
        else:
            log_event(_logger, logging.WARNING, "Unresolvable tool result type", tool_name=name)

    return raw


class JSONLSessionStore(AbstractSessionStore):
    INDEX_FILE    = "index.json"
    MESSAGES_FILE = "messages.jsonl"
    EVENTS_FILE   = "events.jsonl"

    def __init__(self):
        self.base_dir = AI_OPS_BASE_DIR / "sessions"
        self.index_path = self.base_dir / self.INDEX_FILE
        
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

        self.__sessions: Dict[str, Session] = {}
        for session_id in self.__index.values():
            self.__sessions[session_id] = self.__load_session(session_id)
    
    def __load_messages(self, session_id: str) -> List[Message]:
        p = self.base_dir / session_id / self.MESSAGES_FILE
        if not p.exists():
            raise ValueError(f"No persistent session with uuid={session_id}")

        messages = []
        for raw_message in read_jsonl(file=p):
            message = Message.model_validate(raw_message)
            messages.append(message)

        return messages

    def __load_events(self, session_id: str) -> List[Event]:
        events_path = self.base_dir / session_id / self.EVENTS_FILE
        if not events_path.exists():
            raise ValueError(f"No persistent session with uuid={session_id}")

        try:
            return [
                _event_adapter.validate_python(_hydrate_tool_payload(raw)) 
                for raw in read_jsonl(events_path)
            ]
        except ValidationError:
            raise RuntimeError(f"Malformed event list at {events_path}")

    def __load_session(self, session_id: str) -> Session:
        short_id = None
        for _short_id, _session_id in self.__index.items():
            if _session_id == session_id:
                short_id = _short_id
                break

        messages = self.__load_messages(session_id)
        events = self.__load_events(session_id)

        return Session(short_id=short_id, uuid=session_id, messages=messages, events=events)

    def __update_index(self, short_id: int, session_id: str):
        # re-read from disk so concurrent stores don't clobber each other's entries,
        # then persist and mirror in-memory (matches the old JSONLConversationStore).
        with open(str(self.index_path), 'r') as fp:
            index = json.load(fp)

        index[str(short_id)] = session_id

        with open(str(self.index_path), 'w') as fp:
            json.dump(index, fp)

        self.__index[short_id] = session_id

    def create_session(self) -> Session:
        session_id = str(uuid.uuid4())
        short_id = self.__last_short_id + 1

        session_path = self.base_dir / session_id
        session_path.mkdir()
        (session_path / self.MESSAGES_FILE).touch()
        (session_path / self.EVENTS_FILE).touch()

        session = Session(uuid=session_id, short_id=short_id)
        self.__sessions[session_id] = session
        self.__last_short_id = short_id
        self.__update_index(short_id=short_id, session_id=session_id)
        return session

    def get_session_uuid(self, short_id: int) -> str:
        session_id = self.__index.get(short_id)
        if session_id is None:
            raise ValueError(f"No session with short_id={short_id}")
        return session_id

    def get_session_by_uuid(self, session_id: str) -> Session:
        session = self.__sessions.get(session_id)
        if session is None:
            raise ValueError(f"No session with uuid={session_id}")
        return session

    def append_message(self, session_id: str, message: Message) -> None:
        if session_id not in self.__sessions:
            raise ValueError(f"No session with uuid={session_id}")

        p = self.base_dir / session_id / self.MESSAGES_FILE
        append_jsonl(file=p, raw=message.model_dump_json())

        self.__sessions[session_id].messages.append(message)

    def append_event(self, session_id: str, event: Event) -> None:
        if session_id not in self.__sessions:
            raise ValueError(f"No session with uuid={session_id}")

        p = self.base_dir / session_id / self.EVENTS_FILE
        append_jsonl(file=p, raw=event.model_dump_json())

        self.__sessions[session_id].events.append(event)

    def get_messages_by_uuid(self, session_id: str) -> List[Message]:
        if session_id not in self.__sessions:
            raise ValueError(f"No session with uuid={session_id}")
        return self.__load_messages(session_id)

    def get_events_by_uuid(self, session_id: str) -> List[Event]:
        if session_id not in self.__sessions:
            raise ValueError(f"No session with uuid={session_id}")
        return self.__load_events(session_id)


class InMemorySessionStore(AbstractSessionStore):
    def __init__(self):
        self.__sessions: Dict[str, Session] = {}
        self.__short_id_idx: Dict[int, str] = {} # short_id -> uuid
        self.__last_short_id = 0

    def create_session(self) -> Session:
        session_id = str(uuid.uuid4())
        short_id = self.__last_short_id + 1

        session = Session(uuid=session_id, short_id=short_id)
        self.__sessions[session_id] = session
        self.__short_id_idx[short_id] = session_id
        self.__last_short_id = short_id
        return session

    def get_session_uuid(self, short_id: int) -> str:
        session_id = self.__short_id_idx.get(short_id)
        if session_id is None:
            raise ValueError(f"No session with short_id={short_id}")
        return session_id

    def get_session_by_uuid(self, session_id: str) -> Session:
        session = self.__sessions.get(session_id)
        if session is None:
            raise ValueError(f"No session with uuid={session_id}")
        return session

    def append_message(self, session_id: str, message: Message) -> None:
        self.get_session_by_uuid(session_id).messages.append(message)

    def append_event(self, session_id: str, event: Event) -> None:
        self.get_session_by_uuid(session_id).events.append(event)

    def get_messages_by_uuid(self, session_id: str) -> List[Message]:
        return self.get_session_by_uuid(session_id).messages

    def get_events_by_uuid(self, session_id: str) -> List[Event]:
        return self.get_session_by_uuid(session_id).events


class SessionStore:

    def __init__(self, store_cls: Type[AbstractSessionStore]):
        self._store = store_cls()

    def create_session(self) -> Session:
        return self._store.create_session()

    def get_session_uuid(self, short_id: int) -> str:
        return self._store.get_session_uuid(short_id)

    def get_session_by_uuid(self, session_id: str) -> Session:
        return self._store.get_session_by_uuid(session_id=session_id)

    def append_message(self, session_id: str, message: Message) -> None:
        self._store.append_message(session_id=session_id, message=message)

    def append_event(self, session_id: str, event: Event) -> None:
        self._store.append_event(session_id=session_id, event=event)

    def get_messages_by_uuid(self, session_id: str) -> List[Message]:
        return self._store.get_messages_by_uuid(session_id=session_id)

    def get_events_by_uuid(self, session_id: str) -> List[Event]:
        return self._store.get_events_by_uuid(session_id=session_id)


_SESSION_STORE_IMPL = {
    StorageStrategy.IN_MEMORY: InMemorySessionStore,
    StorageStrategy.JSONL: JSONLSessionStore
}
_SESSION_STORE: SessionStore | None = None


def get_session_store(strategy: StorageStrategy = StorageStrategy.JSONL) -> SessionStore:
    global _SESSION_STORE
    if _SESSION_STORE is None:
        _SESSION_STORE = SessionStore(store_cls=_SESSION_STORE_IMPL[strategy])
    return _SESSION_STORE