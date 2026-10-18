# Agent Orchestrator Implementation
import asyncio
from collections.abc import AsyncIterator, Iterator

from ai_ops.core.context import ContextTransform, build_context
from ai_ops.core.llm import InferenceClient, aquery, query
from ai_ops.core.log import get_logger
from ai_ops.core.schema import (
    AgentMode,
    ChatCompletionEvent,
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

_logger = get_logger(__name__)

DEFAULT_ITERATION_LIMIT = {AgentMode.SUPERVISED: 30, AgentMode.UNSUPERVISED: 60}

def agent_loop_sync(
    client: InferenceClient,
    session: Session,
    tools: dict[str, Tool],
    context_transforms: list[ContextTransform] | None = None,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: int | None = None,
) -> Iterator[Event]:
    agent_tools = [tool.serialize() for tool in tools.values()]

    # stop tool is an orchestration primitive so it's always given
    agent_tools.append(StopTool().serialize())

    iteration_limit = max_iterations if max_iterations else DEFAULT_ITERATION_LIMIT[mode]

    it = 0
    stop_called = False
    while it < iteration_limit and not stop_called:
        _logger.info(
            "Agent Loop Iteration session_id=%s iteration=%s",
            session.uuid, it
        )

        context = build_context(messages=session.messages, context_transforms=context_transforms)
        try:
            response = query(
                client=client, 
                messages=[m.message for m in context], 
                tools=agent_tools,
            )
        except RuntimeError as query_err:
            yield StopEvent(
                session_id=session.uuid, 
                issuer="agent", 
                error=str(query_err)
            )
            break
        
        yield ChatCompletionEvent.from_model_response(
            session_id=session.uuid, 
            response=response
        )

        response_message = response.choices[0].message
        if not response_message.tool_calls:
            _logger.debug("no tool call in response_message session_id=%s", session.uuid)
            yield StopEvent(
                session_id=session.uuid, 
                issuer="agent",
                reason="no tool calls"
            )
            break
        
        for tool_call in response_message.tool_calls:
            _logger.debug(
                "raw tool call model=%s tool_call=%s",
                response.model, tool_call.model_dump_json()
            )
            
            tool_name = tool_call.function.name
            
            if tool_name == StopTool.name:
                reason = StopTool.get_input_schema().model_validate_json(tool_call.function.arguments)
                # carry the stop tool_call id so the runner can persist the
                # synthetic tool result that answers it (keeps the trajectory
                # resumable, see AgentRunner._stop_to_message).
                yield StopEvent(
                    session_id=session.uuid,
                    issuer="agent", 
                    reason=reason.reason, 
                    call_id=tool_call.id
                )
                stop_called = True
                break
            
            tool, args = validate_tool_call(available_tools=tools, tool_call=tool_call)
            if tool is None:
                error_msg = args
                _logger.error(
                    "model=%s tool_error=%s",
                    response.model, f"\"{error_msg}\""
                )

                yield ToolErrorEvent(
                    session_id=session.uuid,
                    failure=ToolErrorFailure.VALIDATION_ERROR,
                    call_id=tool_call.id,
                    name=tool_name,
                    error=error_msg
                )
                continue

            # note: here we don't evaluate policy, at least for now
            yield ToolCallEvent(
                session_id=session.uuid, 
                call_id=tool_call.id, 
                name=tool_name, args=args
            )
            try:
                tool_result = tool(args)
                yield ToolResultEvent(
                    session_id=session.uuid,
                    call_id=tool_call.id, 
                    name=tool_name, args=args, 
                    result=tool_result
                )
            except Exception as tool_failure:
                yield ToolErrorEvent(
                    session_id=session.uuid,
                    failure=ToolErrorFailure.EXECUTION_ERROR,
                    call_id=tool_call.id,
                    name=tool_name,
                    error=str(tool_failure)
                )

        it += 1


async def agent_loop(
    client: InferenceClient,
    session: Session,
    tools: dict[str, Tool],
    context_transforms: list[ContextTransform] | None = None,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: int | None = None,
    confirm: ConfirmCallback | None = None,
) -> AsyncIterator[Event]:
    iteration_limit = max_iterations if max_iterations else DEFAULT_ITERATION_LIMIT[mode]
    agent_tools = [tool.serialize() for tool in tools.values()]
    agent_tools.append(StopTool().serialize())

    turn, stop_called = 0, False
    while turn < iteration_limit and not stop_called:
        _logger.info("Agent Loop Iteration session_id=%s turn=%s", session.uuid, turn)

        context = build_context(messages=session.messages, context_transforms=context_transforms)
        try:
            response = await aquery(
                client=client,
                messages=[m.message for m in context],
                tools=agent_tools,
            )
        except RuntimeError as query_err:
            yield StopEvent(session_id=session.uuid, issuer="agent", error=str(query_err))
            break

        yield ChatCompletionEvent.from_model_response(
            session_id=session.uuid, 
            response=response
        )
        
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls is None or (isinstance(tool_calls, list) and len(tool_calls) == 0):
            _logger.debug("no tool call in response_message session_id=%s", session.uuid)
            yield StopEvent(session_id=session.uuid, issuer="agent", reason="no tool calls")
            break

        for tool_call in tool_calls:
            _logger.debug(
                "raw tool call model=%s tool_call=%s",
                response.model, tool_call.model_dump_json()
            )

            tool_name = tool_call.function.name

            if tool_name == StopTool.name:
                reason = StopTool.get_input_schema().model_validate_json(tool_call.function.arguments)
                yield StopEvent(
                    session_id=session.uuid,
                    issuer="agent", 
                    reason=reason.reason, 
                    call_id=tool_call.id
                )
                stop_called = True
                break

            tool, args = validate_tool_call(available_tools=tools, tool_call=tool_call)
            if tool is None:
                error_msg = args
                _logger.error(
                    "Invalid tool call model=%s tool_error=%s", 
                    response.model, f"\"{error_msg}\""
                )

                yield ToolErrorEvent(
                    session_id=session.uuid,
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
                session_id=session.uuid,
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
                        session_id=session.uuid,
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
                yield ToolResultEvent(
                    session_id=session.uuid,
                    call_id=tool_call.id, 
                    name=tool_name, args=args, 
                    result=tool_result
                )
            except Exception as tool_failure:
                yield ToolErrorEvent(
                    session_id=session.uuid,
                    failure=ToolErrorFailure.EXECUTION_ERROR,
                    call_id=tool_call.id,
                    name=tool_name,
                    error=str(tool_failure)
                )

        turn += 1
