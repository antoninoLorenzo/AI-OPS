import src.core.llm.ollama

# disable endpoint check when testing
src.core.llm.ollama.check_ollama_endpoint = lambda *args, **kwargs: True