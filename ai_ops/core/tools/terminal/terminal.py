import uuid
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional, Annotated

from pydantic import BaseModel, Field

from ai_ops.core.tools.base import Tool
from ai_ops.core.tools.terminal.bash import BashSession
from ai_ops.core.tools.terminal.policy import CommandContext, CommandAdmissionPolicy


_logger = logging.getLogger(__name__)

DEFAULT_WORK_DIR = Path('/tmp/ai_ops/')
if not DEFAULT_WORK_DIR.exists():
    _logger.info("Creating terminal working directory '/tmp/ai_ops/'")
    DEFAULT_WORK_DIR.mkdir(parents=True)


_TERMINAL_DESCRIPTION = """"""


class TerminalRequest(BaseModel):
    command: Annotated[
        str, 
        Field(description="The bash command to execute.")
    ]
    session_id: Annotated[
        Optional[str],
        Field(description="Specify terminal session where the command should run.")
    ]


class TerminalResult(BaseModel):
    session_id: str
    command: str
    allowed: bool
    output: Optional[str] = None
    status: Optional[str] = None


class Terminal(Tool[TerminalRequest, TerminalResult]):
    name = "terminal"
    description = _TERMINAL_DESCRIPTION

    def __init__(
        self, 
        working_directory: str,
        policies: Tuple[CommandAdmissionPolicy]
    ):
        self.working_directory = working_directory
        self.__sessions: Dict[str, BashSession] = {}
        self.__policies: Tuple[CommandAdmissionPolicy] = policies


    def __call__(self, tool_args: TerminalRequest) -> TerminalResult:
        command = tool_args.command
        session_id = tool_args.session_id

        for policy in self.__policies:
            allowed = policy(CommandContext(session_id=session_id, command=command))
            if not allowed.admission_status:
                _logger.warning(
                    f"Command Not Allowed: policy={type(policy).__name__} "
                    f"session_id={session_id} command={command} "
                    f"blocked={allowed.blocked} reason={allowed.reason}"
                )
                return TerminalResult(session_id=session_id, command=command, allowed=False)
            
        bash_session = self.__sessions.get(session_id)
        if bash_session is None:
            session_id = session_id or str(uuid.uuid4())
            _logger.info(f"Creating new BashSession with session_id={session_id}")
            self.__sessions[session_id] = BashSession()
            bash_session = self.__sessions[session_id]
        
        result = bash_session.run(command=command, interactive=True)
        return TerminalResult(
            session_id=session_id,
            command=command,
            allowed=True,
            output=result.output,
            status=result.status
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
        status = terminal_result.status or "unknown"

        return (
            f"Session: {terminal_result.session_id}\n"
            f"Command: {terminal_result.command}\n"
            f"Status: {status}\n"
            f"Output:\n{output}"
        )
  