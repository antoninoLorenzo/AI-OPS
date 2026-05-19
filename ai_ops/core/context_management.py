import copy
import itertools
from typing import List, Tuple, Protocol, Annotated, runtime_checkable

from pydantic import Field
from litellm import ChatCompletionAssistantMessage, ChatCompletionToolMessage

from ai_ops.core.conversation import (
    Message, 
    is_tool_call, 
    find_tool_call_result, 
    get_token_count
)
from ai_ops.core.tools import (
    WhiteboardWrite, 
    WhiteboardRead,
    LoadSkill, 
    ThinkTool,
    validate_tool_call
)
from ai_ops.core.tools.terminal.terminal import Terminal
from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)


@runtime_checkable
class ContextView(Protocol):
    """`Conversation` is an append-only record, `ContextView` exists to give 
    the LLM a compressed or potentially modified subset of the messages.
    Keeping the conversation history and the context given to the LLM separate 
    allows the orchestrator to inject ephemeral context (ex. mutable indexes) 
    in the model context window without bloating the conversation history.

    Implementations should return a deep copy of the selected messages.

    > Note: deep copying is accettable, memory-wise, under the assumption that 
    messages contain only text, however that wouldn't really be great if the 
    conversation (following OpenAI format) contained base64 encoded binary blobs.
    """

    def __call__(self, messages: List[Message]) -> List[Message]:
        pass


class RawContextView(ContextView):
    """Default ContextView strategy"""
    def __call__(self, messages: List[Message]) -> List[Message]:
        return copy.deepcopy(messages)
    

class LayeredContextView(ContextView):
    """Implements context compaction at two levels of trajectory granularity: 
    `pre-checkpoint` compaction drops everything before the last whiteboard 
    write, `active-window` compaction happens after the last whiteboard write.
    The system prompt and the user messages are never touched. 

    A whiteboard write (checkpoint) is a signal that the agent completed a 
    sequence of operations either with a positive outcome (ex. found host, 
    found SQLi etc.) or a negative one (ex. attempted path traversal etc.). 
    The whiteboard index contains information about the finding that is kept 
    in-context, while the full whiteboard contains the of operations the agent 
    performed to achieve X. 
    
    The `pre-checkpoint` strategy uses as heuristic a whiteboard write to keep 
    irrelevant info out of context. However this approach is as effective as 
    the frequency at which the agent performs whiteboard writes, assuming it 
    does at all (depending on IF capabilities of the model).
    
    The `active-window` strategy keeps the current context (after checkpoint) 
    clean, independently of whether the agent uses (or is given) the whiteboard 
    tools.
    """

    def __init__(
        self,
        max_window_tokens: int,
        truncation_threshold: Annotated[float, Field(ge=0.0, lt=1.0)] = 0.1,
        max_think: int = 3,
        max_file_write: int = 3,
        terminal_alias: str | None = None,
        file_write_alias: str | None = None
    ):
        """
        :param max_window_tokens: maximum context length of model.
        
        :param truncation_threshold: 
            Percentage of `max_window_tokens`, beyond that stuff will be truncated.
            Default: 10% of `max_window_tokens` (ex. ~1600 for 16k).
        
        :param max_think: Keep last `max_think` Think calls in active window.
        
        :param max_file_write: Keep last `max_file_write` Think calls in active window.
        
        :param terminal_alias: 
            if provided, will be used as name to search for terminal tool calls within 
            the message list. (fucking benchmarks)

        :param file_write_alias: same as `terminal_alias` (fucking benchmarks)
        """
        self.max_window_tokens = max_window_tokens
        self.truncation_threshold = truncation_threshold
        self.max_think = max_think
        self.max_file_write = max_file_write
        self._max_tool_tokens = int(truncation_threshold * max_window_tokens)

        # Currently the Terminal is not tested and the file write tool is not even 
        # implemented since running bench had priority.
        self.terminal_name = terminal_alias if terminal_alias else Terminal.name
        self.file_write_name = file_write_alias if file_write_alias else ""


    def search_checkpoint(self, messages: List[Message]) -> int | None:
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

        # then find the index of the message containing the result of the 
        # whiteboard write by tool_call_id
        checkpoint_index = find_tool_call_result(
            messages=messages, 
            tool_call_id=checkpoint_tool_call_id
        )
        
        return checkpoint_index

    def apply_active_window(self, messages: List[Message]) -> List[Message]:
        # Preserved: user messages, read_whiteboard, load_skill
        # We can't assume (ToolCall, ToolResult) appear sequentially... or can we?
        # The algorithm to drop tool calls can't assume an assistant message contains only 
        # one tool call, for example multiple tool calls of different kind or of the same 
        # kind can happen in the same message.
        # To drop the tool results we can use a mask i.e list of indexes to drop, however 
        # the tool call should be removed from the message itself.
        # Terminal output is an in-place modification of the message (not drop).
        idx_from_end, total_len = 0, len(messages)
        drop_mask = [True for _ in range(total_len)]
        think_count, file_write_count = 0, 0
        # note: reversed allows in-place modifications
        for message in reversed(messages):
            idx_from_end += 1
            idx = total_len - idx_from_end

            # ChatCompletionToolMessage doesn't contain the name of the tool so we have 
            # to apply the same logic where when we find a tool call we search by call id.
            is_terminal, term_call_id = is_tool_call(
                message=message,
                tool_name_key=self.terminal_name
            )
            if is_terminal:
                for call_id in (term_call_id or []):
                    term_res_idx = find_tool_call_result(
                        messages=messages, 
                        tool_call_id=call_id
                    )
                    if term_res_idx is None:
                        continue

                    term_result = messages[term_res_idx]
                    if not (term_result.token_count and term_result.token_count > self._max_tool_tokens):
                        continue

                    original_content = term_result.message.get("content")
                    if original_content is None:
                        continue

                    log_event(
                        _logger, logging.DEBUG, "message.token_count > max_tool_tokens", 
                        message_idx=term_res_idx, is_terminal=is_terminal, 
                        token_count=term_result.token_count,
                        max_tool_tokens=self._max_tool_tokens
                    )

                    # Tokens to truncate are (message.token_count - max_tool_tokens) however 
                    # we need to approximate how much characters to remove from content, to
                    # do so we approximate 4 chars x tok (ok assuming english...).
                    truncation_char_count = (term_result.token_count - self._max_tool_tokens) * 4
                    truncated_content = "[truncated...]" + original_content[truncation_char_count:]
                    term_result.message["content"] = truncated_content     
                    term_result.token_count = get_token_count(term_result.message)               
                    
            # ex. max_think = 2
            # [...Think...Think...Think...] -> [...[dropped]...Think...Think...]
            is_think, think_call_ids = is_tool_call(
                message=message, 
                tool_name_key=ThinkTool.name
            )

            if is_think:
                # edge case: more think in one call
                call_count = sum(
                    1 for call in message.message["tool_calls"] 
                    if call["function"]["name"] == ThinkTool.name
                )

                if think_count + call_count >= self.max_think:
                    log_event(
                        _logger, logging.DEBUG, "think_count + call_count > max_think", 
                        message_idx=idx, is_think=is_think,
                        think_count=think_count,
                        call_count=call_count,
                        max_think=self.max_think
                    )

                    think_res_idxs = list(
                        filter(
                            None, 
                            [
                                find_tool_call_result(messages=messages, tool_call_id=call_id) 
                                for call_id in think_call_ids 
                            ]
                        )
                    )
                    
                    # The original call should not be dropped since it may contain both multiple 
                    # tool calls and text content, we want to "sugrically" remove the tool call.
                    # To address this identify the indexes of the tool calls to drop in the message 
                    # tool call list and compress it in place. 
                    message_tool_calls = message.message["tool_calls"]
                    _drop_think_mask = [True for _ in range(len(message_tool_calls))]
                    _drop_think_count = 0
                    _drop_think_target = think_count + call_count - self.max_think
                    for _idx, tool_call in enumerate(message_tool_calls):
                        if tool_call["id"] in think_call_ids and _drop_think_count < _drop_think_target:
                            _drop_think_mask[_idx] = False
                        _drop_think_count += 1
                    
                    message.message["tool_calls"] = list(itertools.compress(message_tool_calls, _drop_think_mask))
                    if len(message.message["tool_calls"]) == 0 and message.message.get("content") is None:
                        drop_mask[idx] = False

                    # same logic, this code sucks btw
                    _drop_think_count = 0
                    for think_res_idx in think_res_idxs:
                        if _drop_think_count < _drop_think_target:
                            drop_mask[think_res_idx] = False
                        _drop_think_count += 1
                
                think_count += call_count
                continue

            # ex. max_file_write = 2
            # [...Write...Write...Write...] -> [...[dropped]...Write...Write...]
            is_file_write, fw_call_idxs = is_tool_call(
                message=message, 
                tool_name_key=self.file_write_name
            )

            if is_file_write:
                # edge case: more write in one call
                call_count = sum(
                    1 for call in message.message["tool_calls"] 
                    if call["function"]["name"] == self.file_write_name
                )

                if file_write_count + call_count >= self.max_file_write:
                    log_event(
                        _logger, logging.DEBUG, "file_write_count + call_count > max_file_write", 
                        message_idx=idx, is_file_write=is_file_write,
                        file_write_count=file_write_count,
                        call_count=call_count,
                        max_file_write=self.max_file_write
                    )

                    fw_res_idxs = list(
                        filter(
                            None,
                            [
                                find_tool_call_result(messages=messages, tool_call_id=call_id)
                                for call_id in fw_call_idxs
                            ]
                        )
                    )

                    # same logic as Think        
                    message_tool_calls = message.message["tool_calls"]
                    _drop_fw_mask = [True for _ in range(len(message_tool_calls))]
                    _drop_fw_count = 0
                    _drop_fw_target = file_write_count + call_count - self.max_file_write
                    for _idx, tool_call in enumerate(message_tool_calls):
                        if tool_call["id"] in fw_call_idxs and _drop_fw_count < _drop_fw_target:
                            _drop_fw_mask[_idx] = False
                        _drop_fw_count += 1
                    
                    message.message["tool_calls"] = list(itertools.compress(message_tool_calls, _drop_fw_mask))
                    if len(message.message["tool_calls"]) == 0 and message.message.get("content") is None:
                        drop_mask[idx] = False

                    _drop_fw_count = 0
                    for fw_res_idx in fw_res_idxs:
                        if _drop_fw_count < _drop_fw_target:
                            drop_mask[fw_res_idx] = False
                        _drop_fw_count += 1

                file_write_count += call_count
                continue
    
        log_event(_logger, logging.DEBUG, "", drop_mask=drop_mask)
        return list(itertools.compress(messages, drop_mask))


    def __call__(self, messages: List[Message]) -> List[Message]:
        if messages[0].message.get("role", "") != "system" or \
            messages[1].message.get("role", "") != "user":
            raise ValueError("Malformed messages: expected [system, user, ...]")
        
        token_before = sum([
            message.token_count 
            for message in messages 
            if message.token_count
        ])

        # do deep copy here so we're sure context_fn doesn't change the Conversation
        _messages = copy.deepcopy(messages)
        context = [_messages[0], _messages[1]]
        
        checkpoint = self.search_checkpoint(_messages)
        if checkpoint is not None:
            context.extend(_messages[checkpoint+1:])
        else:
            context.extend(_messages[2:])

        context = self.apply_active_window(context)
        
        token_after = sum([
            message.token_count 
            for message in context
            if message.token_count
        ])
        log_event(
            _logger, logging.INFO, "Applied Context Compression",
            token_before=token_before, token_after=token_after
        )

        return context
