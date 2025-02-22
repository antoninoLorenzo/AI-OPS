import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """Setup for API"""
    PROFILE: bool = os.environ.get('PROFILE', False)


load_dotenv()
API_SETTINGS = APISettings()
