import abc
from types import get_original_bases
from typing import Dict, Tuple, Callable, TypeVar, get_args, get_origin

from litellm import ChatCompletionMessageToolCall
from pydantic import BaseModel, ValidationError
from pydantic.json_schema import GenerateJsonSchema
from pydantic._internal._core_utils import is_core_schema

ToolInputT = TypeVar("ToolInput", bound=BaseModel)
ToolOutputT = TypeVar("ToolOutput", bound=BaseModel)


# https://stackoverflow.com/a/78682340
class GenerateJsonSchemaTool(GenerateJsonSchema):
    def field_title_should_be_set(self, schema) -> bool:
        return_value = super().field_title_should_be_set(schema)
        if return_value and is_core_schema(schema):
            return False
        return return_value
    

class Tool[ToolInputT, ToolOutputT](abc.ABC):
    """Generic interface for agent tools.

    A `Tool` implementation is parametrized with two pydantic `BaseModel` 
    types, one for the input payload and one for the output.
    
    This gives type guarantees and makes serialization straightforward, since 
    the input model can be serialized directly into JSON Schema using pydantic 
    following the OpenAI tool specification.

    A `Tool` implementation has to implement `__call__` to perform the tool 
    execution and `format_result` to convert the structured tool output into a 
    string representation for the LLM; this separates exec. and presentation.

    One drawback of this design is the distinction between stateless/stateful 
    tool, since stateful tools may require initialization that depends on the 
    execution context (ex. benchmarks) or tool-specific semantics.
    For this reason tool construction is handled through `ToolRegistry` that 
    maps tool names to `ToolFactory` callables, allowing for context aware 
    initialization.
    """
    name: str
    description: str

    @abc.abstractmethod
    def __call__(self, tool_args: ToolInputT) -> ToolOutputT:
        pass
    
    @staticmethod
    @abc.abstractmethod
    def format_result(tool_result: BaseModel) -> str:
        pass

    def serialize(self) -> dict:
        base = next(
            b for b in get_original_bases(type(self))
            if get_origin(b) is Tool
        )
        input_type, _ = get_args(base)
        
        json_schema = input_type.model_json_schema(schema_generator=GenerateJsonSchemaTool)
        json_schema.pop("title") # even with schema generator there's still a title key at top level
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": json_schema
            }
        }
        
    @classmethod
    def get_input_schema(cls) -> ToolInputT:
        base = next(
            b for b in get_original_bases(cls)
            if get_origin(b) is Tool
        )
        input_type, _ = get_args(base)
        return input_type


def validate_tool_call(
    available_tools: Dict[str, Tool], 
    tool_call: ChatCompletionMessageToolCall
) -> Tuple[Tool, BaseModel] | Tuple[None, str]:
    tool_name = tool_call.function.name
    raw_args = tool_call.function.arguments

    tool = available_tools.get(tool_name)
    if tool is None:
        return None, f"{tool_name} not available"

    try:
        tool_args = tool.get_input_schema().model_validate_json(raw_args)
        return tool, tool_args
    except ValidationError as exc:
        return None, f"Invalid arguments for {tool_name}: {raw_args}; error: {exc}"