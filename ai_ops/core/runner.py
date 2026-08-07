import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

from ai_ops.config import BASE_AGENT_ID, CONFIRMATION_TIMEOUT_S
from ai_ops.core.agent import _AGENT_TEMPERATURE, aorchestrator, orchestrator
from ai_ops.core.context_management import ContextView, RawContextView
from ai_ops.core.conversation import Message, get_token_count, is_valid_message_list
from ai_ops.core.llm import InferenceClient
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
from ai_ops.core.storage import Session, get_session_store
from ai_ops.core.tools import (
    CommandAdmissionPolicy,
    Tool,
    ToolContext,
    ToolRegistry,
    WhiteboardRead,
    WhiteboardWrite,
    replay_whiteboard,
)

_logger = get_logger(__name__)


@dataclass
class AgentConfig:
    agent_id: str = BASE_AGENT_ID
    """Agent identifier. Has to be a valid prompt id in the registry (see `ai_ops.core.prompt`)."""

    temperature: float = _AGENT_TEMPERATURE
    
    tools: list[type[Tool]] = field(default_factory=list)
    """Agent tools, classes not instances."""

    confirmation_timeout_s: float = CONFIRMATION_TIMEOUT_S
    """Time before the execution of tool that requires confirmation is automatically denied."""

    context_fn: ContextView = field(default_factory=RawContextView)
    """Context compaction strategy (ex. `LayeredContextView`). Defaults to `RawContextView`."""

    command_policies: tuple[CommandAdmissionPolicy] = field(default_factory=tuple)
    """Only applies if `Terminal` tool is supplied."""

    prompt_extension: str | None = None
    """Optional instructions appended to the system prompt (useful for benchmarks)."""


class AgentRunner:
    """
    `AgentRunner` separates the client from the orchestrator implementation.
    It holds the agent state for a given conversation.
    """
    def __init__(
        self,
        session_id: str,
        client: InferenceClient,
        config: AgentConfig,
        is_new_conversation: bool = True,
        extra_tool_ctx: dict[str, Any] | None = None
    ):
        self.agent_config = config
        self.session_id = session_id
        self.client = client
        self.context_fn = config.context_fn
        self._store = get_session_store()

        if is_new_conversation:
            system_prompt = build_prompt(
                agent_id=config.agent_id,
                model=client.model,
                prompt_extension=config.prompt_extension
            )
            system_prompt_message = {"role": "system", "content": system_prompt}
            system_prompt_tokens = get_token_count(system_prompt_message)
            self._store.append_message(
                session_id=self.session_id,
                message=Message(message=system_prompt_message, token_count=system_prompt_tokens, agent_id=config.agent_id)
            )
        elif any(t in config.tools for t in (WhiteboardWrite, WhiteboardRead)):
            # rebuild the whiteboard from session events on resume
            replay_whiteboard(
                whiteboard_id=self.session_id,
                events=self._store.get_events_by_uuid(session_id=self.session_id)
            )

        ctx = ToolContext(
            session_id=session_id, 
            model_id=client.model,
            is_new_conversation=is_new_conversation,
            command_policies=config.command_policies,
            extra=extra_tool_ctx
        )
        self.tools = {
            tool.name: spec.factory(ctx)
            for tool in config.tools
            if (spec := ToolRegistry.get(tool.name)) is not None
        }

        # guards run from being invoked when it already was
        self._running = False
        # stop flag, non-preemptive
        self._user_stopped = False
        # pending tool confirmation keyed by tool call id
        self._confirmations: dict[str, asyncio.Future] = {}
        # list of blocked tool call ids to verify one actually exists (prevent 
        # creation of confirmation futures that will never be resolved).
        self._blocked_calls = []
        # when send is called the user message is temporarily set as pending until 
        # there are no pending tool calls, that is required because an assistant 
        # message with tool calls has to be followed with tool messages corresponding 
        # to them.
        # https://joseferben.com/posts/openai-tool-calls-must-be-followed-by-tool-messages/
        self._pending_message: UserMessageEvent | None = None
        self._pending_tool_calls = 0
    
    @property
    def running(self):
        return self._running

    def run(
        self, 
        user_message: UserMessageEvent,
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: int | None = None
    ) -> Iterator[Event]:
        """
        :raises `ValueError`: Invalid conversation format. Expected [system, user, ...] message list.
        """
        self._append_user_message(user_message.content)

        session = self._store.get_session_by_uuid(session_id=self.session_id)
        if not is_valid_message_list(session.messages):
            raise ValueError("Invalid conversation. Expected [system, user, ...] message list.")

        return self.__run_impl(session=session, mode=mode, max_iterations=max_iterations)

    def __run_impl(
        self,
        session: Session,
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: int | None = None
    ) -> Iterator[Event]:
        total_event_count = 0
        event_stream = orchestrator(
            client=self.client,
            session=session,
            tools=self.tools,
            context_fn=self.context_fn,
            mode=mode,
            max_iterations=max_iterations,
            temperature=self.agent_config.temperature,
            agent_id=self.agent_config.agent_id
        )
        
        for event in event_stream:
            total_event_count += 1
            if isinstance(event, Message):
                # this currently handles non-streaming
                text_content = event.message.get("content")
                reasoning_content = event.message.get("reasoning_content")

                if reasoning_content is not None and isinstance(reasoning_content, str):
                    yield ReasoningEvent(chunk=reasoning_content)

                if text_content is not None and isinstance(text_content, str):
                    yield TextEvent(chunk=text_content)

                self._store.append_message(session_id=self.session_id, message=event)
            elif isinstance(event, ToolResultEvent):
                yield event
                self._store.append_message(
                    session_id=self.session_id,
                    message=self._tool_result_to_message(event)
                )
            elif isinstance(event, ToolErrorEvent):
                yield event
                self._store.append_message(
                    session_id=self.session_id,
                    message=self._tool_error_to_message(event)
                )
            elif isinstance(event, (ToolCallEvent, StopEvent)):
                yield event

            if self._user_stopped:
                break
        
        log_event(
            _logger, logging.INFO, "",
            session_id=self.session_id,
            total_event_count=total_event_count
        )

    def arun(
        self,
        user_message: UserMessageEvent,
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: int | None = None
    ) -> AsyncIterator[Event]:
        """
        :raises `RuntimeError`: Already running.
        :raises `ValueError`: Invalid conversation format. Expected [system, user, ...] message list.
        """
        if self._running:
            raise RuntimeError("Already running")

        self._append_user_message(user_message.content)
        session = self._store.get_session_by_uuid(session_id=self.session_id)
        if not is_valid_message_list(session.messages):
            raise ValueError("Invalid conversation. Expected [system, user, ...] message list.")

        self._running = True
        return self.__arun_impl(session=session, mode=mode, max_iterations=max_iterations)

    async def __arun_impl(
        self,
        session: Session,
        mode: AgentMode = AgentMode.SUPERVISED,
        max_iterations: int | None = None
    ) -> AsyncIterator[Event]:
        total_event_count = 0

        while True:
            should_continue = False
            event_stream = aorchestrator(
                client=self.client,
                session=session,
                tools=self.tools,
                context_fn=self.context_fn,
                mode=mode,
                max_iterations=max_iterations,
                temperature=self.agent_config.temperature,
                confirm=self._confirm,
                agent_id=self.agent_config.agent_id
            )

            async for event in event_stream:
                total_event_count += 1
                if isinstance(event, Message):
                    # this currently handles non-streaming
                    text_content = event.message.get("content")
                    reasoning_content = event.message.get("reasoning_content")

                    if reasoning_content is not None and isinstance(reasoning_content, str):
                        reasoning_event = ReasoningEvent(chunk=reasoning_content)
                        yield reasoning_event
                        self._store.append_event(session_id=self.session_id, event=reasoning_event)

                    if text_content is not None and isinstance(text_content, str):
                        txt_event = TextEvent(chunk=text_content)
                        yield txt_event
                        self._store.append_event(session_id=self.session_id, event=txt_event)

                    tool_calls = event.message.get("tool_calls") or []
                    self._pending_tool_calls = len(tool_calls)

                    self._store.append_message(session_id=self.session_id, message=event)
                elif isinstance(event, ToolCallEvent):
                    if event.requires_confirmation:
                        self._blocked_calls.append(event.call_id)
                    
                    yield event
                    self._store.append_event(session_id=self.session_id, event=event)
                elif isinstance(event, ToolResultEvent):
                    yield event

                    self._store.append_message(
                        session_id=self.session_id,
                        message=self._tool_result_to_message(event)
                    )
                    self._store.append_event(session_id=self.session_id, event=event)
                    self._pending_tool_calls -= 1
                elif isinstance(event, ToolErrorEvent):
                    yield event
                    
                    self._store.append_message(
                        session_id=self.session_id,
                        message=self._tool_error_to_message(event)
                    )
                    self._store.append_event(session_id=self.session_id, event=event)
                    self._pending_tool_calls -= 1
                elif isinstance(event, StopEvent):
                    yield event
                    self._store.append_event(session_id=self.session_id, event=event)

                if self._user_stopped:
                    stop_event = StopEvent(issuer="user")
                    yield stop_event
                    self._store.append_event(session_id=self.session_id, event=stop_event)
                    self._running = False
                    break

                # drain send message
                if self._pending_tool_calls == 0 and self._pending_message is not None:
                    self._append_user_message(self._pending_message.content)
                    self._pending_message = None
                    # if we get a user message when the agent issued a stop event the 
                    # loop restarts.
                    should_continue = True
            
            if not should_continue:
                break

        self._running = False
        # edge case: the user called send and then stop, before the enqueued message 
        # could have been consumed
        self._pending_message = None
        log_event(
            _logger, logging.INFO, "",
            session_id=self.session_id,
            total_event_count=total_event_count
        )

    def send(self, user_event: UserMessageEvent) -> bool:
        """
        Enqueue a message in the conversation, the agent processes it after the current 
        event completes it's execution.

        :returns: True if the message is enqueued, False otherwise.
        """
        if self._running and self._pending_message is None:
            self._pending_message = user_event
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
        except TimeoutError:
            log_event(
                _logger, logging.WARNING, "Tool confirmation timed out",
                session_id=self.session_id, call_id=tool_call.call_id
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
        user_message = {"role": "user", "content": content}

        self._store.append_message(
            session_id=self.session_id,
            message=Message(
                message=user_message,
                token_count=get_token_count(message=user_message),
                agent_id=self.agent_config.agent_id
            )
        )
        self._store.append_event(
            session_id=self.session_id,
            event=UserMessageEvent(content=content)
        )

    def _tool_result_to_message(self, event: ToolResultEvent) -> Message:
        tool = self.tools[event.name]
        tool_content = tool.format_result(event.result)
        tool_message = {
            "role": "tool",
            "tool_call_id": event.call_id,
            "content": tool_content
        }

        return Message(
            message=tool_message,
            token_count=get_token_count(tool_message),
            model_id=self.client.model,
            agent_id=self.agent_config.agent_id
        )
        
    def _tool_error_to_message(self, event: ToolErrorEvent) -> Message:
        tool_message = {
            "role": "tool",
            "tool_call_id": event.call_id,
            "content": f"{event.name} {event.failure}: {event.error}"
        }

        return Message(
            message=tool_message,
            token_count=get_token_count(tool_message),
            model_id=self.client.model,
            agent_id=self.agent_config.agent_id
        )
