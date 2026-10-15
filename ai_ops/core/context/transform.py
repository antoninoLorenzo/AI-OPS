import abc
from enum import StrEnum

from pydantic import BaseModel, Field

from ai_ops.core.conversation import (
    Message,
    is_valid_context,
)
from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)


class ContextTransformType(StrEnum):
    CHECKPOINT = "checkpoint"
    REASONING  = "reasoning"
    TERMINAL   = "terminal"


class EmptyTransformConfig(BaseModel):
    """Placeholder for transforms that take no configuration."""


class ContextTransformSettings(BaseModel):
    kind: ContextTransformType
    config: BaseModel = Field(default_factory=EmptyTransformConfig)
    """Initialization parameters for a concrete transform."""


DEFAULT_CONTEXT_TRANSFORMS = [
    ContextTransformSettings(kind=ContextTransformType.CHECKPOINT)
]


class ContextTransform(abc.ABC):
    requires_state: bool = False
    """True if the transform needs agent state (currently only tools) at initialization time."""

    @abc.abstractmethod
    def __call__(self, messages: list[Message]) -> list[Message]:
        """
        :param messages: list of chat completion compliant messages.
        :returns: a modified deep copy of the original message list.
        """
        raise NotImplementedError()
    
    @classmethod
    @abc.abstractmethod
    def config_schema(cls) -> type[BaseModel] | None:
        """
        :returns: __init__ parameters schema for concrete transforms or None.
        """
        raise NotImplementedError()


def build_context(
    messages: list[Message],
    context_transforms: list[ContextTransform] | None = None
) -> list[Message]:
    if context_transforms is None:
        context_transforms = []
        
    valid, err = is_valid_context(messages)
    if not valid:
        raise ValueError(f"Received invalid message list: {err}")

    context = messages
    for transform in context_transforms:
        _messages = transform(messages=context)
        valid, err = is_valid_context(_messages)
        if not valid:
            log_event(
                _logger, logging.WARNING, "Skipping invalid malformed transform", 
                context_view=type(transform).__name__, error=err
            )
        else:
            context = _messages
            
    return context
