"""Exposes implemented LLM functionalities"""

from src.agent.llm.llm import (
    LLM,
    Provider,
    Ollama,
    OpenRouter,
    ProviderError
)

AVAILABLE_PROVIDERS = {
    'ollama': {'class': Ollama, 'key_required': False},
    'open-router': {'class': OpenRouter, 'key_required': True}
}
