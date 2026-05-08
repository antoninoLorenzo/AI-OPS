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
    REASONING = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    STOP = auto()
    TOOL_ERROR = auto()


class Event(abc.ABC):
    kind: EventType


class UserMessageEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.USER_MESSAGE
    content: str


class TextEvent(Event, BaseModel):
    kind: ClassVar[EventType] = EventType.TEXT
    chunk: str


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
    tool_call_id: str
    name: str
    error: str

