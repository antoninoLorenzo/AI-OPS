import pytest
from pydantic import BaseModel

from ai_ops.core.tools import Tool, register_tool, ToolRegistry


class MockIn(BaseModel):
    val: int

class MockOut(BaseModel):
    val: int


class MockTool(Tool[MockIn, MockOut]):
    name = "mock_tool"
    description = "cmon do something"

    def __call__(self, tool_args: MockIn) -> MockOut:
        return MockOut(val=tool_args.val)
    
    @staticmethod
    def format_result(tool_result: MockOut) -> str:
        return str(tool_result.val)

@pytest.fixture
def register_mock_tool():
    register_tool(MockTool.name, lambda _: MockTool())
    yield 
    ToolRegistry.pop(MockTool.name)
    