import abc
from enum import StrEnum
from typing import List, Optional, Set

from pydantic import BaseModel

from ai_ops.core.tools.terminal.utils import extract_executables


class CommandContext(BaseModel):
    session_id: str
    command: str


class PolicyError(StrEnum):
    PARSING_ERROR = "command parsing failed due to a syntax error"


class PolicyResult(BaseModel):
    admission_status: bool
    blocked: Optional[Set[str]] = None
    reason: Optional[str] = None


class CommandAdmissionPolicy(abc.ABC):
    
    @abc.abstractmethod
    def __call__(self, ctx: CommandContext) -> PolicyResult:
        pass


class AllowListPolicy(CommandAdmissionPolicy):
    DEFAULT = {
        'ls', 'cd', 'echo'
    }

    def __init__(self, allowlist: List[str]):
        self._allowed = set(allowlist).union(AllowListPolicy.DEFAULT)

    def __call__(self, ctx: CommandContext) -> PolicyResult:
        command = ctx.command
        exectuables = extract_executables(command)
        if not exectuables:
            return PolicyResult(
                admission_status=False,
                reason=PolicyError.PARSING_ERROR
            )

        not_allowed = exectuables.difference(self._allowed)
        if not_allowed:
            return PolicyResult(
                admission_status=False,
                blocked=not_allowed
            )
        return PolicyResult(admission_status=True)


# class BlockListPolicy(CommandAdmissionPolicy):
#     def __init__(self, blocklist: List[str]):
#         self._blocked = blocklist
# 
#     def __call__(self, ctx: CommandContext) -> PolicyResult:
#         pass
