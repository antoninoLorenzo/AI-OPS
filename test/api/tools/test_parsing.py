from pytest import mark

from src.core.tools import ToolCall, get_tool_call


@mark.parametrize('parameters', [
    {
        'text': """{"name": "function_name", "arguments": {"param1": "content of param1"}}""",
        'expected_none': False
    },
    {
        'text': """{"name": "function_name", "arguments": {"param1": "\"content of param1\""}}""",
        'expected_none': False
    },
    {
        'text': """```json{"name": "function_name", "arguments": {"param1": "content of param1"}}```""",
        'expected_none': False
    },
    {
        'text': """{'name': 'function_name', 'arguments': {'param1': 'content of param1'}}""",
        'expected_none': False
    },
    {
        'text': """Here is a tool call: {'name': 'function_name', 'arguments': {'param1': 'content of param1'}}""",
        'expected_none': False
    },
    {
        'text': """<think>...</think>{'name': 'function_name', 'arguments': {'param1': 'content of param1'}}""",
        'expected_none': False
    },
    {
        'text': """{"name": "function_name", "arguments": {"param1": "content of \\"param1\\" text"}}""",
        'expected_none': False
    },
    {
        'text': """{\n     \"name\": \"function_name\",\n     \"arguments\": {\n         \"param1\": \"content of param1\"\n     }\n}""",
        'expected_none': False
    },
    {
        'text': """This is not a valid tool call""",
        'expected_none': True
    },
])
def test_tool_parsing(parameters):
    text = parameters['text']
    expected_none = parameters['expected_none']

    assert (get_tool_call(text) is None) == expected_none
