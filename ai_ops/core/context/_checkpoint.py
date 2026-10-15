import copy

from pydantic import BaseModel

from ai_ops.core.context.transform import ContextTransform
from ai_ops.core.conversation import (
    Message,
    find_tool_call_result,
    get_token_count,
    is_tool_call,
    message_has_role,
)
from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core.tools import Tool, WhiteboardWrite

_logger = get_logger(__name__)


class CheckpointCompaction(ContextTransform):
    """
    Uses a `write_whiteboard` tool call as a checkpoint, everything before 
    gets dropped from the conversation.

    Exceptions are tools that specify `allow_compaction = False`.

    Tools that implement `post_compaction_state` get the state injected as 
    a user message.
    """
    requires_state: bool = True

    def __init__(self, tools: list[Tool]):
        """
        :param tools: tool instances to make compaction tool aware.
        """
        self.__tools = tools

    @classmethod
    def config_schema(cls) -> type[BaseModel] | None:
        return None

    def search_checkpoint(self, messages: list[Message]) -> int | None:
        """
        :returns: index of the last assistant message that called `write_whiteboard`.
        """
        # start by finding the index of the agent WhiteboardWrite call and 
        # the corresponding tool_call_id
        checkpoint_index, checkpoint_tool_call_id = None, None
        for idx, message in enumerate(messages):
            is_whiteboard, tool_call_ids = is_tool_call(
                message=message, 
                tool_name_key=WhiteboardWrite.name
            )
            if is_whiteboard:
                checkpoint_index = idx
                checkpoint_tool_call_id = tool_call_ids[-1]
        
        if checkpoint_index is None:
            return None # no whiteboard write found

        # guard: whiteboard call must have a result
        if find_tool_call_result(messages, checkpoint_tool_call_id) is None:
            return None

        return checkpoint_index
    
    def __call__(self, messages: list[Message]) -> list[Message]:
        agent_id = messages[0].agent_id
        model_id = messages[0].model_id
        token_before = sum([message.token_count for message in messages])

        _messages = copy.deepcopy(messages)
        checkpoint_idx = self.search_checkpoint(_messages)

        if checkpoint_idx is None:
            # note: no-op can return the original
            return messages
   
        pinned_tools = set()
        tools_state: dict[str, str] = {}
        for tool in self.__tools:
            if not tool.allow_compaction:
                pinned_tools.add(tool.name)

            state = tool.post_compaction_state()
            if state is not None:
                tools_state[tool.name] = state

        pre_checkpoint = _messages[:checkpoint_idx]
        post_checkpoint = _messages[checkpoint_idx:]

        # this code needs refactoring even before it's complete
        context = []
        skip_result = set()
        for message in pre_checkpoint:
            msg = message.message
            if message_has_role(message, "system") or message_has_role(message, "user"):
                context.append(message)

            if message_has_role(message, "assistant"):
                assistant_message = copy.deepcopy(message)
                assistant_message.message["tool_calls"] = []
                found_pinned = False 

                for tool_call in message.message.get("tool_calls") or []: 
                    call_id = tool_call["id"]
                    tool_name = tool_call["function"]["name"]

                    if tool_name in pinned_tools:
                        assistant_message.message["tool_calls"].append(tool_call)
                        found_pinned = True
                    else:
                        result_idx = find_tool_call_result(pre_checkpoint, call_id)
                        if result_idx is not None:
                            tool_call_to_skip = pre_checkpoint[result_idx].message["tool_call_id"]
                            skip_result.add(tool_call_to_skip)

                if found_pinned:
                    context.append(assistant_message)

            if message_has_role(message, "tool") and msg["tool_call_id"] not in skip_result:
                context.append(message)

        # recompute token counts
        for msg in context:
            msg.token_count = get_token_count(msg.message)

        context.extend(post_checkpoint)

        # inject user messages with tool state
        for tool_name, state in tools_state.items():
            raw_msg = {"role": "user", "content": state}
            
            context.append(Message(
                message=raw_msg,
                agent_id=agent_id,
                token_count=get_token_count(raw_msg),
                model_id=model_id
            ))

        token_after = sum([message.token_count for message in context])
        log_event(
            _logger, logging.INFO, "Applied CheckpointCompaction",
            token_before=token_before, token_after=token_after
        )

        return context
