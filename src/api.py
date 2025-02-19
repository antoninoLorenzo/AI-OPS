"""
API Interface for AI-OPS:

- **Chat** (`/conversations`): Agent related operations including chat and conversation management.
"""
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from src.config import API_SETTINGS
from src.chat import router as chat_router
from src.utils import get_logger

logger = get_logger(__name__)

# --- Initialize API
app = FastAPI()
app.include_router(chat_router)

# TODO: implement proper CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=API_SETTINGS.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if API_SETTINGS.PROFILE:
    try:
        from src.routers.monitoring import monitor_router
        app.mount('/monitor', monitor_router)
    except RuntimeError as monitor_startup_err:
        logger.error("Monitoring disabled: ", str(monitor_startup_err))


@app.get('/ping')
def ping():
    """Used to check if API is on"""
    return status.HTTP_200_OK

