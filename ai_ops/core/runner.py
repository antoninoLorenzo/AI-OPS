from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple, Type

import litellm
from litellm import (
    ChatCompletionSystemMessage,
    ChatCompletionToolMessage,
    ChatCompletionUserMessage,
)

from ai_ops.core.agent import DEFAULT_TEMPERATURE, orchestrator
from ai_ops.core.context_management import ContextView, RawContextView
from ai_ops.core.conversation import Message, get_conversation_store, get_token_count
from ai_ops.core.llm import InferenceClient, ModelConfig
from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core.prompt import build_prompt
from ai_ops.core.schema import (
    AgentMode,
    Event,
    ReasoningEvent,
    StopEvent,
    TextEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
    UserMessageEvent,
)
from ai_ops.core.tools import (
    CommandAdmissionPolicy,
    LoadSkill,
    Tool,
    ToolContext,
    ToolRegistry,
    WhiteboardRead,
    get_skill_registry,
    get_whiteboard_store,
)

_logger = get_logger(__name__)


@dataclass
class AgentConfig:
    tools: List[Type[Tool]] = field(default_factory=list)
    context_fn: ContextView = RawContextView()
    working_directory: str | None = None # TODO: this shouldn't be configurable
    command_policies: Tuple[CommandAdmissionPolicy] = field(default_factory=tuple)
    temperature: float = DEFAULT_TEMPERATURE
    prompt_extension: str | None = None


class AgentRunner:
    """`AgentRunner` separates the client from the orchestrator implementation.

    It's responsibilities are initializing the tool instances, persisting the
    conversation (both falling in state management) and routing the events to 
    the client.

    The reason to separate the client from the agent implementation is to allow 
    changes in the agent implementation without directly affecting the client 
    code; however the runner implementation is as stable as the event taxonomy 
    defined in `ai_ops.core.schema`.
    """
    def __init__(
        self,
        conversation_id: str,
        client: InferenceClient,
        config: AgentConfig,
        is_new_conversation: bool = True,
        extra_tool_ctx: Optional[Dict[str, Any]] = None
    ):
        self.agent_config = config
        self.conversation_id = conversation_id
        self.client = client
        self.context_fn = config.context_fn
        self._conversation_store = get_conversation_store()
        
        # build_prompt will load the prompt variant for the specific model if available 
        # otherwise it loads the default ones.
        system_prompt = build_prompt(model=client.model, prompt_extension=config.prompt_extension)
        system_prompt_message = ChatCompletionSystemMessage(role='system', content=system_prompt)
        system_prompt_tokens = get_token_count(system_prompt_message)

        self._conversation_store.append(
            conversation_id=self.conversation_id,
            message=Message(message=system_prompt_message, token_count=system_prompt_tokens)
        )
        
        ctx = ToolContext(
            conversation_id=conversation_id, 
            model_id=client.model,
            is_new_conversation=is_new_conversation,
            working_directory=config.working_directory,
            command_policies=config.command_policies,
            extra=extra_tool_ctx
        )
        self.tools = {
            tool.name: factory(ctx)
            for tool in config.tools
            if (factory := ToolRegistry.get(tool.name)) is not None
        }
        self._user_stopped = False
    
    def run(
        self, 
        user_message: UserMessageEvent,
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: Optional[int] = None
    ) -> Iterator[Event]:
        self._append_user_message(user_message.content)

        conversation = self._conversation_store.get_by_uuid(conversation_id=self.conversation_id)

        total_event_count = 0
        event_stream = orchestrator(
            client=self.client,
            conversation=conversation,
            tools=self.tools,
            context_fn=self.context_fn,
            mode=mode,
            max_iterations=max_iterations,
            temperature=self.agent_config.temperature
        )

        # TODO refactor: we only get ValueError if the message list is malformed
        try:
            for event in event_stream:
                total_event_count += 1
                if isinstance(event, Message):
                    # this currently handles non-streaming
                    text_content = event.message.get("content")
                    reasoning_content = event.message.get("reasoning_content")

                    if not event.internal:
                        if reasoning_content is not None and isinstance(reasoning_content, str):
                            yield ReasoningEvent(chunk=reasoning_content)

                        if text_content is not None and isinstance(text_content, str):
                            yield TextEvent(chunk=text_content)

                    self._conversation_store.append(conversation_id=self.conversation_id, message=event)
                elif isinstance(event, ToolResultEvent):
                    # the orchestrator validates tool calls so we can be sure this doesn't raise
                    tool = self.tools[event.name] 
                    # format_result is required to return a string, if different we get ValueError
                    tool_content = tool.format_result(event.result)
                    
                    yield event
                    
                    tool_message = ChatCompletionToolMessage(
                        role="tool",
                        content=tool_content,
                        tool_call_id=event.call_id
                    )
                    self._conversation_store.append(
                        conversation_id=self.conversation_id, 
                        message=Message(
                            message=tool_message,
                            token_count=get_token_count(tool_message)
                        )
                    )
                elif isinstance(event, (ToolCallEvent, ToolErrorEvent, StopEvent)):
                    yield event

                if self._user_stopped:
                    break
        except Exception as fatal:
            log_event(_logger, logging.ERROR, "Fatal error in agent loop", error=f"\"{fatal}\"")
            yield StopEvent(
                issuer="agent",
                error=str(fatal)
            )

        log_event(
            _logger, logging.INFO, "", 
            conversation_id=self.conversation_id, 
            total_event_count=total_event_count
        )
   

    def send(self, user_event: UserMessageEvent):
        self._append_user_message(user_event.content)

    def stop(self, stop_event: StopEvent):
        # non-preemptive
        self._user_stopped = True

    def _append_user_message(self, content: str):
        self._conversation_store.append(
            conversation_id=self.conversation_id,
            message=Message(
                message=ChatCompletionUserMessage(role="user", content=content),
                # token_count=litellm.token_counter(text=content)
            )
        )
