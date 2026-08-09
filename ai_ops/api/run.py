import uvicorn
from ai_ops.api.api import app
from ai_ops.api.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
