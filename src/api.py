"""
API Interface for AI-OPS:

- **Chat** (`/conversations`): Agent related operations including chat and conversation management.
"""
import os
from fastapi import FastAPI

from src.chat import router as chat_router
from src.utils import get_logger

logger = get_logger(__name__)

# --- Initialize API
app = FastAPI()
app.include_router(chat_router)


@app.get('/ping')
def ping():
    """Used by CLI to ensure API is running/reachable and acquire environment information"""
    return {'model': os.environ.get('MODEL', 'mistral')}
