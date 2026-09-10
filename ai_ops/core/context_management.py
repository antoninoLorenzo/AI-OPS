import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from ai_ops.core.conversation import (
    Message,
    count_tokens,
    find_tool_call_result,
    get_token_count,
    is_tool_call,
    is_valid_context,
)
from ai_ops.core.log import get_logger, log_event, logging
from ai_ops.core.tools import (
    Tool,
    WhiteboardWrite,
)

_logger = get_logger(__name__)


class ContextTransformType(StrEnum):
    CHECKPOINT = "checkpoint"


@runtime_checkable
class ContextTransform(Protocol):
    """
    Implementations should return a deep copy of the selected messages.
    > Note: deep copying is accettable, memory-wise, under the assumption that 
    messages contain only text.
    """
    def __init__(self, **kwargs): # smell
        pass

    def __call__(self, messages: list[Message]) -> list[Message]:
        """
        :param messages: list of chat completion compliant messages.
        :returns: a modified copy of the original message list.
        """


def build_context(
    messages: list[Message],
    context_transforms: list[ContextTransform] | None = None
) -> list[Message]:
    if context_transforms is None:
        context_transforms = []
        
    valid, err = is_valid_context(messages)
    if not valid:
        raise ValueError(f"Received invalid message list: {err}")

    context = messages
    for transform in context_transforms:
        _messages = transform(messages=context)
        valid, err = is_valid_context(_messages)
        if not valid:
            log_event(
                _logger, logging.WARNING, "Skipping invalid malformed transform", 
                context_view=type(transform).__name__, error=err
            )
        else:
            context = _messages
            
    return context


class SlidingWindow(ContextTransform):
    def __init__(self, max_context_length: int):
        self.max_context_length = max_context_length
        self._max_input = int(max_context_length * 0.8)
        # print(f"max_input={self._max_input}")

    def __call__(self, messages: list[Message]) -> list[Message]:
        context_length = sum([
            message.token_count if message.token_count is not None \
                else get_token_count(message.message)
            for message in messages
        ])

        if context_length <= self._max_input:
            return messages
        
        _messages = copy.deepcopy(messages)
        delta = context_length - self._max_input
        
        # here count token consumption of (assistant, tool_calls) blocks (turns)
        # until we reach delta (how much we have to cut)
        s = 0       # sum of token counts up to idx
        idx = 0     # cut idx
        while idx < len(_messages):
            message = _messages[idx]
            msg = message.message

            if msg["role"] == "assistant":
                s += message.token_count
                
                tool_calls = msg.get("tool_calls") or []
                # note: the next len(tool_calls) messages are guaranteed to have 
                # role tool by chat completions format
                for i in range(idx + 1, idx + 1 + len(tool_calls)):
                    s += _messages[i].token_count
                
                # print(f"DEBUG: assistant_idx={idx}; sum={s}; len(tool_calls)={len(tool_calls)}")
                idx += len(tool_calls) + 1

                if s >= delta:
                    break

                continue

            idx += 1 

        context = []
        for i, message in enumerate(_messages):
            msg = message.message
            if msg["role"] in ("system", "user"):
                context.append(message)
            
            if i < idx:
                continue

            if msg["role"] in ("assistant", "tool"):
                context.append(message)

        return context


class CheckpointCompaction(ContextTransform):
    """
    Uses a `write_whiteboard` tool call as a checkpoint, everything before 
    gets dropped from the conversation.

    Exceptions are tools that specify `allow_compaction = False`.

    Tools that implement `post_compaction_state` get the state injected as 
    a user message.
    """

    def __init__(self, tools: list[Tool]):
        """
        :param tools: tool instances to make compaction tool aware.
        """
        self.__tools = tools

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
        token_before = count_tokens(messages=messages)

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
            if msg["role"] in ("system", "user"):
                context.append(message)

            if msg["role"] == "assistant":
                assistant_message = copy.deepcopy(message)
                assistant_message.message["tool_calls"] = []
                found_pinned = False 

                tool_calls = msg.get("tool_calls", [])
                for tool_call in tool_calls:
                    tool_call_id = tool_call["id"]
                    tool_name = tool_call["function"]["name"]

                    if tool_name in pinned_tools:
                        assistant_message.message["tool_calls"].append(tool_call)
                        found_pinned = True
                    else:
                        result_idx = find_tool_call_result(pre_checkpoint, tool_call_id)
                        if result_idx is not None:
                            tool_call_to_skip = pre_checkpoint[result_idx].message["tool_call_id"]
                            skip_result.add(tool_call_to_skip)

                if found_pinned:
                    context.append(assistant_message)
            
            if msg["role"] == "tool" and msg["tool_call_id"] not in skip_result:
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

        token_after = count_tokens(messages=context)
        log_event(
            _logger, logging.INFO, "Applied CheckpointCompaction",
            token_before=token_before, token_after=token_after
        )

        return context


ContextTransformRegistry: dict[ContextTransformType, type[ContextTransform]] = {
    ContextTransformType.CHECKPOINT: CheckpointCompaction
}
