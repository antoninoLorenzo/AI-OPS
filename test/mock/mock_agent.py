from typing import Generator

from src.agent import Agent, Architecture
from src.core import Conversation


class MockArchitecture(Architecture):
    architecture_name = 'mock'

    def query(self, conversation: Conversation) -> Generator:
        usr_msg = conversation.messages[-1]
        response = f'Response for: {usr_msg}'
        for c in response:
            yield c


MOCK_AGENT = Agent(MockArchitecture())


def get_mock_agent():
    return MOCK_AGENT
