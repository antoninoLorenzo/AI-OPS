import uuid
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional, Annotated

from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool
from ai_ops.core.prompt import get_prompt
from ai_ops.core.tools.terminal.bash import BashSession, CommandStatus, Status2String
from ai_ops.core.tools.terminal.policy import CommandContext, CommandAdmissionPolicy
from ai_ops.core.log import get_logger, log_event, logging


_logger = get_logger(__name__)

DEFAULT_WORK_DIR = Path('/tmp/ai_ops/')
if not DEFAULT_WORK_DIR.exists():
    _logger.info("Creating terminal working directory '/tmp/ai_ops/'")
    DEFAULT_WORK_DIR.mkdir(parents=True)

MAX_COMMAND_TIMEOUT_S = 300.0

class TerminalRequest(BaseModel):
    command: Annotated[
        str, 
        Field(description="The bash command to execute.")
    ]
    session_id: Annotated[
        Optional[str],
        Field(description="Session ID to reuse an existing terminal session. Omit to create a new session.")
    ] = None
    interactive: Annotated[
        Optional[bool],
        Field(description="Set to true for interactive commands. Status will not be captured for interactive commands.")
    ] = False
    timeout: Annotated[
        Optional[float],
        Field(description=(
            "Maximum seconds to wait for the command to complete. Defaults to the session default if omitted. "
            F"The value is clamped to {MAX_COMMAND_TIMEOUT_S}s."
        ))
    ] = None


class TerminalResult(BaseModel):
    session_id: str
    command: str
    allowed: bool
    output: Optional[str] = None
    status: Optional[CommandStatus] = None
    timed_out: bool = False


class Terminal(Tool[TerminalRequest, TerminalResult]):
    name = "terminal"
    description = get_prompt(name="terminal", kind="tool")

    def __init__(
        self, 
        conversation_id: str,
        working_directory: Path,
        policies: Tuple[CommandAdmissionPolicy]
    ):
        self.conversation_id = conversation_id # => tied to conversation
        self.working_directory = working_directory
        if not self.working_directory.exists():
            self.working_directory.mkdir(parents=True, exist_ok=True)
        self.__sessions: Dict[str, BashSession] = {}
        self.__policies: Tuple[CommandAdmissionPolicy] = policies

    def __call__(self, tool_args: TerminalRequest) -> TerminalResult:
        command = tool_args.command
        session_id = tool_args.session_id if tool_args.session_id else str(uuid.uuid4())

        for policy in self.__policies:
            policy_result = policy(CommandContext(conversation_id=self.conversation_id, command=command))
            if not policy_result.allowed:
                log_event(
                    _logger, logging.WARNING, "Command not allowed",
                    conversation_id=self.conversation_id,
                    command=command, reason=policy_result.reason
                )
                return TerminalResult(session_id=session_id, command=command, allowed=False)
            
        bash_session = self.__sessions.get(session_id)
        if bash_session is None:
            log_event(_logger, logging.INFO, "Crearing BashSession", session_id=session_id)
            self.__sessions[session_id] = BashSession(working_directory=str(self.working_directory))
            bash_session = self.__sessions[session_id]
        
        timeout = max(5.0, min(tool_args.timeout, MAX_COMMAND_TIMEOUT_S)) if tool_args.timeout else None
        result = bash_session.run(
            command=command, 
            interactive=tool_args.interactive,
            timeout=timeout
        )
        return TerminalResult(
            session_id=session_id,
            command=command,
            allowed=True,
            output=result.output,
            status=result.status,
            timed_out=result.timed_out
        )


    @staticmethod
    def format_result(terminal_result: TerminalResult) -> str:
        if not terminal_result.allowed:
            return (
                f"Session: {terminal_result.session_id}\n"
                f"Command: {terminal_result.command}\n"
                f"Status: BLOCKED\n"
                f"The command was rejected by the security policy."
            )

        output = terminal_result.output or "(no output)"
        status = Status2String[terminal_result.status] or "unknown"

        return (
            f"Session: {terminal_result.session_id}\n"
            f"Command: {terminal_result.command}\n"
            f"Timed Out: {terminal_result.timed_out}\n"
            f"Status: {status}\n"
            f"Output:\n{output}"
        )
    
    def __del__(self):
        for shell in self.__sessions.values():
            if getattr(shell, "close", None):
                shell.close()
