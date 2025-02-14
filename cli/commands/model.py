from typing import Callable, Any, List

from pydantic import BaseModel


class CommandParameter(BaseModel):
    parameter_name: str
    parameter_value: Any = None
    required: bool = True


class CommandSchema(BaseModel):
    command_name: str
    command_parameters: List[CommandParameter] = []


class Command(BaseModel):
    command_schema: CommandSchema
    command_callback: Callable
    requires_app_context: bool = True


class ParserException(Exception):
    pass
