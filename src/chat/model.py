import os
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Setup for AI Agent"""
    MODEL: str = os.environ.get('MODEL', 'mistral')
    ENDPOINT: str = os.environ.get('ENDPOINT', 'http://localhost:11434')
    PROVIDER: str = os.environ.get('PROVIDER', 'ollama')
    PROVIDER_KEY: str = os.environ.get('PROVIDER_KEY', '')
    USE_RAG: bool = os.environ.get('USE_RAG', False)


AGENT_SETTINGS = AgentSettings()
