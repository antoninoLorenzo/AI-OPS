from ai_ops.core.tools.terminal import (
    CommandAdmissionPolicy, 
    CommandContext, 
    PolicyResult,
    PolicyError
)
from ai_ops.core.tools.terminal.bash import CommandOutput, CommandStatus


class MockAdmissionPolicy(CommandAdmissionPolicy):

    def __init__(self, allowed: bool):
        self.allowed = allowed

    def __call__(self, ctx: CommandContext) -> PolicyResult:
        return PolicyResult(allowed=self.allowed)


class MockBashSession:
    def __init__(
        self, 
        output: str | Exception | None = None, 
        status: CommandStatus = CommandStatus.OK,
        **kwargs
    ):
        self.output = output
        self.status = status

    def run(self, command: str, **kwargs) -> CommandOutput:
        if isinstance(self.output, type) and issubclass(self.output, Exception):
            raise self.output

        return CommandOutput(output=self.output, status=self.status)