import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple, Type

import litellm
from litellm import (
    ChatCompletionSystemMessage,
    ChatCompletionToolMessage,
    ChatCompletionUserMessage,
)

from ai_ops.core.agent import _AGENT_TEMPERATURE, aorchestrator, orchestrator
from ai_ops.core.context_management import ContextView, RawContextView
from ai_ops.core.conversation import (
    Conversation, 
    Message, 
    get_conversation_store, 
    get_token_count, 
    is_valid_message_list
)
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
    ToolConfirmationEvent,
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
from ai_ops.config import CONFIRMATION_TIMEOUT_S

_logger = get_logger(__name__)


@dataclass
class AgentConfig:
    tools: List[Type[Tool]] = field(default_factory=list)
    context_fn: ContextView = RawContextView()
    working_directory: str | None = None # TODO: this shouldn't be configurable
    command_policies: Tuple[CommandAdmissionPolicy] = field(default_factory=tuple)
    temperature: float = _AGENT_TEMPERATURE
    prompt_extension: str | None = None
    confirmation_timeout_s: float = CONFIRMATION_TIMEOUT_S


class AgentRunner:
    """
    `AgentRunner` separates the client from the orchestrator implementation.
    It holds the agent state for a given conversation.
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
        
        if is_new_conversation:
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

        # guards run from being invoked when it already was
        self._running = False
        # guards send from being invoked if a user message isn't processed yet
        self._send_lock = False
        # stop flag, non-preemptive
        self._user_stopped = False
        # pending tool confirmation keyed by tool call id
        self._confirmations: Dict[str, asyncio.Future] = {}
        # list of blocked tool call ids to verify one actually exists (prevent 
        # creation of confirmation futures that will never be resolved).
        self._blocked_calls = []
    
    @property
    def running(self):
        return self._running

    def run(
        self, 
        user_message: UserMessageEvent,
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: Optional[int] = None
    ) -> Iterator[Event]:
        """
        :raises `ValueError`: Invalid conversation format. Expected [system, user, ...] message list.
        """
        self._append_user_message(user_message.content)

        conversation = self._conversation_store.get_by_uuid(conversation_id=self.conversation_id)
        if not is_valid_message_list(conversation.messages):
            raise ValueError(f"Invalid conversation. Expected [system, user, ...] message list.")

        return self.__run_impl(conversation=conversation, mode=mode, max_iterations=max_iterations)

    def __run_impl(
        self, 
        conversation: Conversation, 
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: Optional[int] = None
    ) -> Iterator[Event]:
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
        
        log_event(
            _logger, logging.INFO, "",
            conversation_id=self.conversation_id,
            total_event_count=total_event_count
        )

    def arun(
        self,
        user_message: UserMessageEvent,
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: Optional[int] = None
    ) -> AsyncIterator[Event]:
        """
        :raises `RuntimeError`: Already running.
        :raises `ValueError`: Invalid conversation format. Expected [system, user, ...] message list.
        """
        if self._running:
            raise RuntimeError(f"Already running")

        self._append_user_message(user_message.content)
        conversation = self._conversation_store.get_by_uuid(conversation_id=self.conversation_id)
        if not is_valid_message_list(conversation.messages):
            raise ValueError(f"Invalid conversation. Expected [system, user, ...] message list.")
        
        self._running = True
        return self.__arun_impl(conversation=conversation, mode=mode, max_iterations=max_iterations)

    async def __arun_impl(
        self,
        conversation: Conversation, 
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: Optional[int] = None
    ) -> AsyncIterator[Event]:
        total_event_count = 0
        event_stream = aorchestrator(
            client=self.client,
            conversation=conversation,
            tools=self.tools,
            context_fn=self.context_fn,
            mode=mode,
            max_iterations=max_iterations,
            temperature=self.agent_config.temperature,
            confirm=self._confirm
        )

        
        async for event in event_stream:
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
            elif isinstance(event, ToolCallEvent):
                if event.requires_confirmation:
                    self._blocked_calls.append(event.call_id)
                
                yield event
            elif isinstance(event, (ToolErrorEvent, StopEvent)):
                yield event

            self._send_lock = False

            if self._user_stopped:
                break
        
        self._running = False
        log_event(
            _logger, logging.INFO, "",
            conversation_id=self.conversation_id,
            total_event_count=total_event_count
        )

    def send(self, user_event: UserMessageEvent) -> bool:
        """
        Enqueue a message in the conversation, the agent processes it after the current 
        event completes it's execution.

        :returns: True if the message is enqueued, False otherwise.
        """
        if self._running and not self._send_lock:
            self._append_user_message(user_event.content)
            self._send_lock = True
            return True
        return False

    def stop(self):
        """
        Stop agent execution after the current event is completed (ex. tool execution).
        """
        self._user_stopped = True

    def confirm(self, confirmation: ToolConfirmationEvent):
        """
        Confirm a tool call that was blocked in supervised mode (`AgentMode.SUPERVISED`).

        :raises `RuntimeError`: `tool_call_id` doesn't match any existing blocked call.
        """
        # prevent confirmation for non-existing blocked call or already confirmed call
        if not confirmation.call_id in self._blocked_calls:
            raise RuntimeError(f"No tool call with tool_call_id={confirmation.call_id}")

        future = self._get_confirmation_future(confirmation.call_id)
        if not future.done():
            future.set_result(confirmation.approved)

    async def _confirm(self, tool_call: ToolCallEvent) -> bool:
        # this is what gets awaited within `aorchestrator`
        future = self._get_confirmation_future(tool_call.call_id)
        try:
            approved = await asyncio.wait_for(
                future, timeout=self.agent_config.confirmation_timeout_s
            )
        except asyncio.TimeoutError:
            log_event(
                _logger, logging.WARNING, "Tool confirmation timed out",
                conversation_id=self.conversation_id, call_id=tool_call.call_id
            )
            approved = False
        finally:
            self._confirmations.pop(tool_call.call_id, None)
            self._blocked_calls.remove(tool_call.call_id)
        return approved

    def _get_confirmation_future(self, call_id: str) -> asyncio.Future:
        future = self._confirmations.get(call_id)
        if future is None:
            future = asyncio.get_event_loop().create_future()
            self._confirmations[call_id] = future
        return future

    def _append_user_message(self, content: str):
        self._conversation_store.append(
            conversation_id=self.conversation_id,
            message=Message(
                message=ChatCompletionUserMessage(role="user", content=content),
                # token_count=litellm.token_counter(text=content)
            )
        )
