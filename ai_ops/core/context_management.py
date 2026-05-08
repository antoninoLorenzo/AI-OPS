import copy
from typing import List, Protocol, runtime_checkable

from ai_ops.core.conversation import Message


@runtime_checkable
class ContextView(Protocol):
    """
    `Conversation` is an append-only record, `ContextView` exists to give the 
    LLM a compressed or potentially modified subset of the messages.
    Keeping the conversation history and the context given to the LLM separate 
    allows the orchestrator to inject ephemeral context (ex. mutable indexes) 
    in the model context window without bloating the conversation history.

    Implementations should return a deep copy of the selected messages.

    > Note: deep copying is accettable, memory-wise, under the assumption that 
    messages contain only text, however that wouldn't really be great if the 
    conversation (following OpenAI format) contained base64 encoded binary blobs.
    """

    def __call__(self, messages: List[Message]) -> List[Message]:
        pass


def raw_context_view(messages: List[Message]) -> List[Message]:
    return copy.deepcopy(messages)
