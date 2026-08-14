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


# Sentinel value returned by MockConfirmTool.not_admitted_result so tests can
# tell a not-executed (blocked/denied) call from an executed one.
NOT_ADMITTED_VAL = -1


class MockConfirmTool(Tool[MockIn, MockOut]):
    name = "mock_confirm_tool"
    description = "needs confirmation"
    requires_confirmation = True

    def __call__(self, tool_args: MockIn) -> MockOut:
        return MockOut(val=tool_args.val)

    def evaluate(self, tool_args: MockIn) -> bool:
        # always blocked -> always goes through the confirmation path
        return True

    def not_admitted_result(self, tool_args: MockIn) -> MockOut:
        return MockOut(val=NOT_ADMITTED_VAL)

    @staticmethod
    def format_result(tool_result: MockOut) -> str:
        return str(tool_result.val)

class MockSkipCompactionTool(Tool[MockIn, MockOut]):
    name = "skip_compaction"
    allow_compaction = False

    def __call__(self, tool_args: MockIn) -> MockOut:
        return MockOut(val=tool_args.val)

    @staticmethod
    def format_result(tool_result: MockOut) -> str:
        return str(tool_result.val)


class MockPreserveStateTool(Tool[MockIn, MockOut]):
    name = "preserve_state"
    expected_state = "State preserved"

    def __call__(self, tool_args: MockIn) -> MockOut:
        return MockOut(val=tool_args.val)

    @staticmethod
    def format_result(tool_result: MockOut) -> str:
        return str(tool_result.val)

    def post_compaction_state(self):
        return self.expected_state


@pytest.fixture
def register_mock_tool():
    register_tool(MockTool, lambda _: MockTool())
    yield
    ToolRegistry.pop(MockTool.name)


@pytest.fixture
def register_mock_confirm_tool():
    register_tool(MockConfirmTool, lambda _: MockConfirmTool())
    yield
    ToolRegistry.pop(MockConfirmTool.name)


@pytest.fixture
def register_mock_skip_compaction_tool():
    register_tool(MockSkipCompactionTool, lambda _: MockSkipCompactionTool())
    yield
    ToolRegistry.pop(MockSkipCompactionTool.name)


@pytest.fixture
def register_mock_carry_state_tool():
    register_tool(MockPreserveStateTool, lambda _: MockPreserveStateTool())
    yield
    ToolRegistry.pop(MockPreserveStateTool.name)