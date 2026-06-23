# Agent Orchestrator Implementation
import json
import copy
from collections import deque
from difflib import SequenceMatcher
from typing import Dict, Iterator, Optional, List, cast

import litellm
from litellm import (
    ChatCompletionAssistantMessage,
    ChatCompletionSystemMessage,
    ChatCompletionToolMessage,
    ChatCompletionUserMessage,
    ChatCompletionMessageToolCall
)
from pydantic import BaseModel

from ai_ops.core.context_management import ContextView
from ai_ops.core.conversation import (
    Conversation, 
    Message, 
    is_valid_message_list, 
    find_last_user_message_index
)
from ai_ops.core.llm import InferenceClient, query
from ai_ops.core.schema import (
    AgentMode,
    Event,
    StopEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolErrorEvent,
    ToolErrorFailure
)
from ai_ops.core.tools import Tool, WhiteboardWrite, validate_tool_call
from ai_ops.core.conversation import get_token_count
from ai_ops.core.tracing import agent_trace
from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)

DEFAULT_ITERATION_LIMIT = {AgentMode.SUPERVISED: 30, AgentMode.UNSUPERVISED: 60}
DEFAULT_TEMPERATURE = 0.4

class StopReason(BaseModel):
    reason: str

class Noop(BaseModel): 
    pass

class StopTool(Tool[StopReason, Noop]):    
    name = "stop"
    description = "Call this tool when you reached the user objective."

    def __call__(self, _: StopReason) -> Noop:
        return Noop()

    @staticmethod
    def format_result(_: Noop) -> str:
        return ""


# The orchestrator implements the agent logic, currently that's just ReAct loop.
# It's intentionally kept stateless so the only concern remains the orchestration 
# of the agent actions. 
# Conversation management and LLM reliability should be kept outside the orchestrator.
# TODO: mode is not actually used to determine whether a command needs approval
@agent_trace
def orchestrator(
    client: InferenceClient,
    conversation: Conversation,
    tools: Dict[str, Tool],
    context_fn: ContextView,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: Optional[int] = None,
    temperature: float = DEFAULT_TEMPERATURE
) -> Iterator[Message | Event]:
    if not is_valid_message_list(conversation.messages):
        raise ValueError(f"Invalid conversation. Expected [system, user, ...] message list.")

    agent_tools = [tool.serialize() for tool in tools.values()]

    # stop tool is an orchestration primitive so it's always given
    agent_tools.append(StopTool().serialize())

    iteration_limit = max_iterations if max_iterations else DEFAULT_ITERATION_LIMIT[mode]

    it = 0
    stop_called = False
    while it < iteration_limit and not stop_called:
        log_event(
            _logger, logging.INFO, "Agent Loop Iteration", 
            conversation_id=conversation.uuid, iteration=it
        )

        context = context_fn(conversation.messages)

        # append the whiteboard index to the last user message in every loop iteration,
        # note: the index is not part of the "persisted" conversation, also this breaks 
        # prefix caching.
        if WhiteboardWrite.name in tools:
            whiteboard_tool= tools[WhiteboardWrite.name]
            last_user_idx = find_last_user_message_index(messages=context)

            log_event(_logger, logging.DEBUG, "Appending whiteboard index to message", last_user_idx={last_user_idx})
            context[last_user_idx].message["content"] += "\n" + whiteboard_tool.index

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
            token_count=get_token_count(chat_completion_message)
        )

        if not response_message.tool_calls:
            log_event(_logger, logging.DEBUG, "no tool call in response_message", conversation_id=conversation.uuid)
            yield StopEvent(issuer="agent")
            break
        

        for tool_call in response_message.tool_calls:
            log_event(
                _logger, logging.DEBUG, "raw tool call",
                model=response.model, tool_call=tool_call.model_dump_json()
            )
            
            tool_name = tool_call.function.name
            
            if tool_name == StopTool.name:
                reason = StopTool.get_input_schema().model_validate_json(tool_call.function.arguments)
                yield StopEvent(issuer="agent", reason=reason.reason)
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
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    error=error_msg
                )
                continue

            yield ToolCallEvent(call_id=tool_call.id, name=tool_name, args=args)
            try:
                tool_result = tool(args)
                # TODO: here we need to discriminate between failures on success clearly
                yield ToolResultEvent(call_id=tool_call.id, name=tool_name, args=args, result=tool_result)
            except Exception as tool_failure:
                yield ToolErrorEvent(
                    failure=ToolErrorFailure.EXECUTION_ERROR,
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    error=str(tool_failure)
                )

        it += 1
