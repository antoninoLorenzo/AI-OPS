# Client sees this types, the good question is whether a custom schema makes sense 
# at all. It kind of seems like I did an attempt at avoiding OpenAI format and build 
# my own.
import abc
from enum import StrEnum, auto
from typing import List, Type, Literal, ClassVar, Optional, Type

from pydantic import BaseModel
    

class AgentMode(StrEnum):
    SUPERVISED = auto()
    UNSUPERVISED = auto()


class EventType(StrEnum):
    USER_MESSAGE = auto()
    TEXT = auto()
    REASONING = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    STOP = auto()
    TOOL_ERROR = auto()


# Notes on pydantic:
# `Event` could be a BaseModel itself and discriminate by type, this would 
# allow pydantic to serialize types directly into the subclass. To do so 
# `kind` should become a Literal[EventType] always set to text.

class Event(abc.ABC):
    kind: EventType


class UserMessageEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.USER_MESSAGE
    content: str


class TextEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.TEXT
    chunk: str
    stream: bool = False
    stream_done: bool = False


class ReasoningEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.REASONING
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
    error: Optional[str] = None # fatal error


class ToolErrorFailure(StrEnum):
    VALIDATION_ERROR = auto()
    EXECUTION_ERROR = auto()


class ToolErrorEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.TOOL_ERROR
    failure: ToolErrorFailure
    tool_call_id: str # should rename to `call_id`
    name: str
    error: str

