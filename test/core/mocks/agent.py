from typing import AsyncIterator, Dict, Iterator, Optional, Sequence

from litellm import (
    ChatCompletionAssistantMessage,
    ChatCompletionToolMessage,
)

from ai_ops.core.schema import (
    AgentMode, 
    Event,
    ToolCallEvent,
    ToolResultEvent,
    StopEvent
)
from ai_ops.core.llm import InferenceClient
from ai_ops.core.tools import Tool
from ai_ops.core.conversation import Message
from ai_ops.core.storage import Session
from ai_ops.core.context_management import ContextTransform


def mock_orchestrator(
    client: InferenceClient,
    session: Session,
    tools: Dict[str, Tool],
    context_transforms: list[ContextTransform] | None = None,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: Optional[int] = None,
    mock_events: Sequence[Message | Event] | Exception | None = None,
    **kwargs
) -> Iterator[Message | Event]:
    if isinstance(mock_events, Sequence):
        for event in mock_events:
            yield event
    elif isinstance(mock_events, Exception):
        yield StopEvent(issuer="agent", error=str(mock_events))


async def mock_aorchestrator(
    client: InferenceClient,
    session: Session,
    tools: Dict[str, Tool],
    context_transforms: list[ContextTransform] | None = None,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: Optional[int] = None,
    mock_events: Sequence[Message | Event] | Exception | None = None,
    **kwargs
) -> AsyncIterator[Message | Event]:
    if isinstance(mock_events, Sequence):
        for event in mock_events:
            yield event
    elif isinstance(mock_events, Exception):
        yield StopEvent(issuer="agent", error=str(mock_events))

