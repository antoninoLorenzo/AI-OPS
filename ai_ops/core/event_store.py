import abc
from enum import StrEnum, auto
from typing import List, Type

from pydantic import TypeAdapter, ValidationError

from ai_ops.config import AI_OPS_BASE_DIR
from ai_ops.core.schema import Event, EventType, AnyEvent
from ai_ops.core.conversation import StorageStrategy
from ai_ops.core.utils import read_jsonl, append_jsonl
from ai_ops.core.tools import resolve_args_type, resolve_result_type
from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)
_event_adapter = TypeAdapter(AnyEvent)


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


class AbstractEventStore(abc.ABC):
    
    @abc.abstractmethod
    def get_by_conversation_uuid(self, conversation_id: str) -> List[Event]:
        raise NotImplementedError()

    @abc.abstractmethod
    def append(self, conversation_id: str, event: Event) -> None:
        raise NotImplementedError()


class InMemoryEventStore(AbstractEventStore):

    def __init__(self):
        self._events: dict[str, List[Event]] = {}

    def get_by_conversation_uuid(self, conversation_id: str) -> List[Event]:
        return self._events.get(conversation_id, [])

    def append(self, conversation_id: str, event: Event) -> None:
        self._events.setdefault(conversation_id, []).append(event)


class JSONLEventStore(AbstractEventStore):
    EVENTS_FILE = "events.jsonl"

    def __init__(self):
        self.base_dir = AI_OPS_BASE_DIR / "conversations"

    def get_by_conversation_uuid(self, conversation_id: str) -> List[Event]:
        events_path = self.base_dir / conversation_id / self.EVENTS_FILE
        if not events_path.exists():
            return []

        try:
            return [
                _event_adapter.validate_python(_hydrate_tool_payload(raw)) 
                for raw in read_jsonl(events_path)
            ]
        except ValidationError:
            raise RuntimeError(f"Malformed event list at {events_path}")

    def append(self, conversation_id: str, event: Event) -> None:
        if not (self.base_dir / conversation_id).exists():
            raise ValueError(f"Conversation doesn't exists: {conversation_id}")

        events_path = self.base_dir / conversation_id / self.EVENTS_FILE
        append_jsonl(events_path, event.model_dump_json())


class EventStore:
    def __init__(self, store_cls: Type[AbstractEventStore]):
        self._store = store_cls()

    def get_by_conversation_uuid(self, conversation_id: str) -> List[Event]:
        return self._store.get_by_conversation_uuid(conversation_id=conversation_id)

    def append(self, conversation_id: str, event: Event) -> None:
        self._store.append(conversation_id=conversation_id, event=event)


_EVENT_STORE_IMPL = {
    StorageStrategy.IN_MEMORY: InMemoryEventStore,
    StorageStrategy.JSONL: JSONLEventStore
}
_EVENT_STORE: EventStore | None = None

def get_event_store(strategy: StorageStrategy = StorageStrategy.IN_MEMORY) -> EventStore:
    global _EVENT_STORE
    if _EVENT_STORE is None:
        _EVENT_STORE = EventStore(store_cls=_EVENT_STORE_IMPL[strategy])
    return _EVENT_STORE