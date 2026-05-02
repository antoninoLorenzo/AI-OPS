from typing import List, Protocol, runtime_checkable

from ai_ops.core.conversation import Message


@runtime_checkable
class ContextView(Protocol):
    def __call__(self, messages: List[Message]) -> List[Message]:
        pass


def raw_context_view(messages: List[Message]) -> List[Message]:
    return messages
