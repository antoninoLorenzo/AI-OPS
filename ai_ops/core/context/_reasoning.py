import copy

from pydantic import BaseModel

from ai_ops.core.context.transform import ContextTransform
from ai_ops.core.conversation import Message, message_has_role


class ReasoningCompaction(ContextTransform):
    @classmethod
    def config_schema(cls) -> type[BaseModel] | None:
        return None

    def __call__(self, messages: list[Message]) -> list[Message]:
        context = copy.deepcopy(messages)
        
        for message in context:
            if not message_has_role(message, "assistant"):
                continue

            if message.message.get("reasoning_content") is not None:
                message.message["reasoning_content"] = ""

        return context
