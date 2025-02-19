from typing import List

from src.agent import Agent
from src.core.memory import Memory, Conversation


class ConversationService:

    def __init__(self):
        self.__memory = Memory()

    def load_conversations(self) -> List[Conversation]:
        return list(self.__memory.conversations.values())

    def new_conversation(self, name: str) -> Conversation:
        new_conversation_id = max(self.__memory.conversations.keys()) + 1
        self.__memory[new_conversation_id] = Conversation(
            conversation_id=new_conversation_id,
            name=name
        )
        return self.__memory[new_conversation_id]

    def get_conversation(self, conversation_id: int) -> Conversation:
        return self.__memory[conversation_id]

    def rename_conversation(self, conversation_id: int, new_name: str):
        self.__memory[conversation_id].name = new_name
        return self.__memory[conversation_id]

    def save_conversation(self, conversation_id: int):
        self.__memory.save(conversation_id)

    def delete_conversation(self, conversation_id: int):
        self.__memory.delete(conversation_id)


CONVERSATION_SERVICE = ConversationService()


def get_conversation_service() -> ConversationService:
    return CONVERSATION_SERVICE


def query_generator(agent: Agent, conversation: Conversation):
    yield from agent.query(conversation)
