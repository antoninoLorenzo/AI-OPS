# Agent Orchestrator Implementation
from typing import Dict, Optional, Iterator, cast

import litellm
from litellm import (
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage,
    ChatCompletionAssistantMessage,
    ChatCompletionToolMessage
)
from pydantic import BaseModel

from ai_ops.core.schema import (
    AgentMode,
    Event, EventType,
    TextEvent,
    ToolCallEvent,
    ToolResultEvent,
    StopEvent
)
from ai_ops.core.llm import InferenceClient, query
from ai_ops.core.tools import Tool, Whiteboard, validate_tool_call
from ai_ops.core.conversation import Message, Conversation, get_conversation_store
from ai_ops.core.context_management import ContextView
from ai_ops.core.tracing import agent_trace
from ai_ops.core.utils import get_logger

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

    it = 0
    stop_called = False
    while it < iteration_limit and not stop_called:
        _logger.info(f"conversation_id={conversation.id} iteration={it}")
        selected_messages = context_fn(conversation.messages)
        context = [m.message for m in selected_messages]
        window_size = sum([m.token_count for m in selected_messages])
        _logger.info(f"context_window_size={window_size}")

        # append the whiteboard index to the last user message in every loop iteration,
        # note: the index is not part of the "persisted" conversation, also this breaks 
        # prefix caching.
        if Whiteboard.name in tools:
            whiteboard_tool: Whiteboard = tools[Whiteboard.name]
            if whiteboard_tool.index:
                last_usr_idx = next(
                    (
                        i for i in range(len(context)-1, -1, -1)
                        if context[i].role == "user"
                    ),
                    None
                )
                _logger.debug(f"Appending whiteboard index to message last_usr_idx={last_usr_idx}")
                if last_usr_idx is not None:
                    context[last_usr_idx]["content"] += f"Whiteboard Index:\n{whiteboard_tool.index}"

        response = query(client=client, messages=context, tools=agent_tools)
        response_message = response.choices[0].message

        yield Message(
            message=cast(ChatCompletionAssistantMessage, response_message.model_dump()),
            token_count=litellm.token_counter(text=response_message.content or "")
        )

        if not response_message.tool_calls:
            _logger.debug(f"no tool_call in response_message")
            break

        for tool_call in response_message.tool_calls:
            _logger.debug(f"raw tool call from {response.model}: {tool_call.model_dump()}")
            tool_name = tool_call.function.name
            
            if tool_name == StopTool.name:
                reason = StopTool.get_input_schema().model_validate_json(tool_call.function.arguments)
                yield StopEvent(issuer="agent", reason=reason)
                stop_called = True
                break
            
            tool, args = validate_tool_call(available_tools=tools, tool_call=tool_call)
            if tool is None:
                # note: could retry 
                _logger.error(f"model={response.model} tool_error={args}")
                continue

            # note: there goes the logic for approval
            yield ToolCallEvent(call_id=tool_call.id, name=tool_name, args=args)
            tool_result = tool(args)
            yield ToolResultEvent(call_id=tool_call.id, name=tool_name, args=args, result=tool_result)

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

