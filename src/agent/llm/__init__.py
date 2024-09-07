"""Exposes implemented LLM functionalities"""

from src.agent.llm.llm import LLM, Ollama, Provider, ProviderError

AVAILABLE_PROVIDERS = {
    'ollama': {'class': Ollama, 'key_required': False},
}
