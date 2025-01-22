from abc import ABC, abstractmethod
from typing import Tuple
from dataclasses import dataclass

from src.core.memory import Conversation


@dataclass
class Provider(ABC):
    """Defines a common interface for all LLM providers.
    Current implementation only supports Ollama as provider."""
    model: str
    inference_endpoint: str = 'http://localhost:11434'
    api_key: str | None = None

    @abstractmethod
    def query(self, messages: Conversation) -> Tuple[str, Tuple]:
        """Implement to makes query to the LLM provider"""

    @abstractmethod
    def tool_query(self, messages: Conversation, tools: list | None = None):
        """Implement for LLM tool calling"""


class ProviderError(Exception):
    """Just a wrapper to Exception for error handling
    when an error is caused by the LLM provider"""