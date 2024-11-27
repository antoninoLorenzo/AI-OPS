"""
API Interface for AI-OPS, includes Sessions routes and Collections routes:

- **Sessions**: Agent related operations including chat and conversation management.

- **Collections**: RAG related operations (...)

### RAG Routes
- /collections/list    : Returns available Collections.
- /collections/new     : Creates a new Collection.
- /collections/upload/ : Upload document to an existing Collection
"""
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from src.config import API_SETTINGS
from src.routers import session_router
from src.utils import get_logger

logger = get_logger(__name__)

# --- Initialize API
app = FastAPI()
app.include_router(session_router)

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

