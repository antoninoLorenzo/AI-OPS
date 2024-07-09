from src.agent.llm.llm import LLM, Provider, Ollama, OpenRouter

AVAILABLE_PROVIDERS = {
    'ollama': {'class': Ollama, 'key_required': False},
    'open-router': {'class': OpenRouter, 'key_required': True}
}
