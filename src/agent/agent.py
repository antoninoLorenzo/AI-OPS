"""
This module defines the core classes and interfaces for the AI Penetration
Testing Assistant system. It provides the foundational components for handling
user interactions, managing conversations, and processing user inputs using
different agent architectures.

Classes:
    - `AgentArchitecture`: An abstract base class that defines the contract for
      various  architectures used by the assistant to process user queries.
      Implementations of this interface can support different models or
      strategies for generating responses.

    - `Agent`: A high-level interface that manages interaction with the
      penetration testing assistant. It abstracts session management, delegates
      user queries to a specific `AgentArchitecture` implementation, handles
      session persistence.
"""
from abc import ABC, abstractmethod
from typing import Generator
from src.core import Memory


class AgentArchitecture(ABC):
    """Interface defining the contract for various agent architectures.

    This interface abstracts the underlying generation strategies used by
    the `Agent` class, allowing the implementation of multiple architectures
    that can be easily swapped or extended."""
    model: str
    architecture_name: str

    def __init__(self):
        self.memory = Memory()

    @abstractmethod
    def query(
        self,
        session_id: int,
        user_input: str
    ) -> Generator:
        """Handles the input from the user and generates responses in a
        streaming manner. The exact behavior depends on the specific
        implementation of the strategy.

        :param session_id: The session identifier.
        :param user_input: The user's input query.

        :returns: Generator with response text in chunks."""
        raise NotImplementedError()

    @abstractmethod
    def new_session(self, session_id: int):
        raise NotImplementedError()


class Agent:
    """This class serves as a high-level interface for managing the interaction
     with the penetration testing assistant. It abstracts session management
     and delegates querying to a specific `AgentArchitecture` implementation.
    """

    def __init__(
        self,
        architecture: AgentArchitecture
    ):
        """
        :param architecture: the agent architecture implementation that handles
         the core query processing and responses.
        """
        self.agent = architecture

    def query(self, session_id: int, user_input: str):
        """Handles the input from the user and generates responses in a
        streaming manner.

        This method delegates the query to the specified `AgentArchitecture`

        :param session_id: The session identifier.
        :param user_input: The user's input query.

        :returns: Generator with response text in chunks."""
        if not isinstance(user_input, str) or len(user_input) == 0:
            raise ValueError(f'Invalid input: {user_input} [{type(user_input)}]')
        # TODO: if Prometheus Metric is injected update it with token
        #  consumption (arch_name, sid, context_length)
        yield from self.agent.query(session_id, user_input)

    def new_session(self, sid: int):
        """Initializes a new conversation"""
        self.agent.new_session(sid)

    def get_session(self, sid: int):
        """Open existing conversation"""
        return self.agent.memory.get_conversation(sid)

    def get_sessions(self):
        """Returns list of Session objects"""
        return self.agent.memory.get_conversations()

    def save_session(self, sid: int):
        """Saves the specified session to JSON"""
        self.agent.memory.save_conversation(sid)

    def delete_session(self, sid: int):
        """Deletes the specified session"""
        self.agent.memory.delete_conversation(sid)

    def rename_session(self, sid: int, session_name: str):
        """Rename the specified session"""
        self.agent.memory.rename_conversation(sid, session_name)

