# Agent Orchestrator Implementation
import json
import copy
from collections import deque
from difflib import SequenceMatcher
from typing import Dict, Iterator, Optional, cast

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
from ai_ops.core.conversation import Conversation, Message
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
from ai_ops.core.tools import Tool, WhiteboardRead, validate_tool_call
from ai_ops.core.conversation import get_token_count
from ai_ops.core.tracing import agent_trace
from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)
# the values will probably change based on traces
DEFAULT_ITERATION_LIMIT = {AgentMode.SUPERVISED: 30, AgentMode.UNSUPERVISED: 50}
DEFAULT_TEMPERATURE = 0.4

class StopReason(BaseModel):
    reason: str

class Noop(BaseModel): 
    pass

# stop tool is an orchestration primitive so it's always given
class StopTool(Tool[StopReason, Noop]):    
    name = "stop"
    description = "Call this tool when you reached the user objective."

    def __call__(self, _: StopReason) -> Noop:
        return Noop()
    @staticmethod
    def format_result(_: Noop) -> str:
        return ""

# a circular buffer that is used to determine if the agent is stuck in a loop
# by checking the last `window_size` tool calls, if the count exceeds a threshold
# check returns True
class LoopDetector:
    def __init__(self, window_size: int = 6, threshold: int = 3, similarity: float = 0.85):
        self.threshold = threshold
        self.similarity = similarity
        self.__buffer: deque[str] = deque(maxlen=window_size)

    def _similar(self, a: str, b: str) -> bool:
        return SequenceMatcher(None, a, b).ratio() >= self.similarity

    def check(self, tool_call_json: str) -> bool:
        similar_count = sum(1 for prev in self.__buffer if self._similar(prev, tool_call_json))
        self.__buffer.append(tool_call_json)
        return similar_count >= self.threshold


def trim_tool_call_log(tool_call: ChatCompletionMessageToolCall) -> str:
    try:
        trimmed_tool_call = copy.deepcopy(tool_call)
        
        args = trimmed_tool_call.function.arguments
        if isinstance(args, str):
            args = json.loads(args)
            
        trimmed_tool_call.function.arguments = {
            k: f"{v[:15]}...{v[len(v)-15:]}" 
            for k, v in args
        }
        
        return trimmed_tool_call.model_dump_json()
    except Exception:
        return tool_call.model_dump_json()[:30]


# The orchestrator implements the agent logic, currently that's just ReAct loop.
# It's intentionally kept stateless so the only concern remains the orchestration 
# of the agent actions. 
# Conversation management and LLM reliability should be kept outside the orchestrator.
@agent_trace
def orchestrator(
    client: InferenceClient,
    conversation: Conversation,
    tools: Dict[str, Tool],
    context_fn: ContextView,
    mode: AgentMode = AgentMode.SUPERVISED,
    max_iterations: Optional[int] = None
) -> Iterator[Message | Event]:
    agent_tools = [tool.serialize() for tool in tools.values()]
    agent_tools.append(StopTool().serialize())

    iteration_limit = max_iterations if max_iterations else DEFAULT_ITERATION_LIMIT[mode]
    loop_detector = LoopDetector()

    it = 0
    stop_called = False
    while it < iteration_limit and not stop_called:
        log_event(
            _logger, logging.INFO, "", 
            conversation_id=conversation.id, iteration=it
        )
        selected_messages = context_fn(conversation.messages)
        context = [m.message for m in selected_messages]
        # window_size = sum([m.token_count for m in selected_messages if m.token_count is not None])
        # _logger.info(f"context_window_size={window_size}")

        # append the whiteboard index to the last user message in every loop iteration,
        # note: the index is not part of the "persisted" conversation, also this breaks 
        # prefix caching.
        if WhiteboardRead.name in tools:
            whiteboard_tool: WhiteboardRead = tools[WhiteboardRead.name]
            if whiteboard_tool.index:
                last_usr_idx = next(
                    (
                        i for i in range(len(context)-1, -1, -1)
                        if context[i].get("role", "") == "user"
                    ),
                    None
                )
                log_event(
                    _logger, logging.DEBUG, 
                    "Appending whiteboard index to message",
                    last_user_idx={last_usr_idx}
                )
                if last_usr_idx is not None:
                    context[last_usr_idx]["content"] += whiteboard_tool.index

        response = query(client=client, messages=context, tools=agent_tools)
        response_message = response.choices[0].message

        chat_completion_message = cast(ChatCompletionAssistantMessage, response_message.model_dump())
        yield Message(
            message=chat_completion_message, 
            token_count=get_token_count(chat_completion_message)
        )

        if not response_message.tool_calls:
            log_event(
                _logger, logging.DEBUG, 
                "no tool call in response_message",
                conversation_id=conversation.id, 
            )
            break

        for tool_call in response_message.tool_calls:
            log_event(
                _logger, logging.DEBUG, "raw tool call",
                model=response.model, tool_call=trim_tool_call_log(tool_call)
            )
            if loop_detector.check(tool_call.model_dump_json()):
                log_event(
                    _logger, logging.INFO, 
                    "LoopDetector triggered", iteration=it
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
                yield ToolResultEvent(call_id=tool_call.id, name=tool_name, args=args, result=tool_result)
            except Exception as tool_failure:
                yield ToolErrorEvent(
                    failure=ToolErrorFailure.EXECUTION_ERROR,
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    error=str(tool_failure)
                )

        it += 1

    if not stop_called:
        context = [m.message for m in context_fn(conversation.messages)]
        context.append(ChatCompletionUserMessage(
            role="user", 
            content="You have reached the max iteration limit. Produce an assessment of where you got so far."
        ))
        
        response = query(client=client, messages=context)
        response_message = response.choices[0].message

        if response_message.content:
            yield StopEvent(issuer="agent", reason=response_message.content, max_iteration=True)

