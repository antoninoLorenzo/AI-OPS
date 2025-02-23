from typing import List, Optional

from src.agent import Agent, init_default_architecture
from src.chat.model import AGENT_SETTINGS
from src.core.memory import Conversation, Memory
from src.core import (
    LLM,
    AVAILABLE_PROVIDERS,
    TOOL_REGISTRY,
)


class ConversationService:
    """Manages an instance of conversational Memory."""

    def __init__(self):
        self.__memory = Memory()

    def load_conversations(self) -> List[Conversation]:
        return list(self.__memory.conversations.values())

    def new_conversation(self, name: str) -> Conversation:
        if len(self.__memory.conversations) > 0:
            new_conversation_id = max(self.__memory.conversations.keys()) + 1
        else:
            new_conversation_id = 0
        self.__memory[new_conversation_id] = Conversation(
            conversation_id=new_conversation_id,
            name=name
        )
        return self.__memory[new_conversation_id]

    def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        """
        :return: a Conversation or None
        """
        return self.__memory[conversation_id]

    def rename_conversation(self, conversation_id: int, new_name: str):
        if conversation_id in self.__memory:
            self.__memory[conversation_id].name = new_name
            return self.__memory[conversation_id]
        return None

    def save_conversation(self, conversation_id: int) -> bool:
        return self.__memory.save(conversation_id)

    def delete_conversation(self, conversation_id: int) -> bool:
        return self.__memory.delete(conversation_id)


def build_agent_default_architecture() -> Agent:
    provider = AGENT_SETTINGS.PROVIDER
    if provider not in AVAILABLE_PROVIDERS.keys():
        raise RuntimeError(f'{provider} not supported.')
    llm_provider = AVAILABLE_PROVIDERS[provider]['class']
    key_required = AVAILABLE_PROVIDERS[provider]['key_required']

    if key_required and len(AGENT_SETTINGS.PROVIDER_KEY) == 0:
        raise RuntimeError(
            f'Missing PROVIDER_KEY environment variable for {provider}.'
        )

    llm = LLM(
        model=AGENT_SETTINGS.MODEL,
        inference_endpoint=AGENT_SETTINGS.ENDPOINT,
        provider=llm_provider,
        api_key=AGENT_SETTINGS.PROVIDER_KEY
    )
    architecture = init_default_architecture(
        llm=llm,
        tool_registry=TOOL_REGISTRY
    )

    return Agent(architecture)


AGENT = build_agent_default_architecture()
CONVERSATION_SERVICE = ConversationService()


def get_agent() -> Agent:
    """Agent DI"""
    return AGENT


def get_conversation_service() -> ConversationService:
    """Conversation DI"""
    return CONVERSATION_SERVICE


def query_generator(agent: Agent, conversation: Conversation):
    yield from agent.query(conversation)
