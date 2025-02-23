from src.core.llm import ProviderError


class MockOllamaClient:
    def __init__(self, host: str, valid_host = True):
        # valid_host is used to see how application handles Ollam not running on host
        self.__host = host
        if not valid_host:
            raise ProviderError('Ollama: invalid endpoint')

    def chat(
        model: str, 
        messages: list, 
        stream: bool, 
        options: dict,
        tools: list | None = None
    ):
        pass
