from typing import Tuple, Any

import pytest
from pydantic import BaseModel
from litellm import ChatCompletionMessageToolCall

from ai_ops.core.tools import Tool, validate_tool_call

from test.core.mocks.tool import MockTool, MockIn, MockOut, register_mock_tool


_VALIDATE_TOOL_CALL_TESTS = [
    # Case 1: a tool with wrong parameters -> (None, str) tuple
    {
        "available_tools": {MockTool.name: MockTool()},
        "tool_call": ChatCompletionMessageToolCall(
            type="function", id="1234",
            function={"name": MockTool.name, "arguments": {}}
        ),
        "expected": (type(None), str)
    },
    # Case 2: a tool not available -> (None, str) tuple
    {
        "available_tools": {MockTool.name: MockTool()},
        "tool_call": ChatCompletionMessageToolCall(
            type="function", id="1234",
            function={"name": "asd", "arguments": {}}
        ),
        "expected": (type(None), str)
    },
    # Case 3: happy-path -> (Tool, BaseModel)
    {
        "available_tools": {MockTool.name: MockTool()},
        "tool_call": ChatCompletionMessageToolCall(
            type="function", id="1234",
            function={"name": MockTool.name, "arguments": MockIn(val=1).model_dump()}
        ),
        "expected": (Tool, BaseModel)
    },
]


@pytest.mark.parametrize("test_case", _VALIDATE_TOOL_CALL_TESTS)
def test_validate_tool_call(test_case):
    def check_expected(out: Tuple[Any, Any], expected: Tuple[Any, Any]) -> bool:
        if isinstance(out[0], expected[0]) and isinstance(out[1], expected[1]):
            return True
        return False

    tool, args = validate_tool_call(
        available_tools=test_case["available_tools"], 
        tool_call=test_case["tool_call"]
    )
    assert check_expected((tool, args), test_case["expected"])