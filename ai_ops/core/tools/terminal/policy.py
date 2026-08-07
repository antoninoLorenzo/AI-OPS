import abc
from enum import StrEnum

from pydantic import BaseModel

from ai_ops.core.tools.terminal.utils import extract_executables


class CommandContext(BaseModel):
    session_id: str
    command: str


class PolicyError(StrEnum):
    PARSING_ERROR = "command parsing failed due to a syntax error"


class PolicyResult(BaseModel):
    allowed: bool
    blocked: set[str] | None = None
    reason: str | None = None


class CommandAdmissionPolicy(abc.ABC):
    
    @abc.abstractmethod
    def __call__(self, ctx: CommandContext) -> PolicyResult:
        pass


class AllowListPolicy(CommandAdmissionPolicy):
    DEFAULT = frozenset({
        # binaries are considered safe if at most they have file read 
        # here: https://gtfobins.org/#
        'ls', 'cd', 'pwd', 'cat', 'grep', 'which', 'wc', 'tree',
        'ping', 
    })

    def __init__(self, allowlist: list[str]):
        self._allowed = set(allowlist).union(AllowListPolicy.DEFAULT)

    def __call__(self, ctx: CommandContext) -> PolicyResult:
        command = ctx.command
        exectuables = extract_executables(command)
        if not exectuables:
            return PolicyResult(
                allowed=False,
                reason=PolicyError.PARSING_ERROR
            )

        not_allowed = exectuables.difference(self._allowed)
        if not_allowed:
            return PolicyResult(
                allowed=False,
                blocked=not_allowed
            )
        return PolicyResult(allowed=True)


COMMAND_POLICY_REGISTRY = {
    "allowlist": AllowListPolicy
}