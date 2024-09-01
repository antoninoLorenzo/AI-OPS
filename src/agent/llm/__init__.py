"""Exposes implemented LLM functionalities"""

from src.agent.llm.llm import (
    LLM,
    Provider,
    Ollama,
    ProviderError
)

AVAILABLE_PROVIDERS = {
    'ollama': {'class': Ollama, 'key_required': False},
}
