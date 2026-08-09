from typing import Callable

from fastapi import FastAPI, Request

from ai_ops.config import AI_OPS_BASE_DIR
from ai_ops.api.config import get_settings
from ai_ops.core.log import get_logger, log_event, logging


_logger = get_logger(__name__)


def register_profile(app: FastAPI):
    settings = get_settings()
    if not settings.debug:
        log_event(_logger, logging.DEBUG, "Set `AI_OPS_DEBUG` to True to enable profiling.")
        return

    try:
        import pyinstrument
    except ImportError:
        log_event(_logger, logging.DEBUG, "Install `pyinstrument` to profile api.")
        return

    from pyinstrument import Profiler
    from pyinstrument.renderers.html import HTMLRenderer

    profile_dir = AI_OPS_BASE_DIR / "profile"
    profile_dir.mkdir(exist_ok=True)

    @app.middleware("http")
    async def profile_request(request: Request, call_next: Callable):

        if not request.query_params.get("profile", False):
            return await call_next(request)
        
        with Profiler(async_mode="enabled") as profiler:
            response = await call_next(request)

        renderer = HTMLRenderer()
        rq_path = request.url.path.replace('/', '-')
        with open(f"{str(profile_dir)}/profile-{rq_path}.html", "w") as out:
            out.write(profiler.output(renderer=renderer))
        
        return response
