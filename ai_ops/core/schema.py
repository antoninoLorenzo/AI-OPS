# client sees this types
import abc
from enum import StrEnum, auto
from typing import List, Type, Literal, ClassVar, Optional
from dataclasses import dataclass, field

from pydantic import BaseModel

from ai_ops.core.tools import Tool
from ai_ops.core.context_management import ContextView, raw_context_view


@dataclass
class AgentConfig:
    tools: List[Type[Tool]] = field(default_factory=list)
    context_fn: ContextView = raw_context_view
    system_prompt: Optional[str] = None
    

class AgentMode(StrEnum):
    SUPERVISED = auto()
    UNSUPERVISED = auto()


class EventType(StrEnum):
    USER_MESSAGE = auto()
    TEXT = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    STOP = auto()


# do I need to differentiate between client/agent events? for example stop can be both client/agent.
# if yes, is it done though an issuer field? That would assume an event like ToolCall can be issued by a client.
# events should be communication channel agnostic, yielded by agent runner, sent by client, can be in process or on 
# top of http (or tcp, even though why would I use tcp? are other protocols an option, such as some rpc protocol?).


class Event(abc.ABC):
    kind: EventType

class UserMessageEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.USER_MESSAGE
    content: str


class TextEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.TEXT
    chunk: str


class ToolCallEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.TOOL_CALL
    call_id: str
    name: str
    args: BaseModel 


class ToolResultEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.TOOL_RESULT
    call_id: str
    name: str
    args: BaseModel
    result: BaseModel


class StopEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.STOP
    issuer: Literal['agent', 'user']
    reason: Optional[str] = None
    max_iteration: bool = False
