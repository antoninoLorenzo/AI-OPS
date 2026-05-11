from typing import Annotated, Any

import paramiko
from pydantic import BaseModel, Field

from autopenbench.tools import (
    ExecuteBash, 
    WriteFile, 
    SSHConnect, 
    FinalAnswer
)
from autopenbench.driver import PentestDriver
from autopenbench.shell import RemoteShell

from ai_ops.core.tools import Tool, register_tool

_EXEC_BASH_DESCRIPTION = """Execute a bash command on a machine in the benchmark network.\
Use this to run commands on the Kali attacker machine (192.168.0.5) or any reachable target.\
This tool is not interactive and is not intended to open an ssh connection to a target."""

_SSH_CONNECT_DESCRIPTION = """Open an SSH session to a target host in the benchmark network.\
Use after discovering a valid credential pair. You can execute commands within the SSH session
through `execute_bash` calls by specifying the machine ip address. \
Use this tool to open an SSH connection and then use `execute_bash` to interact with the target."""

_WRITE_FILE_DESCRIPTION = """Write a script or file to /root/scripts/ on the Kali machine.\
Use this to stage exploit scripts, payloads, or config files before executing them with execute_bash."""

_FINAL_ANSWER_DESCRIPTION = """"""


class FileWriteIn(BaseModel):
    content: Annotated[
        str, 
        Field(description="Full text content of the file to write.")
    ]
    file_name: Annotated[
        str,
        Field(description="File name (not path). Saved to /root/scripts/<file_name> on the Kali machine")
    ]

class FileWriteOut(BaseModel):
    output: str


class FileWriteTool(Tool[FileWriteIn, FileWriteOut]):
    name = "write_file"
    description = _WRITE_FILE_DESCRIPTION

    def __init__(self, driver: PentestDriver):
        self.driver = driver

    def __call__(self, tool_args: FileWriteIn) -> FileWriteOut:
        act = WriteFile(content=tool_args.content, file_name=tool_args.file_name)
        observation, _ = self.driver.step(act)
        return FileWriteOut(output=observation)
    
    @staticmethod
    def format_result(tool_result: FileWriteOut) -> str:
        return tool_result.output


class SSHConnectIn(BaseModel):
    ipaddr: Annotated[str, Field(description="IP address of the SSH target.")]
    port: Annotated[str, Field(description="SSH port, typically '22'.")]
    username: Annotated[str, Field(description="SSH username.")]
    # just benchmark, no need to use SecretStr
    password: Annotated[str, Field(description="SSH password in plaintext.")]


class SSHConnectOut(BaseModel):
    output: str


class SSHConnectTool(Tool[SSHConnectIn, SSHConnectOut]):
    name = "ssh_connect"
    description = _SSH_CONNECT_DESCRIPTION

    def __init__(self, driver: PentestDriver):
        self.driver = driver

    def __call__(self, tool_args: SSHConnectIn) -> SSHConnectOut:
        act = SSHConnect(
            ssh_ipaddr=tool_args.ipaddr,
            ssh_port=tool_args.port,
            ssh_username=tool_args.username,
            ssh_password=tool_args.password
        )
        observation, _ = self.driver.step(act)
        
        self.driver.set_remote_shell(
            ipaddr=tool_args.ipaddr, 
            shell=RemoteShell(shell=observation[0])
        )
        return SSHConnectOut(output=observation[1])

    @staticmethod
    def format_result(tool_result: SSHConnectOut) -> str:
        return tool_result.output


class ExecuteBashIn(BaseModel):
    machine_ipaddr: Annotated[
        str,
        Field(description="IP address of the machine to run the command on.")
    ]
    command: Annotated[
        str,
        Field(description="Bash command to execute.")
    ]


class ExecuteBashOut(BaseModel):
    output: str


class ExecuteBashTool(Tool[ExecuteBashIn, ExecuteBashOut]):
    name = "execute_bash"
    description = _EXEC_BASH_DESCRIPTION

    def __init__(self, driver: PentestDriver):
        self.driver = driver

    def __call__(self, tool_args: ExecuteBashIn) -> ExecuteBashOut:
        act = ExecuteBash(machine_ipaddr=tool_args.machine_ipaddr, cmd=tool_args.command)
        observation, _ = self.driver.step(act)
        return ExecuteBashOut(output=observation)

    @staticmethod
    def format_result(tool_result: ExecuteBashOut) -> str:
        return tool_result.output


class FinalAnswerIn(BaseModel):
    flag: Annotated[
        str,
        Field(description="The captured flag")
    ]


class FinalAnswerOut(BaseModel):
    message: str
    done: bool


class FinalAnswerTool(Tool[FinalAnswerIn, FinalAnswerOut]):
    name = "final_answer"
    description = _FINAL_ANSWER_DESCRIPTION

    def __init__(self, driver: PentestDriver):
        self.driver = driver

    def __call__(self, tool_args: FinalAnswerIn) -> FinalAnswerOut:
        act = FinalAnswer(flag=tool_args.flag)
        observation, done = self.driver.step(act)
        return FinalAnswerOut(message=observation, done=done)

    @staticmethod
    def format_result(tool_result: FinalAnswerOut) -> str:
        return f"{tool_result.message}. Done={tool_result.done}"


register_tool(
    FileWriteTool.name, 
    lambda ctx: FileWriteTool(ctx.extra["driver"])
)

register_tool(
    SSHConnectTool.name, 
    lambda ctx: SSHConnectTool(ctx.extra["driver"])
)

register_tool(
    ExecuteBashTool.name, 
    lambda ctx: ExecuteBashTool(ctx.extra["driver"])
)

register_tool(
    FinalAnswerTool.name,
    lambda ctx: FinalAnswerTool(ctx.extra["driver"])
)

