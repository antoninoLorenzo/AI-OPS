import json
from enum import StrEnum
from typing import List, Literal, Any

from pydantic import BaseModel, validate_call
from pydantic.main import IncEx


class Role(StrEnum):
    """Message role"""
    SYS = 'system'
    USER = 'user'
    ASSISTANT = 'assistant'
    TOOL = 'tool'

    @staticmethod
    def from_str(item):
        """Convert a string role to Role"""
        try:
            return Role(item)
        except ValueError:
            return None


class Message(BaseModel):
    """Message object"""
    role: Role
    content: str
    __token_length: int = 0

    def model_dump(self, **kwargs):
        return {'role': str(self.role), 'content': self.content}

    # using @property causes issues with BaseModel
    def get_tokens(self) -> int:
        return self.__token_length

    def set_tokens(self, val: int):
        self.__token_length = val


class Conversation(BaseModel):
    """Represents a conversation"""
    name: str
    messages: List[Message] = []
    _tokens: int = 0

    @validate_call
    def add(self, message: Message):
        """Append a message"""
        self.messages.append(message)

    def model_dump(self, **kwargs):
        # return only a list of messages when converting to list[dict]
        return [
            message.model_dump()
            for message in self.messages
        ]

    def __len__(self):
        return len(self.messages)

    @staticmethod
    def from_json(path: str):
        """
        Get a session from a JSON file.
        Reason for not using model_validate_json: saved JSON file contains
        ID, instead Conversation doesn't have an ID field.
        """
        try:
            with open(str(path), 'r', encoding='utf-8') as fp:
                data = json.load(fp)
        except json.decoder.JSONDecodeError:
            return -1, None

        session = Conversation(
            name=data['name'],
            messages=[
                Message(role=Role.from_str(msg['role']), content=msg['content'])
                for msg in data['messages']
            ],
        )

        return data['id'], session

