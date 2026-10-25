import copy

from pydantic import BaseModel

from ai_ops.core.context.transform import ContextTransform
from ai_ops.core.conversation import (
    Message,
    find_tool_call_result,
    get_tool_calls,
)
from ai_ops.core.tools import Terminal, ToolRegistry

DEFAULT_TERMINAL_MAX_TOKENS = 2_000


class TerminalOutputCompactionConfig(BaseModel):
    terminal_alias: str = Terminal.name
    max_tokens: int = DEFAULT_TERMINAL_MAX_TOKENS
    head_lines: int = 10
    tail_lines: int = 10


class TerminalOutputCompaction(ContextTransform):
    @classmethod
    def config_schema(cls) -> type[BaseModel] | None:
        return TerminalOutputCompactionConfig

    def __init__(
        self, 
        terminal_alias: str = Terminal.name,
        max_tokens: int = DEFAULT_TERMINAL_MAX_TOKENS,
        head_lines: int = 10,
        tail_lines: int = 10,
    ):
        self.terminal_alias = terminal_alias
        self.max_tokens = max_tokens
        self.head_lines = head_lines
        self.tail_lines = tail_lines
        self._line_limit = 1000
       
        spec = ToolRegistry.get(terminal_alias)
        if spec is None:
            self._no_op = True
            self._terminal = None
        else:
            self._no_op = False
            self._terminal = spec.tool
        
    def __call__(self, messages: list[Message]) -> list[Message]:
        if self._no_op or self._terminal is None:
            return messages

        context = copy.deepcopy(messages)

        for message in context:            
            for call_id, tool_name, _ in get_tool_calls(message):
                if tool_name != self._terminal.name:
                    continue
                
                idx = find_tool_call_result(messages=context, tool_call_id=call_id)
                if idx is None:
                    continue

                tool_result = context[idx]
                if tool_result.token_count < self.max_tokens:
                    continue

                masked = self.__mask_terminal_output(tool_result.message["content"])
                context[idx].message["content"] = masked


        return context

    def __mask_terminal_output(self, content: str) -> str:
        lines = content.splitlines()
        if len(lines) <= self.head_lines + self.tail_lines:
            return "\n".join(self.__clip_lines(lines))

        head = self.__clip_lines(lines[:self.head_lines])
        tail = self.__clip_lines(lines[-self.tail_lines:])

        dropped = "\n".join(lines[self.head_lines:-self.tail_lines])
        masked = (
            "\n".join(head)
            + f"\n[{len(dropped)} characters dropped...]\n"
            + "\n".join(tail)
        )

        return masked if len(masked) < len(content) \
            else "\n".join(self.__clip_lines(lines))

    def __clip_lines(self, lines: list[str]) -> list[str]:
        return [line[:self._line_limit] for line in lines]

