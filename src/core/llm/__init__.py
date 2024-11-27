"""Exposes implemented LLM functionalities"""

from src.core.llm.llm import (
    LLM,
    Provider,
    ProviderError,
    Ollama,
)

AVAILABLE_PROVIDERS = {
    'ollama': {'class': Ollama, 'key_required': False},
}
