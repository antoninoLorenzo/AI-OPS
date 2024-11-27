import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Setup for AI Agent"""
    MODEL: str = os.environ.get('MODEL', 'mistral')
    ENDPOINT: str = os.environ.get('ENDPOINT', 'http://localhost:11434')
    PROVIDER: str = os.environ.get('PROVIDER', 'ollama')
    PROVIDER_KEY: str = os.environ.get('PROVIDER_KEY', '')
    USE_RAG: bool = os.environ.get('USE_RAG', False)


class RAGSettings(BaseSettings):
    """Settings for Qdrant vector database"""
    RAG_URL: str = os.environ.get('RAG_URL', 'http://localhost:6333')
    IN_MEMORY: bool = os.environ.get('IN_MEMORY', True)
    EMBEDDING_MODEL: str = os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text')
    # There the assumption that embedding url is the same of llm provider
    EMBEDDING_URL: str = os.environ.get('ENDPOINT', 'http://localhost:11434')


class APISettings(BaseSettings):
    """Setup for API"""
    ORIGINS: list = [
        # TODO
    ]
    PROFILE: bool = os.environ.get('PROFILE', False)


load_dotenv()
AGENT_SETTINGS = AgentSettings()
RAG_SETTINGS = RAGSettings()
API_SETTINGS = APISettings()
