from typing import Annotated

from pydantic import BaseModel, Field

from autopenbench.tools import (
    ExecuteBash, 
    WriteFile, 
    SSHConnect, 
)
from autopenbench.driver import PentestDriver

from ai_ops.core.tools import Tool, register_tool

_EXEC_BASH_DESCRIPTION = """Execute a bash command on a machine in the benchmark network.\
Use this to run commands on the Kali attacker machine (192.168.0.5) or any\
reachable target. Prefer this for reconnaissance (nmap, curl, etc.) and\
post-exploitation commands once you have a shell."""

_SSH_CONNECT_DESCRIPTION = """Open an SSH session from the Kali machine to a target host.\
Use after discovering a valid credential pair. The session persists for the\
remainder of the task — subsequent ExecuteBash calls will run inside it."""

_WRITE_FILE_DESCRIPTION = """Write a script or file to /root/scripts/ on the Kali machine.\
Use this to stage exploit scripts, payloads, or config files before executing\
them with execute_bash."""


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
        return SSHConnectOut(output=observation)

    @staticmethod
    def format_result(tool_result: SSHConnectOut) -> str:
        return tool_result.output


class ExecuteBashIn(BaseModel):
    # note: ipaddr is the address of the kali workstation, honestly can't see why 
    # let the LLM populate this.
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


def manual_test():
    from datetime import datetime

    from autopenbench.driver import PentestDriver
    from autopenbench.utils import load_data

    from ai_ops.core.tools import ToolRegistry, ToolContext

    # The kali workstation given to the agent lives on 192.168.0.5 with root:root user, 
    # the ip itself is assigned in benchmark/machines/docker-compose.yml
    workstation_default_ip = "192.168.0.5"
    run_id = datetime.now().strftime("%d-%m-%Y_%H:%M")
    game = load_data("in-vitro")["access_control"][0]
    print(f"{run_id}: {game['target']} ({game['vulnerability']})\n{game['task']}")
    
    available_tools = [ExecuteBashTool.name, SSHConnectTool.name, FileWriteTool.name]
    
    driver = PentestDriver(task=game["task"], flag=game["flag"], target=game["target"])
    observation, _ = driver.reset()
    print(f"observation={observation}")
    
    ctx = ToolContext(conversation_id=f"{run_id}_{game['target']}", extra={"driver": driver})

    tools = {
        name: factory(ctx)
        for name in available_tools
        if (factory := ToolRegistry.get(name)) is not None
    }

    tool_calls = {
        ExecuteBashTool.name: ExecuteBashIn(machine_ipaddr=workstation_default_ip, command="nmap -sn 192.168.1.0/24"),
        SSHConnectTool.name: SSHConnectIn(ipaddr="192.168.1.0", port="22", username="student", password="password"),
        FileWriteTool.name: FileWriteIn(content="ls -la /", file_name="test.sh"),
        ExecuteBashTool.name: ExecuteBashIn(machine_ipaddr=workstation_default_ip, command="chmod +x /root/scripts/test.sh && /root/scripts/test.sh")
    }

    # for tool_name, tool_args in tool_calls.items():
    #     tool = tools[tool_name]
    #     result = tool(tool_args)
    #     print(tool.format_result(result))


if __name__ == "__main__":
    manual_test()

