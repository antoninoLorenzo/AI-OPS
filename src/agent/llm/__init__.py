from src.agent.llm.llm import LLM, Provider, Ollama

AVAILABLE_PROVIDERS = {
    'ollama': {'class': Ollama, 'key_required': False}
}
