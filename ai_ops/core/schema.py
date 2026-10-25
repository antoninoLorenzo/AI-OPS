import time
from collections.abc import Awaitable, Callable
from enum import StrEnum, auto
from typing import Annotated, Literal

from litellm import ModelResponse
from pydantic import BaseModel, Field, SerializeAsAny, TypeAdapter


class AgentMode(StrEnum):
    SUPERVISED = auto()
    UNSUPERVISED = auto()


class EventType(StrEnum):
    USER_MESSAGE = auto()
    CHAT_COMPLETION = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    TOOL_ERROR = auto()
    TOOL_CONFIRMATION = auto()
    STOP = auto()


class Event(BaseModel):
    kind: EventType
    session_id: str
    timestamp: int = Field(default_factory=lambda: int(time.time()))


class UserMessageEvent(Event):
    kind: Literal[EventType.USER_MESSAGE] = EventType.USER_MESSAGE
    content: str


class Usage(BaseModel):
    prompt_tokens: int 
    completion_tokens: int 
    reasoning_tokens: int = 0
    cached_tokens: int = 0


# note: to eventually handle streaming make a new volatile event without touching 
# this one, so that we store only full completion but we get to stream the deltas.
class ChatCompletionEvent(Event):
    kind: Literal[EventType.CHAT_COMPLETION] = EventType.CHAT_COMPLETION
    response_id: str
    message: dict
    # usage-tracking isn't required for the agent to work so having it optional is 
    # defensive against provider-dependent or litellm issues. 
    usage: Usage | None = None 
    
    @classmethod
    def from_model_response(
        cls, 
        session_id: str, 
        response: ModelResponse
    ) -> "ChatCompletionEvent":
        usage = None
        try:
            if getattr(response, "usage", None) is None:
                raise ValueError()

            _usage = response.usage
            if _usage.prompt_tokens is None or _usage.completion_tokens is None: 
                raise ValueError()

            reasoning_tokens = 0
            if _usage.completion_tokens_details is not None \
                    and _usage.completion_tokens_details.reasoning_tokens is not None:
                reasoning_tokens = _usage.completion_tokens_details.reasoning_tokens

            cached_tokens = 0
            if _usage.prompt_tokens_details is not None \
                    and _usage.prompt_tokens_details.cached_tokens is not None:
                cached_tokens = _usage.prompt_tokens_details.cached_tokens

            usage = Usage(
                prompt_tokens=_usage.prompt_tokens,
                completion_tokens=_usage.completion_tokens,
                reasoning_tokens=reasoning_tokens,
                cached_tokens=cached_tokens
            )
        except Exception:
            usage = None

        return ChatCompletionEvent(
            session_id=session_id,
            response_id=response.id,
            message=response.choices[0].message.model_dump(),
            usage=usage
        )


class SummaryRecord(BaseModel):
    """
    A summarization-compaction result together with the fold boundary it covers.
    Persisted per session so the extra summarization call is accounted for in costs
    and so the compaction state can be recovered on resume.
    """
    event: ChatCompletionEvent
    boundary: int
    """
    Number of leading session messages folded into `event` (i.e. `len(session.messages)`
    when the summary was generated). Messages `[0:boundary]` are represented by the
    summary; `[boundary:]` is the still-verbatim tail.
    """


# Tool serialization/deserialization depends on the schema of the tool implementation,
# at serialization time we can use SerializeAsAny; at deserialization time we need to 
# resolve the schema and that can be done through the core.tools.ToolRegistry, however 
# to keep everything in one place and avoid circular imports the resolve function is 
# injected. 
ToolParameters = SerializeAsAny[BaseModel]
ToolResult = SerializeAsAny[BaseModel]
ResolveToolModelFn = Callable[[str], type[BaseModel] | None] 

class ToolCallEvent(Event):
    kind: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    call_id: str
    name: str
    args: ToolParameters
    requires_confirmation: bool = False
    """
    True when the agent executes in `AgentMode.SUPERVISED` and a tool call is blocked,  
    clients should reply with a `ToolConfirmationEvent` otherwise execution is denied 
    on timeout.
    """

class ToolConfirmationEvent(Event):
    """
    Issued by client when a `ToolCallEvent` has `requires_confirmation` set to True.
    """
    kind: Literal[EventType.TOOL_CONFIRMATION] = EventType.TOOL_CONFIRMATION
    call_id: str
    approved: bool


# Awaited by `agent_loop` to obtain the user's decision for a confirmation
# request. It's injected (the agent loop stays stateless): the caller owns the
# pending-decision state and the await/timeout policy. Returns `True` to execute.
ConfirmCallback = Callable[[ToolCallEvent], Awaitable[bool]]


class ToolResultEvent(Event):
    kind: Literal[EventType.TOOL_RESULT] = EventType.TOOL_RESULT
    call_id: str
    name: str
    args: ToolParameters
    result: ToolResult


class StopEvent(Event):
    kind: Literal[EventType.STOP] = EventType.STOP
    issuer: Literal['agent', 'user']
    reason: str | None = None
    max_iteration: bool = False
    error: str | None = None # fatal error
    call_id: str | None = None # tool_call_id when the stop was issued via the stop tool


class ToolErrorFailure(StrEnum):
    VALIDATION_ERROR = auto()
    EXECUTION_ERROR = auto()


class ToolErrorEvent(Event):
    kind: Literal[EventType.TOOL_ERROR] = EventType.TOOL_ERROR
    failure: ToolErrorFailure
    call_id: str
    name: str
    error: str


# Discriminated union of every concrete event, keyed by `kind` for deserialization
# of a streamed/persisted event back into its concrete type.
AnyEvent = Annotated[
    UserMessageEvent | ChatCompletionEvent 
    | ToolCallEvent | ToolConfirmationEvent 
    | ToolResultEvent | ToolErrorEvent
    | StopEvent,
    Field(discriminator="kind"),
]

_EventAdapter = TypeAdapter(AnyEvent)


def deserialize_events(
    raw_events: list[dict], 
    resolve_tool_args_model: ResolveToolModelFn,
    resolve_tool_result_model: ResolveToolModelFn
) -> list[Event]:
    """
    :raises ValidationError: 
        an event couldn't be deserialized with `_EventAdapter` (event schema mismatch) 
        or during `ToolCallEvent`/`ToolResultEvent` deserialization the specific tool 
        deserialization failed (tool schema mismatch).
    :raises ValueError: 
        during `ToolCallEvent`/`ToolResultEvent` deserialization if a tool with 
        corresponding name is not available in `ToolRegistry`.
    """
    return [
        _EventAdapter.validate_python(_hydrate_tool(
            raw_event=raw, 
            resolve_tool_args_model=resolve_tool_args_model,
            resolve_tool_result_model=resolve_tool_result_model
        )) 
        for raw in raw_events
    ]


def _hydrate_tool(
    raw_event: dict,
    resolve_tool_args_model: ResolveToolModelFn,
    resolve_tool_result_model: ResolveToolModelFn
) -> dict:
    kind = raw_event["kind"]
    if kind not in (EventType.TOOL_CALL, EventType.TOOL_RESULT):
        return raw_event
    
    name, raw_args = raw_event["name"], raw_event["args"]
    args_model = resolve_tool_args_model(name)
    if args_model is None:
        raise ValueError(f"Failed event deserialization: no model found for tool \"{name}\"")
    
    raw_event["args"] = args_model.model_validate(raw_args)

    if kind != EventType.TOOL_RESULT:
        return raw_event

    raw_result = raw_event["result"]
    result_model = resolve_tool_result_model(name)
    if result_model is None:
        raise ValueError(f"Failed event deserialization: no model found for tool \"{name}\"")

    
    raw_event["result"] = result_model.model_validate(raw_result)
    return raw_event

