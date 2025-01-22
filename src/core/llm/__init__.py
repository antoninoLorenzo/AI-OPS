"""Exposes implemented LLM functionalities"""

from src.core.llm.llm import LLM
from src.core.llm.schema import Provider, ProviderError
from src.core.llm.ollama import Ollama

AVAILABLE_PROVIDERS = {
    'ollama': {'class': Ollama, 'key_required': False},
}
