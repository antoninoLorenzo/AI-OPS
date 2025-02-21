""""""
from abc import ABC, abstractmethod
from typing import Generator
from src.core import Conversation


class Architecture(ABC):
    """
    Interface to abstract the underlying generation strategies used by the
    `Agent` class, allowing the implementation of multiple architectures that
    can be easily swapped or extended.
    """
    model: str
    architecture_name: str = 'abstract'

    @abstractmethod
    def query(
        self,
        conversation: Conversation
    ) -> Generator:
        """Handles the input from the user and generates responses in a
        streaming manner. The exact behavior depends on the specific
        implementation of the strategy.

        :param conversation: current conversation

        :returns: Generator with response text in chunks."""
        raise NotImplementedError()


class Agent:
    """High-level interface to interact with AI Assistant."""

    def __init__(
        self,
        architecture: Architecture
    ):
        """
        :param architecture: the agent architecture implementation.
        """
        self.__architecture = architecture

    def query(self, conversation: Conversation):
        """Handles the input from the user and generates responses in a
        streaming manner.

        :param conversation: current conversation

        :returns: Generator with response text in chunks."""
        yield from self.__architecture.query(conversation)

    @property
    def architecture_name(self):
        return self.__architecture.architecture_name
