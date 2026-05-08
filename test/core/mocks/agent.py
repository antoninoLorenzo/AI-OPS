from typing import Dict, Iterator, Optional, Sequence

from litellm import (
    ChatCompletionAssistantMessage,
    ChatCompletionToolMessage,
)

from ai_ops.core.schema import (
    AgentMode, 
    Event,
    ToolCallEvent,
    ToolResultEvent
)
from ai_ops.core.llm import InferenceClient
from ai_ops.core.tools import Tool
from ai_ops.core.conversation import Conversation, Message
from ai_ops.core.context_management import ContextView


def mock_orchestrator(
    client: InferenceClient,
    conversation: Conversation,
    tools: Dict[str, Tool],
    context_fn: ContextView,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: Optional[int] = None,
    mock_events: Sequence[Message | Event] | Exception | None = None 
) -> Iterator[Message | Event]:
    if isinstance(mock_events, Sequence):
        for event in mock_events:
            yield event
    elif isinstance(mock_events, Exception):
        raise mock_events

