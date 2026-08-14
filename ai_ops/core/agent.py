# Agent Orchestrator Implementation
import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from typing import cast

from litellm import (
    ChatCompletionAssistantMessage,
)

from ai_ops.config import BASE_AGENT_ID, DEFAULT_TEMPERATURE, TEMPERATURE_ENV
from ai_ops.core.context_management import ContextTransform, build_context
from ai_ops.core.conversation import Message, get_token_count
from ai_ops.core.llm import InferenceClient, aquery, query
from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core.schema import (
    AgentMode,
    ConfirmCallback,
    Event,
    StopEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolErrorFailure,
    ToolResultEvent,
)
from ai_ops.core.storage import Session
from ai_ops.core.tools import StopTool, Tool, validate_tool_call
from ai_ops.core.tracing import agent_trace

_logger = get_logger(__name__)

DEFAULT_ITERATION_LIMIT = {AgentMode.SUPERVISED: 30, AgentMode.UNSUPERVISED: 60}
try:
    _AGENT_TEMPERATURE = float(os.environ.get(TEMPERATURE_ENV, str(DEFAULT_TEMPERATURE)))
except ValueError:
    _AGENT_TEMPERATURE = DEFAULT_TEMPERATURE


# The orchestrator implements the agent logic, currently that's just ReAct loop.
# It's intentionally kept stateless so the only concern remains the orchestration 
# of the agent actions. 
# Conversation management and LLM reliability should be kept outside the orchestrator.
# TODO: mode is not actually used to determine whether a command needs approval
@agent_trace
def orchestrator(
    client: InferenceClient,
    session: Session,
    tools: dict[str, Tool],
    context_transforms: list[ContextTransform] | None = None,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: int | None = None,
    temperature: float = _AGENT_TEMPERATURE,
    agent_id: str = BASE_AGENT_ID
) -> Iterator[Message | Event]:
    agent_tools = [tool.serialize() for tool in tools.values()]

    # stop tool is an orchestration primitive so it's always given
    agent_tools.append(StopTool().serialize())

    iteration_limit = max_iterations if max_iterations else DEFAULT_ITERATION_LIMIT[mode]

    it = 0
    stop_called = False
    while it < iteration_limit and not stop_called:
        log_event(
            _logger, logging.INFO, "Agent Loop Iteration", 
            session_id=session.uuid, iteration=it
        )

        context = build_context(messages=session.messages, context_transforms=context_transforms)
        try:
            response = query(
                client=client, 
                messages=[m.message for m in context], 
                tools=agent_tools, 
                temperature=temperature
            )
        except RuntimeError as query_err:
            yield StopEvent(issuer="agent", error=str(query_err))
            break

        response_message = response.choices[0].message
        chat_completion_message = cast(ChatCompletionAssistantMessage, response_message.model_dump())

        yield Message(
            message=chat_completion_message,
            token_count=get_token_count(chat_completion_message),
            model_id=client.model,
            agent_id=agent_id
        )

        if not response_message.tool_calls:
            log_event(_logger, logging.DEBUG, "no tool call in response_message", session_id=session.uuid)
            yield StopEvent(issuer="agent")
            break
        
        for tool_call in response_message.tool_calls:
            log_event(
                _logger, logging.DEBUG, "raw tool call",
                model=response.model, tool_call=tool_call.model_dump_json()
            )
            
            tool_name = tool_call.function.name
            
            if tool_name == StopTool.name:
                # TODO: `break` skips any sibling tool_calls positioned after stop
                # in this same assistant message, leaving them unanswered. Out of
                # scope here; the common case is stop emitted on its own.
                reason = StopTool.get_input_schema().model_validate_json(tool_call.function.arguments)
                # carry the stop tool_call id so the runner can persist the
                # synthetic tool result that answers it (keeps the trajectory
                # resumable, see AgentRunner._stop_to_message).
                yield StopEvent(issuer="agent", reason=reason.reason, call_id=tool_call.id)
                stop_called = True
                break
            
            tool, args = validate_tool_call(available_tools=tools, tool_call=tool_call)
            if tool is None:
                error_msg = args
                log_event(
                    _logger, logging.ERROR, "", 
                    model=response.model, tool_error=f"\"{error_msg}\""
                )

                yield ToolErrorEvent(
                    failure=ToolErrorFailure.VALIDATION_ERROR,
                    call_id=tool_call.id,
                    name=tool_name,
                    error=error_msg
                )
                continue

            # note: here we don't evaluate policy, at least for now
            yield ToolCallEvent(call_id=tool_call.id, name=tool_name, args=args)
            try:
                tool_result = tool(args)
                yield ToolResultEvent(call_id=tool_call.id, name=tool_name, args=args, result=tool_result)
            except Exception as tool_failure:
                yield ToolErrorEvent(
                    failure=ToolErrorFailure.EXECUTION_ERROR,
                    call_id=tool_call.id,
                    name=tool_name,
                    error=str(tool_failure)
                )

        it += 1


# Async variant of `orchestrator`. It mirrors the synchronous loop one-to-one,
# the only difference is that inference is awaited (`aquery`) so the loop doesn't
# block the event loop while waiting on the model provider.
# Tools are still synchronous, but they're run via `asyncio.to_thread` so a
# blocking tool doesn't freeze the event loop (see the tool-execution comment).
# `agent_trace` detects the async-generator function and dispatches to the async
# tracer, so tracing works the same way it does for `orchestrator`.
@agent_trace
async def aorchestrator(
    client: InferenceClient,
    session: Session,
    tools: dict[str, Tool],
    context_transforms: list[ContextTransform] | None = None,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: int | None = None,
    temperature: float = _AGENT_TEMPERATURE,
    confirm: ConfirmCallback | None = None,
    agent_id: str = BASE_AGENT_ID
) -> AsyncIterator[Message | Event]:
    agent_tools = [tool.serialize() for tool in tools.values()]

    # stop tool is an orchestration primitive so it's always given
    agent_tools.append(StopTool().serialize())

    iteration_limit = max_iterations if max_iterations else DEFAULT_ITERATION_LIMIT[mode]

    it = 0
    stop_called = False
    while it < iteration_limit and not stop_called:
        log_event(
            _logger, logging.INFO, "Agent Loop Iteration",
            session_id=session.uuid, iteration=it
        )

        context = build_context(messages=session.messages, context_transforms=context_transforms)
        try:
            response = await aquery(
                client=client,
                messages=[m.message for m in context],
                tools=agent_tools,
                temperature=temperature
            )
        except RuntimeError as query_err:
            yield StopEvent(issuer="agent", error=str(query_err))
            break

        response_message = response.choices[0].message
        chat_completion_message = cast(ChatCompletionAssistantMessage, response_message.model_dump())

        yield Message(
            message=chat_completion_message,
            token_count=get_token_count(chat_completion_message),
            model_id=client.model,
            agent_id=agent_id
        )

        if not response_message.tool_calls:
            log_event(_logger, logging.DEBUG, "no tool call in response_message", session_id=session.uuid)
            yield StopEvent(issuer="agent")
            break


        for tool_call in response_message.tool_calls:
            log_event(
                _logger, logging.DEBUG, "raw tool call",
                model=response.model, tool_call=tool_call.model_dump_json()
            )

            tool_name = tool_call.function.name

            if tool_name == StopTool.name:
                # TODO: `break` skips any sibling tool_calls positioned after stop
                # in this same assistant message, leaving them unanswered. Out of
                # scope here; the common case is stop emitted on its own.
                reason = StopTool.get_input_schema().model_validate_json(tool_call.function.arguments)
                # carry the stop tool_call id so the runner can persist the
                # synthetic tool result that answers it (keeps the trajectory
                # resumable, see AgentRunner._stop_to_message).
                yield StopEvent(issuer="agent", reason=reason.reason, call_id=tool_call.id)
                stop_called = True
                break

            tool, args = validate_tool_call(available_tools=tools, tool_call=tool_call)
            if tool is None:
                error_msg = args
                log_event(
                    _logger, logging.ERROR, "",
                    model=response.model, tool_error=f"\"{error_msg}\""
                )

                yield ToolErrorEvent(
                    failure=ToolErrorFailure.VALIDATION_ERROR,
                    call_id=tool_call.id,
                    name=tool_name,
                    error=error_msg
                )
                continue

            # admission: `evaluate` decides whether the call is blocked. A blocked
            # call is not executed in UNSUPERVISED; in SUPERVISED the user is asked
            # to confirm (the injected `confirm` awaits the decision, applying its
            # own timeout policy). A not-executed call still reports a result so
            # the conversation stays well-formed.
            blocked = tool.evaluate(args)
            will_confirm = blocked and mode == AgentMode.SUPERVISED
            tool_call_event = ToolCallEvent(
                call_id=tool_call.id, name=tool_name, args=args,
                requires_confirmation=will_confirm
            )
            yield tool_call_event

            if blocked:
                approved = False
                if will_confirm and confirm is not None:
                    approved = await confirm(tool_call_event)
                if not approved:
                    yield ToolResultEvent(
                        call_id=tool_call.id, name=tool_name, args=args,
                        result=tool.not_admitted_result(args)
                    )
                    continue

            try:
                # tools are synchronous and may block (ex. Terminal waits on a
                # subprocess up to MAX_COMMAND_TIMEOUT_S); run off the event loop
                # so a blocking tool doesn't freeze the whole loop (and with it
                # every other conversation and the stop/confirm endpoints).
                tool_result = await asyncio.to_thread(tool, args)
                yield ToolResultEvent(call_id=tool_call.id, name=tool_name, args=args, result=tool_result)
            except Exception as tool_failure:
                yield ToolErrorEvent(
                    failure=ToolErrorFailure.EXECUTION_ERROR,
                    call_id=tool_call.id,
                    name=tool_name,
                    error=str(tool_failure)
                )

        it += 1
