import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class RAGSettings(BaseSettings):
    """Settings for Qdrant vector database"""
    RAG_URL: str = os.environ.get('RAG_URL', 'http://localhost:6333')
    IN_MEMORY: bool = os.environ.get('IN_MEMORY', True)
    EMBEDDING_MODEL: str = os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text')
    # There the assumption that embedding url is the same of llm provider
    EMBEDDING_URL: str = os.environ.get('ENDPOINT', 'http://localhost:11434')


class APISettings(BaseSettings):
    """Setup for API"""
    PROFILE: bool = os.environ.get('PROFILE', False)


load_dotenv()
RAG_SETTINGS = RAGSettings()
API_SETTINGS = APISettings()
