# Add a Tool to AI-OPS

You can extend the AI-OPS agent by subclassing the generic `Tool`, registering it in the application, and adding it to the `tools` list in `AgentConfig` when you construct `AgentRunner`.

> **Extension model:** this only works when using `ai_ops.core` directly in your own code. The API server doesn't currently expose a way to register custom tools at runtime (the only way to add a tool there is by contributing it to the project). MCP-based tool extension is not currently planned.

## Basic Tool

Register the tool at module load time, before you build `AgentConfig` (`register_tool` populates a global registry, so if it runs after `AgentRunner` is constructed, the tool won't be found).

```python
from typing import Annotated
from pydantic import BaseModel, Field

from ai_ops.core.tools import Tool, register_tool
from ai_ops.core.runner import AgentConfig


class MyInput(BaseModel):
    var: Annotated[int, Field(description="The value to double")]

class MyOutput(BaseModel):
    result: int

class MyTool(Tool[MyInput, MyOutput]):
    name = "my_tool"
    description = "Doubles the given integer."

    # execution logic
    def __call__(self, tool_args: MyInput) -> MyOutput:
        return MyOutput(result=tool_args.var * 2)

    # converting to text for LLMs
    @staticmethod
    def format_result(tool_result: MyOutput) -> str:
        return f"Result: {tool_result.result}"


register_tool(MyTool, lambda _: MyTool())

AgentConfig(tools=[MyTool, ...])
```

## Tool State

`register_tool(tool_class, factory)` takes the class plus a factory `lambda`, not an instance, so `AgentRunner` can build the tool without knowing its constructor signature. The input/output models are read from the `Tool[In, Out]` base, so you don't pass them to `register_tool` separately. If your tool needs configuration or shared state, receive it through `ToolContext`:

`ai_ops.core.tools.__init__`
```python
@dataclass
class ToolContext:
    session_id: str
    model_id: str | None = None
    is_new_conversation: bool = True
    command_policies: tuple[CommandAdmissionPolicy] = field(default_factory=list)
    # anything that doesn't deserve a first-class field
    extra: dict[str, Any] | None = None
```

```python
from typing import Annotated
from pydantic import BaseModel, Field

from ai_ops.core.tools import Tool, ToolContext, register_tool
from ai_ops.core.runner import AgentConfig


class MyInput(BaseModel):
    var: Annotated[int, Field(description="The value to multiply")]

class MyOutput(BaseModel):
    result: int

class MyTool(Tool[MyInput, MyOutput]):
    name = "my_tool"
    description = "Multiplies the given integer by a configured factor."

    def __init__(self, session_id: str, multiplier: int):
        self.session_id = session_id
        self.multiplier = multiplier

    # execution logic
    def __call__(self, tool_args: MyInput) -> MyOutput:
        return MyOutput(result=tool_args.var * self.multiplier)

    # converting to text for LLMs
    @staticmethod
    def format_result(tool_result: MyOutput) -> str:
        return f"Result: {tool_result.result}"


register_tool(
    MyTool,
    lambda ctx: MyTool(session_id=ctx.session_id, multiplier=ctx.extra["multiplier"]),
)

AgentConfig(tools=[MyTool, ...])
```

## Human-in-the-Loop Confirmation

Tools that perform sensitive operations should require user confirmation when the agent runs in supervised mode. A tool that requires confirmation:

- sets `requires_confirmation = True`
- implements `evaluate(tool_args) -> bool`, returning `True` when *this specific call* needs confirmation (or can't run at all in unsupervised mode)
- implements `not_admitted_result(tool_args)`, building the result reported when the call is denied or times out

```python
from typing import Annotated
from pydantic import BaseModel, Field

from ai_ops.core.tools import Tool, register_tool
from ai_ops.core.runner import AgentConfig


class MyInput(BaseModel):
    var: Annotated[int, Field(description="The value to double")]

class MyOutput(BaseModel):
    result: int
    error: str | None = None

class MyTool(Tool[MyInput, MyOutput]):
    name = "my_tool"
    description = "Doubles the given integer; requires confirmation above 10."
    requires_confirmation = True

    def evaluate(self, tool_args: MyInput) -> bool:
        return tool_args.var > 10

    def not_admitted_result(self, tool_args: MyInput) -> MyOutput:
        return MyOutput(result=-1, error="var can't be more than 10 without confirmation")

    # execution logic (always assumes the call was already admitted)
    def __call__(self, tool_args: MyInput) -> MyOutput:
        return MyOutput(result=tool_args.var * 2)

    # converting to text for LLMs
    @staticmethod
    def format_result(tool_result: MyOutput) -> str:
        return f"Result: {tool_result.result}"


register_tool(MyTool, lambda _: MyTool())

AgentConfig(tools=[MyTool, ...])
```

`evaluate` and `not_admitted_result` are only ever consulted when `requires_confirmation = True`; a denied or timed-out call still flows back to the model as a normal tool result via `not_admitted_result`, so the conversation stays well-formed.