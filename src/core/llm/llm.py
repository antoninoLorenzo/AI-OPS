from typing import Tuple
from dataclasses import dataclass

from src.core.llm.schema import Provider
from src.core.llm.ollama import Ollama
from src.core.memory import Conversation


@dataclass
class LLM:
    """LLM interface"""
    model: str
    inference_endpoint: str = 'http://localhost:11434'
    provider: Provider = Ollama
    api_key: str | None = None

    def __post_init__(self):
        self.provider = self.provider(
            model=self.model,
            inference_endpoint=self.inference_endpoint,
            api_key=self.api_key
        )

    def query(
        self,
        messages: Conversation
    ) -> Tuple[str, int]:
        """Generator that returns LLM response in a tuple containing:
        (chunk, token_usage).

        :param messages:
            The current conversation provided as a list of messages in the
            format [{"role": "assistant/user/system", "content": "..."}, ...]"""
        yield from self.provider.query(messages)

    def tool_query(
        self,
        messages: Conversation,
        tools: list | None = None
    ):
        """
        :param messages:
            The current conversation provided as a list of messages in the
            format [{"role": "assistant/user/system", "content": "..."}, ...]
        :param tools:
            A list of tools in the format specified by `ollama-python`,
            the conversion is managed by `tool-parse` library."""
        return self.provider.tool_query(messages, tools)

